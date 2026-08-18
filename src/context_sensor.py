"""Model-aware session context sensor (ADR-0018).

Single source of truth for the session wrap-up / handoff feature. Both hook
wrappers (``.claude/hooks/context_statusline.py``, ``context_guard.py``) and the
``wrapping-up-sessions`` skill delegate here, so the wrappers stay thin and the
threshold model / transcript-parsing / spawn-command logic lives in exactly one
coverage-measured place (``src/`` is on the ``--cov`` perimeter).

Responsibilities:
    * Load the per-model threshold config (``config/model_context_profiles.yaml``).
    * Resolve a model id -> threshold profile via ``min(fraction*window, abs_cap)``,
      normalizing harness/snapshot id variants before falling back (see
      :func:`resolve_threshold`).
    * Read context occupancy from the statusLine-written sidecar, or fall back to
      a transcript-token estimate (reusing ``scripts/ingest_token_usage.py``).
    * Decide whether to inject a soft/hard wrap-up nudge, debounced per session.
    * Build the (validated, shell-safe) auto-launch continuation command.
    * Enforce handoff-artifact retention.

Security invariants (ADR-0018, security spec-review):
    * ``session_id`` is allowlist-validated before it touches any path.
    * The continuation command is a discrete argv list for ``shell=False`` and its
      handoff path is canonicalized to live inside ``HANDOFF_DIR``.
    * Only numeric ``usage.*`` fields and ``model`` are read from a transcript;
      message/tool string content never reaches an injected nudge.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from scripts.ingest_token_usage import (
    MessageRecord,
    _parse_message_line,
    discover_session_dirs,
    parse_session_dir,
)

# ---------------------------------------------------------------------------
# Constants and paths.
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "model_context_profiles.yaml"
DEFAULT_STATE_DIR = PROJECT_ROOT / ".claude" / "hooks" / ".state"
HANDOFF_DIR = PROJECT_ROOT / "docs" / "handoff"

# Operational fallbacks, used when the config omits the `settings:` block.
DEFAULT_SIDECAR_FRESHNESS_SECONDS = 300
DEFAULT_HANDOFF_RETENTION_CAP = 5
DEFAULT_MAX_AUTO_LAUNCH_DEPTH = 1

# A session id must be a short, filesystem-safe token before it is interpolated
# into any path or filename (security spec-review B-SEC-1 / A-SEC-1).
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Last-resort profile if the config file is missing/unreadable — the most
# conservative numbers, so we wrap up early rather than never.
_HARDCODED_PROFILE = {
    "context_window": 200000,
    "soft_wrapup_fraction": 0.50,
    "hard_wrapup_fraction": 0.65,
    "soft_abs_cap_tokens": 130000,
    "hard_abs_cap_tokens": 160000,
    "auto_compact_fraction": 0.83,
}
_HARDCODED_DEFAULT_PROFILE_NAME = "haiku_200k"


# ---------------------------------------------------------------------------
# Data structures.
# ---------------------------------------------------------------------------


#: The three ways a model id can arrive at a profile. ``exact`` = the id is a key
#: in the config's ``models:`` map. ``normalized`` = a suffix-stripped form of the
#: id is a key (see :func:`_resolution_candidates`). ``default`` = nothing matched
#: and the conservative ``defaults.profile`` floor was used.
RESOLUTION_EXACT = "exact"
RESOLUTION_NORMALIZED = "normalized"
RESOLUTION_DEFAULT = "default"


@dataclass(frozen=True)
class ThresholdProfile:
    """Resolved wrap-up thresholds for a specific model.

    Attributes:
        profile_name: The profile key the model resolved to (e.g. ``opus_1m``).
        context_window: The model's advertised context window, in tokens.
        soft_tok: Effective soft threshold = ``min(soft_fraction*window, soft_cap)``.
        hard_tok: Effective hard threshold = ``min(hard_fraction*window, hard_cap)``.
        auto_compact_tok: Harness auto-compaction backstop, in tokens (informational).
        model: The model id this was resolved for, or ``None``.
        matched: ``True`` if ``model`` reached a profile deliberately (exactly OR via
            normalization); ``False`` if it fell back to the conservative default.
            This is the operator-facing "chosen vs defaulted" bit and its meaning is
            unchanged from ADR-0018.
        resolution: Which of the three routes was taken — ``"exact"``,
            ``"normalized"``, or ``"default"``. This is the third state ``matched``
            cannot express, and is what distinguishes "the config names this model"
            from "we inferred it from a variant suffix".
        resolved_model_id: The ``models:`` key that was actually hit (equal to
            ``model`` for an exact match, the stripped base id for a normalized
            match, ``None`` when defaulted).

    Invariant maintained by :func:`resolve_threshold`:
    ``matched == (resolution != RESOLUTION_DEFAULT)``. The two new fields carry
    defaults ONLY so that existing positional construction keeps working; they are
    purely informational and never influence a threshold, so their default value
    has no fail-safe consequence.
    """

    profile_name: str
    context_window: int
    soft_tok: int
    hard_tok: int
    auto_compact_tok: int
    model: str | None
    matched: bool
    resolution: str = RESOLUTION_EXACT
    resolved_model_id: str | None = None


@dataclass(frozen=True)
class Occupancy:
    """A point-in-time context-occupancy reading.

    Attributes:
        used_tokens: Estimated tokens currently resident in the context window.
        used_percentage: ``used_tokens`` as a percentage of ``window`` (0-100+).
        window: The context window size used for the percentage, in tokens.
        source: ``"statusline"`` (authoritative) or ``"transcript-estimate"``.
        model: The model id, or ``None`` if unknown.
    """

    used_tokens: int
    used_percentage: float
    window: int
    source: str
    model: str | None


# ---------------------------------------------------------------------------
# Config loading (cached on path + mtime so statusLine renders stay cheap).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _load_config_cached(path_str: str, _mtime: float) -> dict:
    """Parse the YAML config; cached by path and mtime. Never raises."""
    try:
        with open(path_str, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_config(config_path: Path | None = None) -> dict:
    """Load the context-profiles config, returning ``{}`` if unavailable.

    Args:
        config_path: Override for the config location (defaults to
            ``config/model_context_profiles.yaml``).

    Returns:
        The parsed config mapping, or an empty dict on any failure.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    return _load_config_cached(str(path), mtime)


def get_settings(config: dict | None = None) -> dict:
    """Return operational tunables with fallbacks to module defaults.

    Args:
        config: A pre-loaded config mapping, or ``None`` to load it.

    Returns:
        Dict with keys ``sidecar_freshness_seconds``, ``handoff_retention_cap``,
        and ``max_auto_launch_depth``.
    """
    config = load_config() if config is None else config
    settings = config.get("settings") if isinstance(config.get("settings"), dict) else {}
    return {
        "sidecar_freshness_seconds": _as_int(
            settings.get("sidecar_freshness_seconds"), DEFAULT_SIDECAR_FRESHNESS_SECONDS
        ),
        "handoff_retention_cap": _as_int(
            settings.get("handoff_retention_cap"), DEFAULT_HANDOFF_RETENTION_CAP
        ),
        "max_auto_launch_depth": _as_int(
            settings.get("max_auto_launch_depth"), DEFAULT_MAX_AUTO_LAUNCH_DEPTH
        ),
    }


def _as_int(value: object, fallback: int) -> int:
    """Coerce ``value`` to ``int``, returning ``fallback`` on failure."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    return fallback


# ---------------------------------------------------------------------------
# Threshold resolution.
# ---------------------------------------------------------------------------

# A harness-emitted context-window variant suffix, e.g. "claude-opus-5[1m]".
_BRACKET_SUFFIX_RE = re.compile(r"^(?P<base>.+?)\[(?P<tag>[^\[\]]*)\]$")
# A date-pinned snapshot suffix, e.g. "claude-opus-5-20260601". Exactly 8 digits.
_DATE_SUFFIX_RE = re.compile(r"^(?P<base>.+?)-\d{8}$")
# A variant tag that advertises a window size, e.g. "1m" -> 1_000_000, "200k" -> 200_000.
_WINDOW_TAG_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[kKmM])$")


def _parse_window_tag(tag: str) -> int | None:
    """Return the token count a variant tag advertises, or ``None`` if unparseable.

    ``"1m"`` -> ``1_000_000``; ``"200k"`` -> ``200_000``. Anything we cannot read as
    a window size returns ``None``, which the caller treats as "refuse to normalize"
    (an unknown variant could denote a *smaller* window, and guessing permissively is
    the one failure direction this module must not take).
    """
    match = _WINDOW_TAG_RE.match(tag.strip())
    if match is None:
        return None
    scale = 1_000_000 if match.group("unit").lower() == "m" else 1_000
    return int(match.group("value")) * scale


def _resolution_candidates(model: str) -> list[tuple[str, int | None]]:
    """Ordered ``(candidate_id, window_hint)`` fallbacks to try AFTER the exact id.

    Two — and only two — suffix forms are stripped, most-specific first:

    1. A bracketed context-window variant (``claude-opus-5[1m]`` -> ``claude-opus-5``),
       carrying the tag's advertised window as a hint the caller uses as a guard.
    2. A date-pinned snapshot (``claude-opus-5-20260601`` -> ``claude-opus-5``). Both
       strips compose, so ``claude-opus-5-20260601[1m]`` yields both intermediate forms.

    A version segment is deliberately NEVER stripped: the config maps
    ``claude-sonnet-4-5`` to a 200K profile and ``claude-sonnet-4-6`` to a 1M one, so
    collapsing a minor version would cross window classes and could pick the
    permissive side. An unparseable bracket tag aborts normalization entirely
    (returns ``[]``) rather than risk widening the window on a guess.
    """
    candidates: list[tuple[str, int | None]] = []
    seen = {model}
    base = model
    window_hint: int | None = None

    bracket = _BRACKET_SUFFIX_RE.match(base)
    if bracket is not None:
        window_hint = _parse_window_tag(bracket.group("tag"))
        if window_hint is None:
            return []
        base = bracket.group("base")
        if base and base not in seen:
            candidates.append((base, window_hint))
            seen.add(base)

    dated = _DATE_SUFFIX_RE.match(base)
    if dated is not None:
        undated = dated.group("base")
        if undated and undated not in seen:
            candidates.append((undated, window_hint))
    return candidates


def _select_profile_name(
    model: str | None, models: dict, profiles: dict, default_name: str
) -> tuple[str, str, str | None]:
    """Pick a profile name for ``model``; return ``(name, resolution, matched_key)``.

    The ladder is exact -> normalized -> default, so a currently-resolving id can
    never change behaviour. A normalized hit is accepted only when the variant tag
    does not advertise a window *smaller* than the base model's profile window;
    otherwise we fail safe to the conservative default rather than hand a 200K
    session a 1M model's headroom.
    """
    if not model:
        return default_name, RESOLUTION_DEFAULT, None
    if model in models:
        return models[model], RESOLUTION_EXACT, model
    for candidate, window_hint in _resolution_candidates(model):
        name = models.get(candidate)
        if name is None:
            continue
        if window_hint is not None:
            profile_window = _as_int((profiles.get(name) or {}).get("context_window"), 0)
            if profile_window and window_hint < profile_window:
                break
        return name, RESOLUTION_NORMALIZED, candidate
    return default_name, RESOLUTION_DEFAULT, None


def resolve_threshold(model: str | None, config: dict | None = None) -> ThresholdProfile:
    """Resolve a model id to its effective soft/hard wrap-up thresholds.

    Effective thresholds use ``min(fraction*window, absolute_cap)`` so the
    percentage binds on small windows and the absolute cap binds on 1M windows.
    An unknown/absent model falls back to the most conservative profile, so its
    thresholds are <= every known model's.

    The numbers this returns are a **judgment, not a measurement**. Nothing in
    this repository answers "at what occupancy does output quality degrade?", so
    the caps encode a reading of third-party research plus a mechanical
    constraint (leave room to write the handoff before the harness compacts).
    The reasoning is recorded in the config's ``CAP RECALIBRATION`` block and is
    bound to this function by
    ``tests/test_context_sensor.py::TestCapRationaleIsRecorded`` and
    ``::TestHandoffHeadroomInvariant`` — read those before changing a cap.

    Resolution is a three-rung ladder — exact id, then a normalized id, then the
    default (see :func:`_select_profile_name`). Normalization exists because the
    harness emits ids the config's ``models:`` map does not literally contain
    (``claude-opus-5[1m]``, ``claude-opus-5-20260601``); before it, every such
    session was measured against the 200K floor while really holding a 1M window.
    Exact match is tried first, so no id that resolves today can change.

    Scope of the fail-safe guarantee — read this before adding a ``models:`` key.
    What the *mechanism* guarantees is narrow: normalization only ever tries
    *shorter* candidate ids and still requires an exact hit in ``models:``, so an
    id matching no key reaches the conservative default exactly as before. It does
    NOT make the answer safe; it makes the answer *the config's answer*. And it
    changes what a key means: an entry that used to answer for one literal id now
    answers for that id's whole family (``claude-opus-4`` also answers for
    ``claude-opus-4-20250514``). A key overstating a model's window therefore
    overstates it for N ids, and ``hard_tok`` — computed as a fraction of that
    window — can land above ``auto_compact_fraction * real window``, i.e. we would
    fire the handoff only after the harness had already compacted the thread.
    The config carries the matching obligation (VERIFIED WINDOWS ONLY) and
    ``tests/test_context_sensor.py::TestConfigKeyWindowsAreVerified`` enforces it;
    that test, not this docstring, is what keeps the direction fail-safe.

    Args:
        model: Full model id (e.g. ``claude-opus-4-7``) or ``None``.
        config: Pre-loaded config mapping, or ``None`` to load it.

    Returns:
        A populated :class:`ThresholdProfile`.
    """
    config = load_config() if config is None else config
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    models = config.get("models") if isinstance(config.get("models"), dict) else {}
    default_name = (config.get("defaults") or {}).get("profile", _HARDCODED_DEFAULT_PROFILE_NAME)

    profile_name, resolution, resolved_id = _select_profile_name(
        model, models, profiles, default_name
    )
    if not profiles.get(profile_name):
        # The map named a profile the config does not define. Report the fallback
        # honestly rather than stamping a tier whose numbers we did not use.
        profile_name, resolution, resolved_id = default_name, RESOLUTION_DEFAULT, None
    profile = profiles.get(profile_name) or profiles.get(default_name) or _HARDCODED_PROFILE
    if profile is _HARDCODED_PROFILE:
        profile_name = _HARDCODED_DEFAULT_PROFILE_NAME
    matched = resolution != RESOLUTION_DEFAULT

    window = _as_int(profile.get("context_window"), _HARDCODED_PROFILE["context_window"])
    soft = min(
        int(float(profile.get("soft_wrapup_fraction", 0.5)) * window),
        _as_int(profile.get("soft_abs_cap_tokens"), window),
    )
    hard = min(
        int(float(profile.get("hard_wrapup_fraction", 0.65)) * window),
        _as_int(profile.get("hard_abs_cap_tokens"), window),
    )
    auto = int(float(profile.get("auto_compact_fraction", 0.83)) * window)
    return ThresholdProfile(
        profile_name, window, soft, hard, auto, model, matched, resolution, resolved_id
    )


# ---------------------------------------------------------------------------
# Session-id validation and state paths.
# ---------------------------------------------------------------------------


def is_valid_session_id(session_id: object) -> bool:
    """Return ``True`` iff ``session_id`` is a safe ``[A-Za-z0-9_-]{1,64}`` token."""
    return isinstance(session_id, str) and bool(SESSION_ID_RE.match(session_id))


def sidecar_path(session_id: str, state_dir: Path | None = None) -> Path | None:
    """Return the sidecar path for a session, or ``None`` if the id is invalid."""
    if not is_valid_session_id(session_id):
        return None
    base = state_dir or DEFAULT_STATE_DIR
    return base / f"context-occupancy.{session_id}.json"


def _flag_path(session_id: str, kind: str, state_dir: Path | None = None) -> Path | None:
    """Return the debounce-flag path for ``kind`` in {soft, hard}, or ``None``."""
    if not is_valid_session_id(session_id):
        return None
    name = "context-guard-armed" if kind == "soft" else "context-guard-hard"
    base = state_dir or DEFAULT_STATE_DIR
    return base / f"{name}.{session_id}"


# ---------------------------------------------------------------------------
# Sidecar read / write.
# ---------------------------------------------------------------------------


def write_sidecar_atomic(record: dict, state_dir: Path | None = None) -> Path | None:
    """Atomically write the occupancy sidecar for ``record['session_id']``.

    Uses write-temp-then-``os.replace`` so concurrent readers never see a partial
    file. Returns the written path, or ``None`` if the session id is invalid or
    the write failed.
    """
    session_id = record.get("session_id")
    if not is_valid_session_id(session_id):
        return None
    path = sidecar_path(session_id, state_dir)
    if path is None:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(record), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def read_sidecar(
    session_id: str,
    state_dir: Path | None = None,
    *,
    now: float | None = None,
    freshness_seconds: int | None = None,
) -> dict | None:
    """Read a fresh occupancy sidecar, or ``None`` if missing/stale/invalid.

    A sidecar whose ``written_at_epoch`` is older than ``freshness_seconds`` is
    treated as stale (callers then fall back to the transcript estimate).
    """
    path = sidecar_path(session_id, state_dir)
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    freshness = (
        get_settings()["sidecar_freshness_seconds"]
        if freshness_seconds is None
        else freshness_seconds
    )
    written = data.get("written_at_epoch")
    now = time.time() if now is None else now
    if not isinstance(written, int | float) or (now - written) > freshness:
        return None
    return data


def window_disagreement(occ: Occupancy, profile: ThresholdProfile) -> bool:
    """Return ``True`` when the harness-reported window differs from the profile's.

    This is the cheap cross-check that would have caught the ADR-0031 defect while
    it was live: the statusLine payload reported a 1,000,000-token window while the
    resolved ``haiku_200k`` profile assumed 200,000, and nothing compared the two.
    A mismatch in either direction is worth surfacing — too small means we are
    taxing the session, too large means we are being dangerously permissive.

    Only the ``statusline`` source is checked; the transcript-estimate path derives
    ``occ.window`` from the profile itself, so a comparison there is vacuous.
    """
    return (
        occ.source == "statusline"
        and occ.window > 0
        and profile.context_window > 0
        and occ.window != profile.context_window
    )


def build_sidecar_record(
    occ: Occupancy, profile: ThresholdProfile, session_id: str, *, now: float | None = None
) -> dict:
    """Assemble the JSON-serializable sidecar record for an occupancy reading.

    Carries the resolution provenance (``resolution`` / ``matched`` /
    ``resolved_model_id``) and the ``window_mismatch`` cross-check alongside the
    numbers, so a human reading a sidecar off disk can tell whether the tier was
    chosen for this model or silently defaulted.
    """
    return {
        "session_id": session_id,
        "used_tokens": occ.used_tokens,
        "used_percentage": round(occ.used_percentage, 2),
        "window": occ.window,
        "model": occ.model,
        "tier": profile.profile_name,
        "soft_tok": profile.soft_tok,
        "hard_tok": profile.hard_tok,
        "source": occ.source,
        "resolution": profile.resolution,
        "matched": profile.matched,
        "resolved_model_id": profile.resolved_model_id,
        "profile_window": profile.context_window,
        "window_mismatch": window_disagreement(occ, profile),
        "written_at_epoch": time.time() if now is None else now,
    }


# ---------------------------------------------------------------------------
# Occupancy from statusLine JSON.
# ---------------------------------------------------------------------------


def _extract_model(payload: dict) -> str | None:
    """Pull a model id from a statusLine payload (str or ``{"id": ...}``)."""
    model = payload.get("model")
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        mid = model.get("id")
        return mid if isinstance(mid, str) else None
    return None


def occupancy_from_statusline(payload: dict) -> Occupancy | None:
    """Parse a statusLine JSON payload into an :class:`Occupancy`, or ``None``.

    Returns ``None`` (graceful degrade) when the ``context_window`` block or the
    fields needed to compute occupancy are absent — never raises.
    """
    if not isinstance(payload, dict):
        return None
    cw = payload.get("context_window")
    if not isinstance(cw, dict):
        return None
    window = _as_int(cw.get("context_window_size"), 0)
    if window <= 0:
        return None
    used_pct = cw.get("used_percentage")
    total_input = cw.get("total_input_tokens")
    if isinstance(used_pct, int | float) and not isinstance(used_pct, bool):
        used_tokens = int(used_pct / 100 * window)
        pct = float(used_pct)
    elif isinstance(total_input, int) and not isinstance(total_input, bool):
        used_tokens = total_input
        pct = used_tokens / window * 100
    else:
        return None
    return Occupancy(used_tokens, pct, window, "statusline", _extract_model(payload))


# ---------------------------------------------------------------------------
# Occupancy from transcript (fallback).
# ---------------------------------------------------------------------------


def _iter_records_from_file(path: Path) -> list[MessageRecord]:
    """Parse a single transcript JSONL file directly (no projects-root guard).

    Reuses ``_parse_message_line`` so a fixture file outside ``~/.claude`` is
    parseable in tests. Malformed lines are skipped; an unreadable file yields
    an empty list.
    """
    records: list[MessageRecord] = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = _parse_message_line(line, path)
                if record is not None:
                    records.append(record)
    except OSError:
        return []
    return records


def _latest_usage_record(records: list[MessageRecord]) -> MessageRecord | None:
    """Return the newest record carrying any token-usage field, else ``None``."""
    usable = [
        r
        for r in records
        if r.input_tokens is not None
        or r.cache_read_tokens is not None
        or r.cache_create_tokens is not None
    ]
    if not usable:
        return None
    return max(usable, key=lambda r: r.timestamp)


def estimate_from_transcript(
    transcript_path: Path | None = None,
    *,
    project_root: Path | None = None,
    config: dict | None = None,
    records: list[MessageRecord] | None = None,
) -> Occupancy | None:
    """Estimate occupancy from the most recent transcript message, or ``None``.

    Resident context is approximated as ``input + cache_read + cache_create``
    tokens of the newest assistant message. This is lower-confidence than the
    statusLine value (cache/sliding-window effects), hence the ``source`` stamp.

    Args:
        transcript_path: A specific transcript ``.jsonl`` to parse (used in tests
            and from the hook payload's ``transcript_path``).
        project_root: Discover transcripts for this project (production path).
        config: Pre-loaded config, for threshold/window resolution.
        records: Pre-parsed records (test seam); takes precedence.

    Returns:
        An :class:`Occupancy` stamped ``transcript-estimate``, or ``None`` if no
        usable record exists.
    """
    if records is not None:
        recs = records
    elif transcript_path is not None:
        recs = _iter_records_from_file(Path(transcript_path))
    else:
        recs = []
        for session_path in discover_session_dirs(project_root or PROJECT_ROOT):
            recs.extend(parse_session_dir(session_path))
    latest = _latest_usage_record(recs)
    if latest is None:
        return None
    used = sum(
        v
        for v in (latest.input_tokens, latest.cache_read_tokens, latest.cache_create_tokens)
        if v is not None
    )
    profile = resolve_threshold(latest.model, config)
    window = profile.context_window
    pct = (used / window * 100) if window else 0.0
    return Occupancy(used, pct, window, "transcript-estimate", latest.model)


# ---------------------------------------------------------------------------
# statusLine entry point (writer + display).
# ---------------------------------------------------------------------------


def process_statusline(
    payload: dict, *, state_dir: Path | None = None, config: dict | None = None
) -> str:
    """Handle one statusLine invocation: write the sidecar and return a display line.

    Writes the occupancy sidecar as a side effect (the real job); the returned
    string is what the terminal status line shows. Never raises.
    """
    occ = occupancy_from_statusline(payload)
    if occ is None:
        return "ctx ?"
    profile = resolve_threshold(occ.model, config)
    session_id = payload.get("session_id")
    if is_valid_session_id(session_id):
        write_sidecar_atomic(build_sidecar_record(occ, profile, session_id), state_dir)
    # ASCII-only display: statusLine prints to the raw terminal, which may use a
    # non-UTF-8 codec (e.g. Windows cp1252) that cannot encode emoji.
    warn = " [wrap-up]" if occ.used_tokens >= profile.soft_tok else ""
    return (
        f"ctx {occ.used_percentage:.0f}% | {occ.used_tokens // 1000}K/{occ.window // 1000}K | "
        f"{_tier_token(occ, profile)} | soft {profile.soft_tok // 1000}K hard "
        f"{profile.hard_tok // 1000}K{warn}"
    )


def _tier_token(occ: Occupancy, profile: ThresholdProfile) -> str:
    """Render the tier name with a one-char ASCII provenance marker.

    ``opus_1m`` (exact) · ``opus_1m~`` (normalized) · ``haiku_200k?`` (defaulted) ·
    ``haiku_200k!`` (the window cross-check disagrees — the loudest state, and the
    one that was invisible while ADR-0031's defect was live). Markers are ASCII so
    the cp1252 statusLine regression test keeps holding.
    """
    if window_disagreement(occ, profile):
        return f"{profile.profile_name}!"
    if profile.resolution == RESOLUTION_DEFAULT:
        return f"{profile.profile_name}?"
    if profile.resolution == RESOLUTION_NORMALIZED:
        return f"{profile.profile_name}~"
    return profile.profile_name


# ---------------------------------------------------------------------------
# Guard entry point (nudge decision + debounce).
# ---------------------------------------------------------------------------


def classify_level(occ: Occupancy, profile: ThresholdProfile) -> str | None:
    """Return ``"hard"``, ``"soft"``, or ``None`` for the occupancy vs thresholds.

    Comparison is on integer tokens, inclusive (``>=``).
    """
    if occ.used_tokens >= profile.hard_tok:
        return "hard"
    if occ.used_tokens >= profile.soft_tok:
        return "soft"
    return None


def _resolve_occupancy(
    payload: dict, state_dir: Path | None, project_root: Path | None = None
) -> Occupancy | None:
    """Read occupancy for the guard: fresh sidecar first, else transcript estimate.

    ``project_root`` is injectable so the final discover-transcripts fallback can
    be exercised in tests without touching the real ``~/.claude/projects``.
    """
    session_id = payload.get("session_id")
    if is_valid_session_id(session_id):
        sidecar = read_sidecar(session_id, state_dir)
        if sidecar is not None:
            return Occupancy(
                used_tokens=_as_int(sidecar.get("used_tokens"), 0),
                used_percentage=float(sidecar.get("used_percentage", 0.0) or 0.0),
                window=_as_int(sidecar.get("window"), 0),
                source=str(sidecar.get("source", "statusline")),
                model=sidecar.get("model") if isinstance(sidecar.get("model"), str) else None,
            )
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        candidate = Path(transcript)
        # Only accept a transcript path that looks like a Claude Code transcript
        # (.jsonl). The hook payload is harness-controlled, but validating the
        # suffix keeps a stray/crafted value from steering the read (security review).
        if candidate.suffix == ".jsonl":
            return estimate_from_transcript(candidate)
    return estimate_from_transcript(project_root=project_root or PROJECT_ROOT)


def _nudge_text(level: str) -> str:
    """Build the model-facing nudge. FIXED TEXT — no numbers, ever.

    **This function must never interpolate a value.** Not the occupancy, not the
    percentage, not the threshold, not the window, not the profile name. It is a
    constant lookup and it is deliberately shaped so that adding a number requires
    changing its signature.

    Why (ADR-0033, amendment 2026-08-08). The Anthropic reference names surfacing a
    remaining-token count to the model as a *cause* of the failure this machinery is
    supposed to prevent, twice: "surfacing remaining-token counts to the model can
    cause premature wrap-up behavior; avoid showing them where possible", and, on
    long-running agents, "it can worry about running out of context — suggesting a
    new session or trimming its own work — most often when the harness surfaces a
    remaining-token countdown. Avoid showing explicit context-budget counts."
    This hook was doing exactly that on every single prompt, e.g.
    "Context HARD wrap-up: ~651,312 tokens (~65% of the opus_1m window; hard
    threshold 400,000)" — three budget figures, injected into the model's context.

    What was kept and what was dropped, deliberately:
      * DROPPED — every figure, and the "before context degrades" / "before quality
        degrades" clauses. There is no documented quality cliff (see the config's
        CAP RECALIBRATION block); those clauses asserted one.
      * KEPT — the checkpoint instruction itself, at both levels. Deleting the nudge
        was the other option on the table and was rejected: the mechanism exists so a
        session checkpoints before it dies, and losing the thread is the worse
        failure. The documentation objects to the *countdown*, not to being told to
        checkpoint, so the countdown is what goes.
      * ADDED — a reassurance clause, which is the reference's own recommended
        mitigation for context anxiety: without one, a bare "wrap up now" still
        reads as scarcity pressure. See the constraint on its wording below.

    **THE CONSTRAINT THAT SHAPES THE WORDING: this text is profile-independent, so
    it may only assert what is true at the TIGHTEST profile.** The first version of
    this amendment said "Context remaining is ample", justified by opus_1m leaving
    430000 tokens (~17x the handoff reserve) above its hard cap. That justification
    only ever surveyed the 1M class. Measured 2026-08-08 by piping a real payload
    through the hooks, a `sonnet_200k` session at 141K/200K received the identical
    sentence — with 26000 tokens left before the harness auto-compacts, i.e. 1.04x
    the reserve and 1.42x the measured cost of one handoff. "Ample", plus "do not
    trim your work ... on account of context", told the profile closest to the
    mechanical floor the opposite of its situation. That is the same failure this
    amendment was convened to fix, mirrored: the old text over-stated scarcity to
    every session, and the fix under-stated it to every session.

    What replaced it is the claim the system actually guarantees everywhere: room to
    write the handoff **is reserved** at the threshold. That holds for all four
    profiles by construction — ``TestHandoffHeadroomInvariant`` requires
    ``auto_compact_tok - hard_tok >= 25000`` and the measured handoff cost sits under
    that reserve — so the sentence is enforced rather than asserted. It carries the
    same anti-anxiety payload (do not rush, do not truncate, do not bail to a new
    session) without claiming anything about how full the window is.

    The developer-facing signal is unchanged and still carries every number: it is
    the status line (:func:`process_statusline`), which prints to the terminal and is
    never injected into the model's context.

    Enforced by ``tests/test_context_sensor.py::TestModelFacingNudgeCarriesNoFigures``,
    which asserts the emitted text is digit-free across a sweep of occupancies, that
    the status line still carries digits for the same readings, and that the
    reassurance clause is true on the tightest profile the config defines.
    """
    if level == "hard":
        return (
            "Checkpoint due (HARD). Stop starting new work. Run the "
            "`wrapping-up-sessions` skill or `/handoff` now: checkpoint the current "
            "step, update BUILD_STATUS.md, and write the handoff so the thread "
            "survives if this session ends. Room to write it in full is reserved at "
            "this threshold, so write it properly rather than rushing: wrap up "
            "because the checkpoint is due, not because you have run out of room. "
            "Do not trim your work, shorten your answers, or suggest a new session on "
            "account of context."
        )
    return (
        "Checkpoint due (soft). Finish the current atomic step, then run the "
        "`wrapping-up-sessions` skill / `/handoff` to write a handoff so the thread "
        "survives if this session ends. Room to write it in full is reserved at this "
        "threshold, so write it properly: do not trim your work, shorten your "
        "answers, or suggest a new session on account of context."
    )


def evaluate_guard(
    payload: dict,
    *,
    state_dir: Path | None = None,
    config: dict | None = None,
    project_root: Path | None = None,
) -> dict:
    """Decide whether to inject a wrap-up nudge for a UserPromptSubmit turn.

    Reads occupancy (sidecar or transcript), classifies it against the model's
    thresholds, and applies one-shot debounce: a level fires once per crossing
    (a ``.state`` flag is written) and re-arms only when occupancy drops back
    below soft (the flags are cleared). Below soft, returns ``{}`` (silence).

    ``state_dir``, ``config``, and ``project_root`` are injectable for testing.

    The occupancy and thresholds decide **whether** to speak; they never appear in
    **what** is said. The injected text is fixed and figure-free (see
    :func:`_nudge_text`) because surfacing a remaining-token count to the model is
    itself a documented cause of premature wrap-up. The numbers stay on the
    developer-facing status line.

    Returns:
        ``{"additionalContext": <str>}`` to inject, or ``{}`` for silence.
    """
    occ = _resolve_occupancy(payload, state_dir, project_root)
    if occ is None:
        return {}
    session_id = payload.get("session_id")
    profile = resolve_threshold(occ.model, config)
    level = classify_level(occ, profile)

    soft_flag = (
        _flag_path(session_id, "soft", state_dir) if is_valid_session_id(session_id) else None
    )
    hard_flag = (
        _flag_path(session_id, "hard", state_dir) if is_valid_session_id(session_id) else None
    )

    if level is None:
        _clear_flag(soft_flag)
        _clear_flag(hard_flag)
        return {}
    if level == "hard":
        if _flag_exists(hard_flag):
            return {}
        _set_flag(soft_flag)
        _set_flag(hard_flag)
        return {"additionalContext": _nudge_text("hard")}
    # level == "soft"
    if _flag_exists(soft_flag):
        return {}
    _set_flag(soft_flag)
    return {"additionalContext": _nudge_text("soft")}


def _flag_exists(path: Path | None) -> bool:
    """Return ``True`` if the flag file exists."""
    return path is not None and path.exists()


def _set_flag(path: Path | None) -> None:
    """Create the flag file (best effort)."""
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def _clear_flag(path: Path | None) -> None:
    """Delete the flag file if present (best effort)."""
    if path is None or not path.exists():
        return
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Auto-launch continuation command (validated, shell-safe).
# ---------------------------------------------------------------------------


def build_launch_command(
    handoff_path: Path,
    *,
    auth: bool,
    allow_launch: bool,
    depth: int,
    max_depth: int | None = None,
    handoff_dir: Path | None = None,
) -> list[str] | None:
    """Build the continuation ``claude --print`` argv, or ``None`` if not allowed.

    Returns ``None`` (no launch) when the session is not authorized, the explicit
    ``ALLOW_AUTO_LAUNCH_SESSION`` opt-in is absent, the spawn-chain depth cap is
    reached, or the handoff path escapes ``HANDOFF_DIR``. The result is a discrete
    argv list intended for ``subprocess.run(..., shell=False)``; the validated
    path is the only variable element and no untrusted text is interpolated.

    Args:
        handoff_path: Path to the handoff artifact to continue from.
        auth: Whether the Autonomous Execution Authorization is active.
        allow_launch: Whether the separate ``ALLOW_AUTO_LAUNCH_SESSION`` opt-in is set.
        depth: The current spawn-chain depth (0 for a human-started session).
        max_depth: Override for the depth cap (defaults to config/module value).
        handoff_dir: Override for the allowed handoff directory.

    Returns:
        The argv list, or ``None`` when a launch must not happen.
    """
    if not (auth and allow_launch):
        return None
    cap = get_settings()["max_auto_launch_depth"] if max_depth is None else max_depth
    if depth >= cap:
        return None
    allowed_dir = (handoff_dir or HANDOFF_DIR).resolve()
    try:
        resolved = handoff_path.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(allowed_dir):
        return None
    # The handoff path is canonicalized and contained within HANDOFF_DIR (above), so
    # interpolating it into the FIXED prompt is injection-safe: the command runs with
    # shell=False (no shell parsing) and the only variable element is the validated
    # path — no untrusted text is included. A single-positional prompt is what
    # `claude --print` accepts (a separate trailing path arg is not honored by the CLI;
    # security review B-SEC-1's threat — shell injection — is closed by shell=False
    # regardless of whether the path is its own argv element). Verify the exact
    # invocation against the installed CLI at first real use (ADR-0018 limitation).
    prompt = (
        f"Read the session handoff at {resolved} and continue the work it describes. "
        "You inherit the full CLAUDE.md and rules: run /review before any commit, do not "
        "bypass capture, and do not push or auto-merge."
    )
    return ["claude", "--print", prompt]


# ---------------------------------------------------------------------------
# Handoff retention.
# ---------------------------------------------------------------------------


def enforce_retention(handoff_dir: Path | None = None, cap: int | None = None) -> list[Path]:
    """Keep only the ``cap`` most-recent ``HANDOFF-*.md`` files (FIFO eviction).

    Args:
        handoff_dir: Directory of handoff artifacts (defaults to ``docs/handoff``).
        cap: Maximum files to keep (defaults to the config/module value).

    Returns:
        The list of removed paths (empty if nothing was evicted).
    """
    directory = handoff_dir or HANDOFF_DIR
    keep = get_settings()["handoff_retention_cap"] if cap is None else cap
    if not directory.exists():
        return []
    # Filename timestamps (HANDOFF-YYYYMMDD-HHMMSS.md) sort chronologically.
    files = sorted(directory.glob("HANDOFF-*.md"), key=lambda p: p.name)
    removed: list[Path] = []
    while len(files) > keep:
        oldest = files.pop(0)
        try:
            oldest.unlink()
            removed.append(oldest)
        except OSError:
            pass
    return removed
