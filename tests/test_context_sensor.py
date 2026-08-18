"""Tests for src/context_sensor.py (ADR-0018, model-aware session wrap-up).

Covers the threshold model (min(fraction*window, abs_cap) + conservative floor),
statusLine parsing + graceful degrade, session-id allowlisting, sidecar
read/write + freshness boundary, transcript-estimate fallback, the debounced
guard state machine, handoff retention, and the (no-spawn) auto-launch command
builder. Every path is exercised with injected config / state_dir / project_root
so no test touches the real ``~/.claude`` or the system clock.
"""

from __future__ import annotations

import inspect
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ingest_token_usage import MessageRecord
from src.context_sensor import (
    DEFAULT_CONFIG_PATH,
    PROJECT_ROOT,
    RESOLUTION_DEFAULT,
    RESOLUTION_EXACT,
    RESOLUTION_NORMALIZED,
    Occupancy,
    ThresholdProfile,
    _nudge_text,
    build_launch_command,
    build_sidecar_record,
    classify_level,
    enforce_retention,
    estimate_from_transcript,
    evaluate_guard,
    is_valid_session_id,
    load_config,
    occupancy_from_statusline,
    process_statusline,
    read_sidecar,
    resolve_threshold,
    sidecar_path,
    window_disagreement,
    write_sidecar_atomic,
)

# ---------------------------------------------------------------------------
# Fixtures / factories.
# ---------------------------------------------------------------------------


def _make_statusline_json(
    *,
    used_percentage: float | None = 14.0,
    window: int | None = 1_000_000,
    total_input_tokens: int | None = None,
    model: object = "claude-opus-4-7",
    session_id: str = "sess-abc_123",
) -> dict:
    """Pin the statusLine JSON shape this feature depends on (B-QA-6).

    Documents the exact fields the sensor reads, with sensible defaults so each
    test overrides only what it cares about.
    """
    cw: dict = {}
    if window is not None:
        cw["context_window_size"] = window
    if used_percentage is not None:
        cw["used_percentage"] = used_percentage
    if total_input_tokens is not None:
        cw["total_input_tokens"] = total_input_tokens
    payload: dict = {"context_window": cw, "session_id": session_id}
    if model is not None:
        payload["model"] = model
    return payload


def _make_record(
    *,
    input_tokens: int | None = 100,
    cache_read_tokens: int | None = 0,
    cache_create_tokens: int | None = 0,
    model: str | None = "claude-opus-4-7",
    ts: datetime | None = None,
) -> MessageRecord:
    """Construct a MessageRecord for transcript-estimate tests."""
    return MessageRecord(
        message_id="msg_x",
        timestamp=ts or datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
        model=model,
        input_tokens=input_tokens,
        output_tokens=10,
        cache_read_tokens=cache_read_tokens,
        cache_create_tokens=cache_create_tokens,
        source_file=Path("fixture.jsonl"),
    )


def _profile(name: str, *, window: int, fraction: float, cap: int) -> dict:
    """Build a single-profile synthetic config keyed by ``name``."""
    return {
        "profiles": {
            name: {
                "context_window": window,
                "soft_wrapup_fraction": fraction,
                "hard_wrapup_fraction": fraction,
                "soft_abs_cap_tokens": cap,
                "hard_abs_cap_tokens": cap,
                "auto_compact_fraction": 0.83,
            }
        },
        "models": {},
        "defaults": {"profile": name},
    }


# A small deterministic config: window 1000 -> soft 100, hard 200.
TINY_CONFIG: dict = {
    "profiles": {
        "tiny": {
            "context_window": 1000,
            "soft_wrapup_fraction": 0.10,
            "hard_wrapup_fraction": 0.20,
            "soft_abs_cap_tokens": 100,
            "hard_abs_cap_tokens": 200,
            "auto_compact_fraction": 0.83,
        }
    },
    "models": {},
    "defaults": {"profile": "tiny"},
    "settings": {
        "sidecar_freshness_seconds": 300,
        "handoff_retention_cap": 5,
        "max_auto_launch_depth": 1,
    },
}


def _write_sidecar(
    state_dir: Path, session_id: str, used_tokens: int, *, model: str = "tiny-model"
) -> None:
    """Write a fresh occupancy sidecar for the guard tests."""
    record = {
        "session_id": session_id,
        "used_tokens": used_tokens,
        "used_percentage": used_tokens / 10.0,
        "window": 1000,
        "model": model,
        "tier": "tiny",
        "soft_tok": 100,
        "hard_tok": 200,
        "source": "statusline",
        "written_at_epoch": time.time(),
    }
    write_sidecar_atomic(record, state_dir)


# ---------------------------------------------------------------------------
# AC-1: threshold resolution — min() crossover + conservative floor.
# ---------------------------------------------------------------------------


class TestResolveThreshold:
    def test_known_opus_uses_absolute_cap(self) -> None:
        prof = resolve_threshold("claude-opus-4-7")
        assert prof.profile_name == "opus_1m"
        # Recalibrated 2026-08-08 (was 140000 / 180000) — see the config's
        # CAP RECALIBRATION block, ADR-0033, and TestWrapupCapRecalibration below.
        # Read from the one table rather than re-typed, so a cap moves in exactly
        # one place in this file.
        assert (prof.soft_tok, prof.hard_tok) == _RECALIBRATED_CAPS["opus_1m"]
        assert prof.matched is True

    def test_fraction_governs_when_below_cap(self) -> None:
        # 0.5 * 200000 = 100000 < cap 130000 -> fraction governs.
        prof = resolve_threshold("m", _profile("p", window=200000, fraction=0.5, cap=130000))
        assert prof.soft_tok == 100000

    def test_cap_governs_when_below_fraction(self) -> None:
        # 0.55 * 1_000_000 = 550000 > cap 140000 -> cap governs.
        prof = resolve_threshold("m", _profile("p", window=1_000_000, fraction=0.55, cap=140000))
        assert prof.soft_tok == 140000

    def test_degenerate_fraction_equals_cap(self) -> None:
        # 0.5 * 200000 = 100000 == cap 100000 -> both equal.
        prof = resolve_threshold("m", _profile("p", window=200000, fraction=0.5, cap=100000))
        assert prof.soft_tok == 100000

    def test_unknown_model_falls_back_to_conservative_floor(self) -> None:
        cfg = load_config()
        unknown = resolve_threshold("totally-unknown-xyz", cfg)
        assert unknown.matched is False
        known = ["claude-opus-4-7", "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-haiku-4-5"]
        for model in known:
            prof = resolve_threshold(model, cfg)
            assert unknown.soft_tok <= prof.soft_tok
            assert unknown.hard_tok <= prof.hard_tok

    def test_none_model_falls_back(self) -> None:
        prof = resolve_threshold(None)
        assert prof.matched is False

    def test_missing_config_uses_hardcoded_profile(self) -> None:
        prof = resolve_threshold("anything", {})
        assert prof.soft_tok > 0 and prof.hard_tok > prof.soft_tok


# ---------------------------------------------------------------------------
# Model-id normalization (ADR-0031 follow-on).
#
# The config's `models:` map is keyed by BASE ids, but the harness emits variant
# and snapshot forms. Before normalization, exact-string lookup sent every real
# frontier session to the haiku_200k floor: measured 2026-08-07,
# claude-fable-5[1m] -> soft 100000 against a 1000000-token window, and the one
# sidecar on disk recorded exactly that with nothing flagging it.
# ---------------------------------------------------------------------------

# Live-observed id forms -> the profile each must reach. Every one of these
# except the first resolved to haiku_200k/soft=100000 before this change.
_ONE_M_ID_FORMS = [
    ("claude-opus-5", "opus_1m", RESOLUTION_EXACT),
    ("claude-opus-5[1m]", "opus_1m", RESOLUTION_NORMALIZED),
    ("claude-fable-5[1m]", "opus_1m", RESOLUTION_NORMALIZED),
    ("claude-sonnet-5[1m]", "sonnet_1m", RESOLUTION_NORMALIZED),
    ("claude-opus-5-20260601", "opus_1m", RESOLUTION_NORMALIZED),
    ("claude-opus-5-20260601[1m]", "opus_1m", RESOLUTION_NORMALIZED),
]


class TestModelIdNormalization:
    @pytest.mark.regression
    @pytest.mark.parametrize(("model", "expected_profile", "expected_res"), _ONE_M_ID_FORMS)
    def test_live_id_forms_reach_the_1m_profile(
        self, model: str, expected_profile: str, expected_res: str
    ) -> None:
        # Regression (ADR-0031 follow-on): resolve_threshold did an exact-string
        # dict lookup, so a bracketed/date-suffixed id fell to the 200K floor.
        prof = resolve_threshold(model, load_config())
        assert prof.profile_name == expected_profile
        assert prof.context_window == 1_000_000
        assert prof.resolution == expected_res
        assert prof.matched is True
        # The specific number the old code produced for these ids.
        assert prof.soft_tok > 100000

    @pytest.mark.parametrize(("model", "expected_profile", "_res"), _ONE_M_ID_FORMS)
    def test_normalized_matches_its_base_id_exactly(
        self, model: str, expected_profile: str, _res: str
    ) -> None:
        # A normalized hit must be indistinguishable (numerically) from resolving
        # the base id directly — normalization picks the key, never new numbers.
        cfg = load_config()
        prof = resolve_threshold(model, cfg)
        base = resolve_threshold(prof.resolved_model_id, cfg)
        assert (prof.soft_tok, prof.hard_tok, prof.context_window) == (
            base.soft_tok,
            base.hard_tok,
            base.context_window,
        )
        assert base.profile_name == expected_profile

    def test_exact_match_still_wins_over_normalization(self) -> None:
        # An explicitly-listed variant key must pin its own profile, so an operator
        # can always override the inferred one. Here the bracketed id is listed
        # against the FLOOR while its base id maps to a 1M profile.
        cfg = {
            "profiles": load_config()["profiles"],
            "models": {"claude-opus-5": "opus_1m", "claude-opus-5[1m]": "haiku_200k"},
            "defaults": {"profile": "haiku_200k"},
        }
        prof = resolve_threshold("claude-opus-5[1m]", cfg)
        assert prof.resolution == RESOLUTION_EXACT
        assert prof.profile_name == "haiku_200k"

    # -- Fail-safe direction: these must NOT reach a permissive profile. --------

    @pytest.mark.parametrize(
        "model",
        [
            "totally-unknown-xyz",  # nothing like a known id
            "claude-opus-9[1m]",  # unknown base, parseable tag
            "claude-opus-5[thinking]",  # known base, UNPARSEABLE tag
            "claude-opus-5[]",  # known base, empty tag
            "claude-opus-5[200k]",  # known base, tag advertises a SMALLER window
            "claude-opus-4-9",  # version segment must never be stripped
            "claude-sonnet-4-9",  # ditto, other family
            "claude-opus-5-2026060",  # 7 digits: not a snapshot date
            "[1m]",  # degenerate: strip would leave an empty base
        ],
    )
    def test_unresolvable_ids_fall_back_to_the_conservative_floor(self, model: str) -> None:
        cfg = load_config()
        prof = resolve_threshold(model, cfg)
        assert prof.resolution == RESOLUTION_DEFAULT
        assert prof.matched is False
        # Floor property (AC-8): <= every known model's thresholds.
        for known, _p, _r in _ONE_M_ID_FORMS:
            reference = resolve_threshold(known, cfg)
            assert prof.soft_tok <= reference.soft_tok
            assert prof.hard_tok <= reference.hard_tok

    def test_smaller_window_tag_is_refused_not_widened(self) -> None:
        # The one way normalization could be MORE permissive than the truth: a
        # variant tag naming a window smaller than the base model's profile.
        cfg = load_config()
        narrow = resolve_threshold("claude-opus-5[200k]", cfg)
        wide = resolve_threshold("claude-opus-5", cfg)
        assert wide.context_window == 1_000_000
        assert narrow.context_window == 200000
        assert narrow.soft_tok < wide.soft_tok

    def test_equal_and_larger_window_tags_are_accepted(self) -> None:
        cfg = load_config()
        # Exactly the profile's window -> accepted (not "smaller than").
        assert resolve_threshold("claude-opus-5[1000k]", cfg).resolution == RESOLUTION_NORMALIZED
        # A future wider variant -> accepted; the profile's caps stay conservative.
        larger = resolve_threshold("claude-opus-5[2m]", cfg)
        assert larger.resolution == RESOLUTION_NORMALIZED
        assert larger.profile_name == "opus_1m"

    # -- Provenance bookkeeping. -----------------------------------------------

    def test_matched_and_resolution_stay_consistent(self) -> None:
        cfg = load_config()
        samples = [m for m, _p, _r in _ONE_M_ID_FORMS] + [
            "claude-haiku-4-5",
            "totally-unknown-xyz",
            "claude-opus-5[200k]",
            None,
        ]
        for model in samples:
            prof = resolve_threshold(model, cfg)
            assert prof.matched == (prof.resolution != RESOLUTION_DEFAULT)
            # resolved_model_id is set iff a profile was deliberately chosen...
            assert (prof.resolved_model_id is not None) == prof.matched
            # ...and when set it is a real key in the config's models map.
            if prof.resolved_model_id is not None:
                assert prof.resolved_model_id in cfg["models"]

    def test_config_naming_an_undefined_profile_reports_the_fallback_honestly(self) -> None:
        cfg = {
            "profiles": {"floor": {"context_window": 200000, "soft_wrapup_fraction": 0.5}},
            "models": {"m": "does_not_exist"},
            "defaults": {"profile": "floor"},
        }
        prof = resolve_threshold("m", cfg)
        # The reported tier must be the one whose numbers were actually used.
        assert prof.profile_name == "floor"
        assert prof.resolution == RESOLUTION_DEFAULT
        assert prof.matched is False


# ---------------------------------------------------------------------------
# Config-key window verification (the precondition normalization depends on).
#
# Normalization turned every `models:` key from an exact-match-only entry into a
# FAMILY-WIDE PREFIX TARGET — `claude-opus-4` now also answers for
# `claude-opus-4-20250514` and every other snapshot. So a key that overstates a
# model's window overstates it for N ids, and `hard_tok` (a fraction of that
# window) can land ABOVE `auto_compact_fraction * real window`: the hard wrap-up
# would fire only after the harness had already compacted the thread away. That
# is the "sessions die without a handoff" harm, and it is strictly worse than the
# premature-wrap-up token tax normalization exists to fix.
#
# These tests are the enforcement of the config's VERIFIED WINDOWS ONLY rule.
# ---------------------------------------------------------------------------

#: Real context window per `models:` key, verified 2026-08-07 against the
#: authoritative Anthropic model catalog (`claude-api` skill, Current Models).
#: The 1M window class begins at the 4.6 generation; 4.5-and-earlier are 200K.
#: Adding a `models:` key WITHOUT adding it here fails
#: ``test_every_config_key_has_a_verified_window`` — that is the point.
_VERIFIED_MODEL_WINDOWS: dict[str, int] = {
    "claude-opus-5": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-sonnet-4-5": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-4-5": 200_000,
}

#: Real, released model ids whose true window is 200K — listed in the config or
#: not. Every one must stay below the 200K auto-compact backstop however it
#: resolves (exact key, normalized base, or the conservative floor). This is the
#: assertion that generalises: it encodes "we always fire before the harness
#: compacts" as a test rather than as a comment, and it catches a bad key whether
#: it is reached directly or via normalization.
_KNOWN_200K_IDS = [
    "claude-opus-4",
    "claude-opus-4-20250514",
    "claude-opus-4-1",
    "claude-opus-4-1-20250805",
    "claude-opus-4-5",
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4",
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
]


def _auto_compact_fraction(prof: ThresholdProfile) -> float:
    """Recover the profile's harness-backstop fraction from its resolved values."""
    assert prof.context_window > 0
    return prof.auto_compact_tok / prof.context_window


class TestConfigKeyWindowsAreVerified:
    def test_every_config_key_has_a_verified_window(self) -> None:
        # Both directions: an unverified key added to the config fails here, and a
        # stale entry left in the table after a key is removed fails here too.
        config_keys = set(load_config()["models"])
        assert config_keys == set(_VERIFIED_MODEL_WINDOWS), (
            "config `models:` keys and the verified-window table disagree. Every key "
            "must have its real window checked against the model catalog before it is "
            "listed — normalization makes each key answer for a whole id family."
        )

    @pytest.mark.parametrize(("model", "real_window"), sorted(_VERIFIED_MODEL_WINDOWS.items()))
    def test_profile_window_matches_the_models_real_window(
        self, model: str, real_window: int
    ) -> None:
        prof = resolve_threshold(model, load_config())
        assert prof.matched is True
        assert prof.context_window == real_window, (
            f"{model} resolves to profile {prof.profile_name!r} which assumes a "
            f"{prof.context_window}-token window, but the model's real window is "
            f"{real_window}. Thresholds are computed from the assumed window."
        )

    @pytest.mark.parametrize(("model", "real_window"), sorted(_VERIFIED_MODEL_WINDOWS.items()))
    def test_config_key_fires_before_the_harness_auto_compacts(
        self, model: str, real_window: int
    ) -> None:
        prof = resolve_threshold(model, load_config())
        backstop = int(_auto_compact_fraction(prof) * real_window)
        assert prof.hard_tok < backstop, (
            f"{model}: hard threshold {prof.hard_tok} is at or above the "
            f"{backstop}-token auto-compact backstop of its REAL {real_window} window — "
            "the handoff would fire only after compaction destroyed the thread."
        )
        assert prof.soft_tok <= prof.hard_tok

    @pytest.mark.regression
    @pytest.mark.parametrize("model", _KNOWN_200K_IDS)
    def test_known_200k_models_stay_below_their_real_backstop(self, model: str) -> None:
        # Regression: `claude-opus-4` was mapped to opus_1m under an inline
        # "historically 200K — re-check at add-time" caveat. Normalization then made
        # it the prefix target for `claude-opus-4-20250514`, moving that id from the
        # 200K floor (hard 130000) to the opus_1m hard cap — ABOVE the 166000 backstop
        # of its real window. That overshoot was 14000 tokens when the cap was 180000
        # and is 234000 now that it is 400000, so this guard got more load-bearing,
        # not less. Guards every 200K-family id, listed or not.
        prof = resolve_threshold(model, load_config())
        backstop = int(_auto_compact_fraction(prof) * 200_000)
        assert prof.context_window <= 200_000, (
            f"{model} is a 200K model but resolved to a {prof.context_window}-token "
            f"profile ({prof.profile_name})."
        )
        assert prof.hard_tok < backstop, (
            f"{model}: hard {prof.hard_tok} >= real-window backstop {backstop}."
        )

    @pytest.mark.parametrize(("model", "real_window"), sorted(_VERIFIED_MODEL_WINDOWS.items()))
    def test_dated_snapshot_inherits_the_key_it_normalizes_to(
        self, model: str, real_window: int
    ) -> None:
        # Makes the family-wide-target property explicit: whatever a key claims, it
        # claims for every snapshot of that model too. Pairs with the window checks
        # above so a wrong key cannot be wrong quietly for N ids.
        snapshot = resolve_threshold(f"{model}-20250101", load_config())
        assert snapshot.resolution == RESOLUTION_NORMALIZED
        assert snapshot.resolved_model_id == model
        assert snapshot.context_window == real_window
        assert snapshot.hard_tok < int(_auto_compact_fraction(snapshot) * real_window)


# ---------------------------------------------------------------------------
# Wrap-up cap recalibration (2026-08-07) + the handoff-headroom invariant.
#
# The caps are a JUDGMENT, and these tests are careful not to pretend otherwise.
# What they pin is not "the right occupancy to wrap up at" — nothing in this repo
# can answer that — but three things that ARE checkable:
#   1. the numbers currently in force, so a change to them is deliberate;
#   2. the mechanical invariant that a session ordered to hand off can still
#      AFFORD to write the handoff, with the affordability measured from this
#      repo's own artifacts rather than assumed;
#   3. that the recorded rationale in the config still describes the live numbers.
#
# Why (2) is not already covered: TestConfigKeyWindowsAreVerified asserts
# `hard_tok < backstop`. A hard threshold one token below the backstop satisfies
# that and still loses the thread, because the wrap-up itself costs tokens. The
# reserve below puts a measured number on the word "before".
# ---------------------------------------------------------------------------

#: Tokens that must stay free between the hard wrap-up threshold and the harness
#: auto-compaction backstop. Derived, not chosen: `_measured_handoff_cost_tokens`
#: re-measures the durable components (18620 tokens, re-counted 2026-08-08 in
#: round 4) from real files on every run — including the largest of
#: the 15 real `docs/handoff/HANDOFF-*.md` artifacts on disk; the config's CAP
#: RECALIBRATION block itemizes those plus a measured-once ~1948-token BUILD_STATUS
#: edit payload, and this constant rounds the ~20568 total up to cover what was not
#: itemized (close_discussion calls, retention, the final report turn).
#: `test_stated_reserve_matches_the_test_constant` keeps this number and the
#: config's copy of it from drifting apart. The itemized figures here are a dated
#: snapshot for a reader; only the live re-measurement is load-bearing.
HANDOFF_HEADROOM_TOKENS = 25_000

#: Anthropic's DOCUMENTED server-side compaction default trigger, in tokens: the
#: point at which the API begins summarizing earlier context by default (beta
#: `compact-2026-01-12`). Verified 2026-08-08 against the authoritative reference.
#:
#: This is the anchor the 1M caps are derived from as of 2026-08-08, replacing a
#: third-party "effective working fraction ~= 50-65% of the window" band that was
#: measured on earlier model generations. It is deliberately NOT a quality
#: threshold and must never be cited as one: it says a conversation has grown large
#: enough to be worth *managing*, which is the cost claim, not that the model has
#: grown worse. The reference states the opposite about quality — a 1M window as
#: both default and maximum for Claude Opus 5, with instruction following, tool
#: calling and reasoning strong across the full window, and no published
#: degradation threshold at all.
_DOCUMENTED_COMPACTION_TRIGGER = 150_000

#: chars -> tokens divisor. 3.5 sits BELOW the lowest chars/token ratio measured
#: across every file `_measured_handoff_cost_tokens` reads when those same files
#: were run through a real BPE tokenizer (lowest observed 3.538, mean 3.835), so
#: this over-states the cost of each of them rather than under-stating it. A real
#: tokenizer is deliberately NOT imported: none is a declared dependency of this
#: project, and an optional import would make the assertion vary by environment.
#: The calibration tokenizer was a GPT-family BPE used as a proxy for Claude's —
#: which is itself a reason to keep the divisor on the conservative side.
_CHARS_PER_TOKEN = 3.5


def _est_tokens(path: Path) -> int:
    """Conservatively estimate the token cost of a UTF-8 text file (0 if absent)."""
    try:
        return int(len(path.read_text(encoding="utf-8")) / _CHARS_PER_TOKEN)
    except OSError:
        return 0


def _measured_handoff_cost_tokens() -> dict[str, int]:
    """Re-measure what writing ONE handoff costs, from this repo's own artifacts.

    Components follow the `wrapping-up-sessions` protocol steps: load the skill,
    read BUILD_STATUS.md (step 3), read the handoff template (step 5), write the
    artifact (step 5). Returned itemized so a failure names which file grew.
    """
    root = PROJECT_ROOT
    components = {
        "wrapup_skill_load": _est_tokens(
            root / ".claude" / "skills" / "wrapping-up-sessions" / "SKILL.md"
        ),
        "build_status_read": _est_tokens(root / "BUILD_STATUS.md"),
        "handoff_template_read": _est_tokens(root / "docs" / "templates" / "handoff-template.md"),
    }
    # `HANDOFF-supervisor-rolling.md` is excluded by name: the session supervisor
    # APPENDS to one file across a whole chain of sessions (measured at ~23000
    # tokens), so it is not the cost of a single handoff write. `docs/handoff/` is
    # also gitignored, so a fresh checkout may hold none at all — the template is
    # then the best available stand-in for an artifact's size.
    artifacts = [
        p for p in (root / "docs" / "handoff").glob("HANDOFF-*.md") if "rolling" not in p.name
    ]
    components["handoff_artifact_write"] = (
        max((_est_tokens(p) for p in artifacts), default=0) or components["handoff_template_read"]
    )
    return components


def _profile_names() -> list[str]:
    """Every profile the config defines, including any no model maps to."""
    return sorted(load_config().get("profiles", {}))


def _resolve_profile(name: str) -> ThresholdProfile:
    """Resolve a profile BY NAME through the real resolver (via `defaults`).

    Going through `resolve_threshold` rather than reading the YAML keeps these
    tests measuring the same ``min(fraction*window, cap)`` arithmetic production
    uses, and covers profiles that no `models:` key currently points at.
    """
    cfg = load_config()
    return resolve_threshold(None, {**cfg, "defaults": {"profile": name}})


#: Effective (soft_tok, hard_tok) per profile after the 2026-08-08 recalibration
#: (ADR-0033). The 1M pair moved (opus_1m was 140000/180000, sonnet_1m was
#: 120000/160000); the 200K pair deliberately did not — they are the profiles
#: actually close to the auto-compaction backstop, so widening them was out of
#: scope for an edit whose whole point was the 1M class.
#:
#: These are LOWER than the 400000/500000 an earlier attempt proposed. ADR-0033
#: upholds the cost half of ADR-0018's magnitude objection ("per-turn cost scales
#: with resident context") and answers it by taking 100000 fewer tokens of hard
#: cap, rather than by rewording the objection away.
_RECALIBRATED_CAPS: dict[str, tuple[int, int]] = {
    "opus_1m": (300_000, 400_000),
    "sonnet_1m": (250_000, 350_000),
    "sonnet_200k": (110_000, 140_000),
    "haiku_200k": (100_000, 130_000),
}


class TestWrapupCapRecalibration:
    """Pin the thresholds in force, so moving them is always a deliberate act."""

    @pytest.mark.parametrize(("name", "expected"), sorted(_RECALIBRATED_CAPS.items()))
    def test_effective_thresholds_are_the_recalibrated_values(
        self, name: str, expected: tuple[int, int]
    ) -> None:
        prof = _resolve_profile(name)
        assert (prof.soft_tok, prof.hard_tok) == expected

    def test_the_table_covers_every_profile_the_config_defines(self) -> None:
        # A new profile added without a considered soft/hard pair fails here.
        assert set(_profile_names()) == set(_RECALIBRATED_CAPS)

    @pytest.mark.regression
    def test_a_19_percent_1m_session_no_longer_trips_the_hard_stop(self) -> None:
        # Regression, 2026-08-07: a live session on a 1M-window model was ordered
        # to stop work and hand off at ~19% occupancy, because opus_1m's hard cap
        # was 180000 — 18% of the window it was actually running in.
        prof = resolve_threshold("claude-opus-5[1m]", load_config())
        quiet = Occupancy(190_000, 19.0, 1_000_000, "statusline", "claude-opus-5[1m]")
        assert classify_level(quiet, prof) is None
        # ...and both nudges still fire, in order, further up the window.
        soft = Occupancy(prof.soft_tok, 30.0, 1_000_000, "statusline", "m")
        hard = Occupancy(prof.hard_tok, 40.0, 1_000_000, "statusline", "m")
        assert classify_level(soft, prof) == "soft"
        assert classify_level(hard, prof) == "hard"

    @pytest.mark.parametrize("name", ["opus_1m", "sonnet_1m"])
    def test_absolute_caps_still_bind_on_the_1m_profiles(self, name: str) -> None:
        # The design property the THRESHOLD MODEL block describes: on a 1M window
        # the absolute cap, not the percentage, is the binding term. Raising the
        # caps must not have quietly handed control back to the fractions (which
        # would put hard at 700000 without anyone deciding to).
        raw = load_config()["profiles"][name]
        prof = _resolve_profile(name)
        assert raw["soft_abs_cap_tokens"] < raw["soft_wrapup_fraction"] * raw["context_window"]
        assert raw["hard_abs_cap_tokens"] < raw["hard_wrapup_fraction"] * raw["context_window"]
        assert prof.soft_tok == raw["soft_abs_cap_tokens"]
        assert prof.hard_tok == raw["hard_abs_cap_tokens"]

    @pytest.mark.parametrize("name", ["opus_1m", "sonnet_1m"])
    def test_1m_hard_caps_stay_within_the_documented_compaction_anchor(self, name: str) -> None:
        # RETARGETED 2026-08-08. This test was
        # `test_1m_hard_caps_stay_below_the_researched_bands_bottom_edge` and asserted
        # `hard < 0.50 * window`, i.e. below the bottom edge of a third-party
        # "effective working fraction ~= 50-65%" band. That band is retired: it is
        # older, measured on earlier model generations, and the authoritative
        # Anthropic reference states capability holds across the FULL 1M window with
        # no published degradation threshold. A test named after a retired claim is a
        # stale citation, so it is re-anchored on the number Anthropic does publish —
        # the 150000-token server-side compaction default trigger (see the config's
        # `UNIT` term and ADR-0033's derivation).
        #
        # NOTHING IS WEAKENED BY THE SWAP. The new ceiling is 3 x 150000 = 450000;
        # the old one was 0.50 x 1000000 = 500000. The new bound is STRICTLY TIGHTER,
        # so every edit the old test would have caught, this one still catches —
        # including the 500000 an earlier attempt shipped, which now fails on two
        # counts rather than sitting exactly on the old line. Asserted here rather
        # than as a fraction of the window because the anchor is denominated in
        # absolute tokens: it is a cost/manageability threshold, and you are billed
        # in tokens, not in percentages of a window.
        prof = _resolve_profile(name)
        assert prof.hard_tok < 3 * _DOCUMENTED_COMPACTION_TRIGGER, (
            f"{name}: hard {prof.hard_tok} is at or above 3x the documented "
            f"server-side compaction trigger ({3 * _DOCUMENTED_COMPACTION_TRIGGER}). "
            "That anchor is the only published number the caps rest on; drifting past "
            "it needs a new derivation in ADR-0033, not a bigger constant here."
        )
        assert prof.soft_tok < prof.hard_tok
        # The old bound, kept as a subsumption check so the retarget cannot silently
        # loosen anything: passing the new assertion must imply passing the old one.
        assert 3 * _DOCUMENTED_COMPACTION_TRIGGER <= int(0.50 * prof.context_window)

    def test_the_1m_caps_are_exactly_what_the_documented_arithmetic_produces(self) -> None:
        # ADR-0033's derivation, executed. The config states an arithmetic
        # (soft = 2 x UNIT; hard = soft + RUNWAY; sonnet = opus - TIER_STEP) and the
        # resolver has to actually produce it — otherwise the "re-derivation" is
        # prose sitting next to unrelated numbers, which is the failure mode this
        # whole suite exists to prevent.
        unit, runway, step = _DOCUMENTED_COMPACTION_TRIGGER, 100_000, 50_000
        opus, sonnet = _resolve_profile("opus_1m"), _resolve_profile("sonnet_1m")
        assert opus.soft_tok == 2 * unit
        assert opus.hard_tok == opus.soft_tok + runway
        assert sonnet.soft_tok == opus.soft_tok - step
        assert sonnet.hard_tok == opus.hard_tok - step
        # RUNWAY is claimed to be ~5x the measured handoff cost — the reason the
        # soft->hard gap is wide enough to finish a step AND write the handoff.
        assert runway >= 4 * sum(_measured_handoff_cost_tokens().values())
        # TIER_STEP is claimed to be RUNWAY / 2.
        assert step * 2 == runway

    def test_tier_ordering_is_preserved(self) -> None:
        # opus > sonnet > the conservative floor, the ordering the config's prose
        # asserts ("opus degrades slowest", "sonnet faster degradation risk").
        opus, sonnet = _resolve_profile("opus_1m"), _resolve_profile("sonnet_1m")
        floor = _resolve_profile(load_config()["defaults"]["profile"])
        assert opus.soft_tok > sonnet.soft_tok > floor.soft_tok
        assert opus.hard_tok > sonnet.hard_tok > floor.hard_tok

    @pytest.mark.parametrize("name", ["opus_1m", "sonnet_1m"])
    def test_soft_to_hard_runway_can_absorb_a_handoff(self, name: str) -> None:
        # "Finish the current atomic step, THEN wrap up" is only an honest
        # instruction if the gap between the two nudges is wider than the handoff.
        prof = _resolve_profile(name)
        assert prof.hard_tok - prof.soft_tok >= HANDOFF_HEADROOM_TOKENS


class TestHandoffHeadroomInvariant:
    """A session ordered to hand off must still be able to afford the handoff."""

    @pytest.mark.parametrize("name", _profile_names())
    def test_every_profile_reserves_room_to_write_a_handoff(self, name: str) -> None:
        prof = _resolve_profile(name)
        headroom = prof.auto_compact_tok - prof.hard_tok
        assert headroom >= HANDOFF_HEADROOM_TOKENS, (
            f"profile {name!r}: only {headroom} tokens separate the hard wrap-up "
            f"threshold ({prof.hard_tok}) from the auto-compaction backstop "
            f"({prof.auto_compact_tok}), but writing one handoff in this repo costs "
            f"~{sum(_measured_handoff_cost_tokens().values())} tokens and the reserve "
            f"is {HANDOFF_HEADROOM_TOKENS}. A hard nudge that fires with no room to "
            "act on it loses the thread — the exact harm this machinery prevents."
        )

    def test_measured_handoff_cost_still_fits_the_reserve(self) -> None:
        # The tripwire. The reserve was sized against files that grow: when
        # BUILD_STATUS.md or the handoff template outgrows it, this fails and the
        # fix is a decision (trim the file, or raise the reserve AND re-check every
        # profile above) rather than a silent erosion of the margin.
        components = _measured_handoff_cost_tokens()
        for required in ("wrapup_skill_load", "build_status_read", "handoff_template_read"):
            assert components[required] > 0, (
                f"{required} measured as 0 tokens — the source file is missing, so this "
                "measurement would pass vacuously. Fix the path, do not lower the bar."
            )
        total = sum(components.values())
        assert total <= HANDOFF_HEADROOM_TOKENS, (
            f"writing one handoff now costs ~{total} tokens, above the "
            f"{HANDOFF_HEADROOM_TOKENS}-token reserve every profile is sized against. "
            f"Itemized: {components}"
        )

    def test_the_invariant_has_teeth_beyond_the_existing_backstop_check(self) -> None:
        # Demonstrates that this class is not a restatement of
        # TestConfigKeyWindowsAreVerified. A profile whose hard cap sits 1000 tokens
        # under the backstop satisfies the OLD check and fails this one.
        danger = {
            **load_config(),
            "profiles": {
                "danger": {
                    "context_window": 1_000_000,
                    "soft_wrapup_fraction": 0.9,
                    "hard_wrapup_fraction": 0.9,
                    "soft_abs_cap_tokens": 829_000,
                    "hard_abs_cap_tokens": 829_000,
                    "auto_compact_fraction": 0.83,
                }
            },
            "defaults": {"profile": "danger"},
        }
        prof = resolve_threshold(None, danger)
        assert prof.hard_tok < prof.auto_compact_tok  # passes the pre-existing check
        assert prof.auto_compact_tok - prof.hard_tok < HANDOFF_HEADROOM_TOKENS  # fails this one


#: The ADR that ORIGINATED these caps. It is a superseded record now, and it is
#: IMMUTABLE (Principle #4: ADRs are never deleted, only superseded with a
#: reference to the replacement). Its original objection to the magnitude now in
#: force is preserved verbatim inside it, on purpose.
_ADR_0018 = "docs/adr/ADR-0018-model-aware-session-wrapup.md"

#: The ADR that GOVERNS the cap values in force. It supersedes ADR-0018's 1M cap
#: VALUES and nothing else — ADR-0018 still governs the threshold structure.
_ADR_0033 = "docs/adr/ADR-0033-wrapup-cap-recalibration.md"

#: The model-facing skill the wrap-up protocol loads when a nudge fires.
_WRAPUP_SKILL = ".claude/skills/wrapping-up-sessions/SKILL.md"

#: Every document that tells a reader — or a model — what the wrap-up caps are
#: for TODAY. ADR-0018 is deliberately NOT in this tuple: it is history, and
#: scanning it for a superseded rationale would demand the rewrite that
#: Principle #4 forbids (and that a previous attempt actually performed).
_GOVERNING_DOCS = (_ADR_0033, _WRAPUP_SKILL, "config/model_context_profiles.yaml")


def _governing_adr_text() -> str:
    """The full text of the ADR that governs the caps, or fail explaining why not."""
    path = PROJECT_ROOT / _ADR_0033
    assert path.is_file(), (
        f"{_ADR_0033} is missing. The 1M wrap-up caps were moved off the values "
        "ADR-0018 set, past a magnitude ADR-0018 argued against, so a decision "
        "record has to exist for them. Recording the rationale only in "
        "config/model_context_profiles.yaml is what this test exists to prevent: "
        "the config and the decision record then contradict each other silently. "
        "Amending ADR-0018 in place is NOT the alternative — that is the defect "
        "this ADR was written to fix."
    )
    return path.read_text(encoding="utf-8")


def _governing_adr_decision() -> str:
    """ADR-0033's ``## Decision`` section — where its binding numbers must live."""
    match = re.search(
        r"^## Decision\b.*?(?=^## |\Z)", _governing_adr_text(), re.DOTALL | re.MULTILINE
    )
    assert match is not None, f"{_ADR_0033} has no '## Decision' section"
    return match.group(0)


class TestCapRationaleIsRecorded:
    """The rationale must live in the config, admit it is a judgment, and not rot.

    A threshold with no recorded reasoning is precisely what this change fixes; a
    recorded reasoning that drifts away from the live numbers is the same failure
    one generation later. These bind the prose to the resolver.
    """

    @staticmethod
    def _block() -> str:
        text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"=== CAP RECALIBRATION\b.*?=== END CAP RECALIBRATION ===", text, re.DOTALL
        )
        assert match is not None, (
            "config/model_context_profiles.yaml no longer carries a CAP RECALIBRATION "
            "block. The wrap-up caps are a judgment made against one model generation; "
            "deleting the recorded rationale is not a way to make this test pass."
        )
        return match.group(0)

    def test_block_labels_itself_a_judgment_not_a_measurement(self) -> None:
        assert "THIS IS A JUDGMENT, NOT A MEASUREMENT" in self._block()

    def test_block_admits_what_cannot_be_measured(self) -> None:
        block = self._block()
        assert "WHAT NOBODY HERE HAS MEASURED" in block
        assert "not answerable from this repository" in block

    def test_block_names_what_would_change_the_numbers(self) -> None:
        assert "WHAT WOULD CHANGE THESE NUMBERS" in self._block()

    def test_block_states_which_way_it_erred(self) -> None:
        assert "WHICH WAY THIS ERRS" in self._block()

    def test_stated_caps_match_what_the_resolver_computes(self) -> None:
        stated = {
            name: (int(soft), int(hard))
            for name, soft, hard in re.findall(
                r"CAP (\w+): soft (\d+) / hard (\d+)", self._block()
            )
        }
        assert set(stated) == set(_profile_names()), (
            f"the block states caps for {sorted(stated)} but the config defines "
            f"profiles {_profile_names()}. Every profile's numbers must be accounted "
            "for in the rationale, including ones left deliberately unchanged."
        )
        for name, (soft, hard) in stated.items():
            prof = _resolve_profile(name)
            assert (prof.soft_tok, prof.hard_tok) == (soft, hard), (
                f"the rationale says {name} is soft {soft} / hard {hard}, but the "
                f"resolver computes soft {prof.soft_tok} / hard {prof.hard_tok}."
            )

    def test_stated_reserve_matches_the_test_constant(self) -> None:
        claimed = re.search(r"Reserve used by the invariant test: (\d+) tokens", self._block())
        assert claimed is not None, "the block states no handoff reserve"
        assert int(claimed.group(1)) == HANDOFF_HEADROOM_TOKENS

    # -- the config must not be the only place the decision lives -------------
    #
    # The failure this guards is not hypothetical: the recalibration originally
    # shipped with a thorough rationale in the config and ZERO ADR work, while
    # ADR-0018 as accepted rejected percentage-only thresholds partly because the
    # ~550K they produce is "wasteful and degraded" — and the new hard cap is
    # 500000. The rationale of record contradicted the decision of record, and
    # nothing executed either, so nothing noticed.

    def test_block_cites_the_governing_adr(self) -> None:
        assert "ADR-0033" in self._block(), (
            "the CAP RECALIBRATION block never names the decision record it is "
            "operating under. Moving these caps is an ADR-level decision, not a "
            "config edit with a long comment."
        )

    def test_the_cited_adr_exists_and_supersedes_the_original(self) -> None:
        # Retarget of test_the_cited_adr_carries_a_matching_amendment. It used to
        # demand an in-place amendment to ADR-0018; that demand is what produced
        # the Principle #4 violation this ADR replaces.
        text = _governing_adr_text()
        frontmatter = text.split("---", 2)[1]
        assert re.search(r"^supersedes:\s*ADR-0018\s*$", frontmatter, re.MULTILINE), (
            f"{_ADR_0033} does not declare `supersedes: ADR-0018` in its frontmatter. "
            "A replacement record that does not name what it replaces leaves two "
            "live ADRs stating different caps."
        )
        assert "supersedes_scope:" in frontmatter, (
            "the supersession is unscoped. ADR-0018 governs far more than the cap "
            "values (the threshold structure, the consent model, the sensor design); "
            "a blanket supersession would read as retiring all of it."
        )

    def test_adr_caps_match_what_the_resolver_computes(self) -> None:
        # Same binding as test_stated_caps_match_what_the_resolver_computes, aimed
        # at the ADR. Moving a cap now requires touching the config, the ADR, and
        # this table together, or the suite goes red.
        stated = {
            name: (int(soft), int(hard))
            for name, soft, hard in re.findall(
                r"CAP (\w+): soft (\d+) / hard (\d+)", _governing_adr_decision()
            )
        }
        assert set(stated) == {"opus_1m", "sonnet_1m"}, (
            f"{_ADR_0033}'s Decision section states caps for {sorted(stated)}; it must "
            "state exactly the two 1M profiles it moved (the 200K pair was "
            "deliberately left alone and is documented as unchanged)."
        )
        for name, (soft, hard) in stated.items():
            prof = _resolve_profile(name)
            assert (prof.soft_tok, prof.hard_tok) == (soft, hard), (
                f"{_ADR_0033} says {name} is soft {soft} / hard {hard}, but the "
                f"resolver computes soft {prof.soft_tok} / hard {prof.hard_tok}. "
                "The decision record and the running config have come apart."
            )

    def test_the_adrs_stated_handoff_ratio_is_computed_against_its_own_defined_term(self) -> None:
        # ROUND 3 FIX, executed. ADR-0033 said the tightest profile's headroom was
        # "1.42x the measured cost of one handoff". 1.42 is 26000 / 18371 — the LIVE
        # four-component subtotal — while the term the same ADR defines as the
        # measured handoff cost is `HANDOFF`, which is that subtotal PLUS the
        # itemized BUILD_STATUS edit payload. Two quantities, one name, and the
        # sentence used the smaller one, which flattered the margin. Against
        # `HANDOFF` the ratio was 1.28x in round 3, and 1.26x after round 4
        # re-derived HANDOFF from its own itemization (20391 -> 20568) — which is
        # why the assertion divides rather than matching a literal.
        #
        # Both figures in that sentence are now divisions this test performs: the
        # denominators come from the ADR's own terms table and the live resolver, so
        # neither the ADR's arithmetic nor its defined term can move alone.
        adr = _governing_adr_text()
        flat = re.sub(r"[`*]", "", re.sub(r"\s+", " ", adr))
        claim = re.search(r"([\d.]+)x the RESERVE and ([\d.]+)x HANDOFF", flat)
        assert claim is not None, (
            f"{_ADR_0033} no longer states the tightest profile's headroom as a "
            "multiple of BOTH the reserve and the measured handoff cost. That "
            "sentence is what tells a reader how little margin the 200K class has; "
            "deleting it is not a way to make this test pass."
        )
        adr_terms = {
            name: int(value.replace(",", ""))
            for name, value in re.findall(r"^\|\s*`([A-Z_]+)`\s*\|\s*([\d,]+)\s*\|", adr, re.M)
        }
        for required in ("RESERVE", "HANDOFF"):
            assert required in adr_terms, f"{_ADR_0033}'s terms table omits {required}"
        tightest = min(
            (_resolve_profile(name) for name in _profile_names()),
            key=lambda p: p.auto_compact_tok - p.hard_tok,
        )
        headroom = tightest.auto_compact_tok - tightest.hard_tok
        for stated, term in ((claim.group(1), "RESERVE"), (claim.group(2), "HANDOFF")):
            assert float(stated) == pytest.approx(headroom / adr_terms[term], abs=0.005), (
                f"{_ADR_0033} states {stated}x {term}, but {tightest.profile_name} — the "
                f"tightest profile the config defines — has {headroom} tokens of headroom "
                f"and the ADR's own terms table puts {term} at {adr_terms[term]}, i.e. "
                f"{headroom / adr_terms[term]:.2f}x. A ratio computed against a quantity "
                "the document does not define as its denominator is how 1.42x got here."
            )

    def test_adr_addresses_the_objection_it_contradicts(self) -> None:
        # A replacement that moves the cap toward a magnitude the superseded ADR
        # argued against, without engaging that argument, is the same defect
        # wearing a new number.
        text = _governing_adr_text()
        assert "550K" in text, (
            f"{_ADR_0033} never mentions the ~550K magnitude ADR-0018 called "
            "'wasteful and degraded', though the hard cap now in force is 73% of it. "
            "Moving toward a number the superseded ADR rejected is the thing that "
            "needs explaining."
        )
        assert "per-turn cost scales with resident context" in text, (
            "the objection is paraphrased rather than quoted. The previous attempt "
            "deleted this sentence from ADR-0018 outright; the replacement record has "
            "to carry it verbatim so a reader sees the argument against the number "
            "now in force, not a summary written by the side that won."
        )

    def test_adr_declares_the_objections_disposition_in_a_heading(self) -> None:
        # Deliberately asserted against a HEADING, not the body. A body-wide keyword
        # scan is escapable: prose repeats itself, so gutting the real disposition
        # can leave a stray "withdrawn" elsewhere and keep the test green (verified —
        # that mutation escaped an earlier version of this check). A heading is one
        # line, it is what a reader sees first, and any rewrite of the substance has
        # to restate it.
        headings = [
            line
            for line in _governing_adr_text().splitlines()
            if line.startswith("#") and "objection" in line.lower()
        ]
        assert headings, (
            f"{_ADR_0033} has no heading about the objection at all. ADR-0018 rejected "
            "percentage-only thresholds because ~550K is 'wasteful and degraded'; the "
            "hard cap is now 400000. That objection's fate belongs in a heading, not "
            "buried for a reader to reconcile from the body."
        )
        assert any(
            word in h.lower()
            for h in headings
            for word in ("withdraw", "uphold", "upheld", "narrow")
        ), (
            f"{_ADR_0033} names the objection in a heading but does not say what became "
            f"of it.\n  headings: {headings}\n"
            "It must be explicitly withdrawn, narrowed, or upheld there."
        )

    def test_adr_labels_the_caps_a_judgment_and_names_its_triggers(self) -> None:
        # The ADR, not only the config, has to carry the epistemic label. A reader
        # who arrives via the decision record must not come away thinking 400000
        # was measured.
        text = _governing_adr_text()
        assert "not answerable from this repository" in text, (
            f"{_ADR_0033} does not admit that 'at what occupancy does output quality "
            "degrade?' is unanswerable here. Without that sentence the ADR reads as "
            "evidence, and it is not evidence."
        )
        assert "What would change these numbers" in text, (
            f"{_ADR_0033} names no triggers that would move the caps. A judgment with "
            "no stated falsifier is indistinguishable from a preference."
        )

    @pytest.mark.regression
    def test_adr_0018_was_not_amended_in_place(self) -> None:
        # THE regression this whole record exists for. A prior slice raised the caps
        # by editing ADR-0018 and deleting twelve lines of its reasoning, including
        # the objection to the magnitude it was moving to. Principle #4: ADRs are
        # never deleted, only superseded with a reference to the replacement.
        path = PROJECT_ROOT / _ADR_0018
        assert path.is_file(), f"{_ADR_0018} is missing — the superseded record is gone"
        text = path.read_text(encoding="utf-8")
        assert "## Amendment — 2026-08-07" not in text, (
            "ADR-0018 has been amended in place again. The caps are governed by "
            f"{_ADR_0033}; ADR-0018 is history and is immutable (Principle #4)."
        )
        # Whitespace-normalized: the objection wraps across two lines in the file,
        # so a raw substring match would be a hostage to where the wrap falls.
        flat = re.sub(r"\s+", " ", text)
        assert (
            "wasteful (per-turn cost scales with resident context) and still degraded" in flat
        ), (
            "ADR-0018 no longer carries its original objection to the ~550K magnitude. "
            "That sentence is the argument AGAINST the caps now in force, and deleting "
            "it is exactly the failure that produced this test. Restore the file to its "
            "committed state; record disagreements in a superseding ADR."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", sorted(_GOVERNING_DOCS))
    def test_no_governing_doc_still_justifies_the_caps_by_resident_rot(self, rel: str) -> None:
        # Regression, 2026-08-07: after the caps were raised, the decision record, the
        # model-facing wrapping-up-sessions SKILL.md, and this config all still told
        # their reader that the cap exists to avoid running to ~550K tokens of
        # "resident rot" — a magnitude the cap had moved most of the way toward.
        # SKILL.md is the one a model loads mid-wrap-up, so a stale justification
        # there is not a documentation nit; it is an instruction.
        #
        # ADR-0018 is NOT scanned: it is the superseded record and its "resident rot"
        # lines are its original reasoning, which Principle #4 requires be preserved.
        # Scanning it would demand the very rewrite this suite now forbids
        # (test_adr_0018_was_not_amended_in_place).
        path = PROJECT_ROOT / rel
        assert path.is_file(), f"{rel} is missing — this check would pass vacuously"
        offenders = [
            f"{rel}:{n}: {line.strip()}"
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"resident (?:context )?rot", line)
        ]
        assert not offenders, (
            "a governing document still justifies the wrap-up caps by the amount of "
            "'resident rot' a percentage-only threshold would allow. ADR-0033 narrowed "
            "that rationale (hard is now 400000; the objection was to ~550000) and "
            "upheld its cost half explicitly. Say what the cap is for now, or cite "
            "ADR-0033.\n  " + "\n  ".join(offenders)
        )

    def test_the_wrapup_skill_cites_a_governing_record_that_exists(self) -> None:
        # Regression, found by hand 2026-08-08: SKILL.md named "ADR-0018, Amendment
        # 2026-08-07" as its governing record. THAT AMENDMENT DOES NOT EXIST — it was
        # an in-place rewrite of an immutable ADR, and it was reverted, so the
        # citation pointed at deleted text. A severed citation is worse than none:
        # it reads as authority and cannot be followed.
        #
        # The governing record is ADR-0033. Asserted as: the page cites ADR-0033, the
        # cited file exists on disk, and the page does not present the phantom
        # amendment as live. The retirement note is allowed to NAME the bad citation
        # (that is how a downstream reader recognises a stale copy), so the check is
        # scoped to the "Governing record:" claim itself.
        text = (PROJECT_ROOT / _WRAPUP_SKILL).read_text(encoding="utf-8")
        assert (PROJECT_ROOT / _ADR_0033).is_file()
        claims = re.findall(r"Governing record:\s*\*\*(.+?)\*\*", text)
        assert claims, (
            f"{_WRAPUP_SKILL} states no `Governing record:` at all. The page describes "
            "thresholds a model acts on; it has to say which decision governs them."
        )
        for claim in claims:
            assert "ADR-0033" in claim, (
                f"{_WRAPUP_SKILL} names {claim!r} as the governing record. The "
                "governing record for the cap values is ADR-0033."
            )
            assert "Amendment 2026-08-07" not in claim, (
                f"{_WRAPUP_SKILL} cites a phantom amendment as governing: {claim!r}. "
                "ADR-0018 was reverted; that amendment does not exist."
            )
        # Prefer a stable anchor over a line number: a section title survives edits
        # above it, a line number does not.
        assert "docs/adr/ADR-0033-wrapup-cap-recalibration.md" in text
        assert not re.search(r"ADR-0033[^\n]*?:\d+", text), (
            "the wrap-up skill cites ADR-0033 by line number. Line numbers rot on the "
            "next edit; cite the section heading instead."
        )

    def test_every_section_anchor_the_skill_cites_resolves(self) -> None:
        # The completion of the test above. That one forbids citing ADR-0033 by LINE
        # NUMBER and says "cite the section heading instead" — but nothing checked
        # that a cited heading exists. A section anchor is only better than a line
        # number if it is verified; unverified, it fails the same way the phantom
        # "Amendment 2026-08-07" did, and reads as authority while pointing nowhere.
        #
        # Scoped to `§ *Title*` citations, the form the page uses. Matching is on the
        # heading TEXT, so re-levelling a heading (### -> ##) does not trip this, but
        # renaming or deleting one does — which is the failure worth catching.
        skill = (PROJECT_ROOT / _WRAPUP_SKILL).read_text(encoding="utf-8")
        adr = (PROJECT_ROOT / _ADR_0033).read_text(encoding="utf-8")
        headings = {line.lstrip("#").strip() for line in adr.splitlines() if line.startswith("#")}
        cited = [c.strip() for c in re.findall(r"§\s*\*([^*]+)\*", skill)]
        assert cited, (
            f"{_WRAPUP_SKILL} cites no ADR section by anchor at all. The test above "
            "requires section anchors over line numbers; if the page stopped using "
            "them, re-point this check rather than deleting it."
        )
        missing = [c for c in cited if c not in headings]
        assert not missing, (
            f"{_WRAPUP_SKILL} cites {len(missing)} ADR-0033 section(s) that do not "
            "exist. A severed anchor is the same defect as the phantom amendment: it "
            f"reads as authority and cannot be followed.\n  missing: {missing}"
        )

    def test_the_model_facing_skill_defers_to_the_config(self) -> None:
        # The skill is loaded by the wrap-up protocol itself. It must not become a
        # copy of the numbers that can rot independently — it must send the reader to
        # the config, which is the file the resolver actually reads.
        #
        # The follow-up this comment used to record as OWED is DISCHARGED. The page
        # named "ADR-0018, Amendment 2026-08-07" as its governing record and quoted
        # "Opus hard 500K"; both were stale, and both were fixed in the same effort —
        # the page now cites ADR-0033 by section anchor and states no cap value of its
        # own. `test_the_wrapup_skill_cites_a_governing_record_that_exists` is what
        # holds that fix in place. The assertion below is deliberately narrower than
        # that one and outlives it: whatever record governs, the page must send its
        # reader to the config rather than carry numbers that rot independently.
        text = (PROJECT_ROOT / _WRAPUP_SKILL).read_text(encoding="utf-8")
        assert re.search(r"ADR-00(18|33)", text), (
            "the wrap-up skill cites no decision record for the thresholds it describes"
        )
        assert "read the config" in text.lower(), (
            "the wrap-up skill must tell its reader to read "
            "config/model_context_profiles.yaml rather than infer a threshold from the "
            "page. Without that line, every number on the page is a live instruction "
            "that rots independently of the resolver."
        )


# ---------------------------------------------------------------------------
# Amendment 1 (2026-08-08): no documented quality cliff.
#
# The caps were justified by a third-party "effective working fraction ~= 50-65%
# of the window" band and a context-rot argument. The authoritative Anthropic
# reference contradicts the premise: for Claude Opus 5 it states a 1M-token
# context window as both the DEFAULT and the MAXIMUM, and that instruction
# following, tool calling and reasoning STAY STRONG ACROSS THE FULL WINDOW. No
# degradation threshold is published. The band is older and was measured on
# earlier model generations.
#
# So the rationale was wrong, not the number: the cap exists for COST and HANDOFF
# HEADROOM. These tests hold the retirement in place, because a retracted claim
# that nothing enforces grows back — the caps slice is itself the proof, having
# shipped a thorough rationale built entirely on the band.
# ---------------------------------------------------------------------------

#: The exact retirement marker every governing doc must carry. A POSITIVE
#: assertion on purpose: a negative grep goes green when someone deletes the whole
#: discussion, which is the failure mode that lets the claim quietly return.
_QUALITY_CLIFF_RETIREMENT = "RETIRED 2026-08-08: no documented quality cliff"

#: Phrases that only ever appear when the retired band is being used to JUSTIFY a
#: number. Deliberately narrow: the bare words "effective working fraction" and
#: "50-65%" also appear in legitimate *quotations* of ADR-0018's original research
#: note (which Principle #4 requires be quotable), so matching those would force
#: the history out of the record. These two idioms never occur in a quotation.
_BAND_JUSTIFICATION_IDIOMS = (
    "bottom edge of the researched",
    "effective-working-fraction band",
)


class TestNoQualityCliffClaimSurvives:
    """The cap is for cost and handoff headroom. No doc may say otherwise."""

    @pytest.mark.parametrize("rel", sorted(_GOVERNING_DOCS))
    def test_every_governing_doc_records_the_retirement(self, rel: str) -> None:
        path = PROJECT_ROOT / rel
        assert path.is_file(), f"{rel} is missing — this check would pass vacuously"
        assert _QUALITY_CLIFF_RETIREMENT in path.read_text(encoding="utf-8"), (
            f"{rel} no longer carries the marker {_QUALITY_CLIFF_RETIREMENT!r}. Every "
            "document that tells a reader what the wrap-up caps are for must say, in "
            "terms, that the quality justification was withdrawn — otherwise the next "
            "author re-derives it from the leftover framing. Anthropic publishes no "
            "degradation threshold and states capability holds across the full 1M "
            "window; the caps exist for cost and handoff headroom."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", sorted(_GOVERNING_DOCS))
    def test_no_governing_doc_justifies_a_cap_by_the_retired_band(self, rel: str) -> None:
        # Regression: `.claude/skills/wrapping-up-sessions/SKILL.md` justified the 1M
        # cap as "the bottom edge of the researched effective-working-fraction band".
        # That page is loaded by the wrap-up protocol itself, so the claim was not a
        # documentation nit — it was an instruction, and it was unsupported.
        #
        # A passage may still NAME the idiom while retiring it (that is how a reader
        # of a stale downstream copy recognises one), so the rule is: wherever the
        # idiom appears, the word RETIRED appears in the same paragraph.
        #
        # The unit is a PARAGRAPH, not a line, and that is load-bearing rather than
        # incidental: the first version of this check scoped to a line and fired on
        # ADR-0033's own retirement note purely because prose wrapping put "RETIRED"
        # one line above the idiom. A rule whose verdict depends on where a line
        # break falls produces false positives that get "fixed" by reflowing text,
        # which teaches the next author to reflow rather than to think.
        path = PROJECT_ROOT / rel
        assert path.is_file(), f"{rel} is missing — this check would pass vacuously"
        text = path.read_text(encoding="utf-8")
        offenders = []
        line_no = 1
        for para in re.split(r"\n\s*\n", text):
            if any(idiom in para for idiom in _BAND_JUSTIFICATION_IDIOMS):
                if "RETIRED" not in para:
                    offenders.append(f"{rel}:~{line_no}: {' '.join(para.split())[:160]}")
            line_no += para.count("\n") + 2
        assert not offenders, (
            "a governing document still uses the researched effective-working-fraction "
            "band to justify a cap value. That band is third-party, older, and measured "
            "on earlier model generations; the reference states capability holds across "
            "the full 1M window. Say the cap is for cost and handoff headroom, or mark "
            "the line RETIRED.\n  " + "\n  ".join(offenders)
        )

    @staticmethod
    def _stated_terms() -> dict[str, int]:
        """Parse the config's `TERMS` table (`NAME = VALUE`) out of the block."""
        block = TestCapRationaleIsRecorded._block()
        terms = {
            name: int(value)
            for name, value in re.findall(r"^#\s+([A-Z_]+)\s+=\s+(\d+)\b", block, re.MULTILINE)
        }
        assert terms, (
            "the CAP RECALIBRATION block states no `NAME = VALUE` terms. The 2026-08-08 "
            "re-anchoring replaced a prose justification with an arithmetic; if the "
            "arithmetic is gone, so is the only thing a reader can re-derive."
        )
        return terms

    def test_the_config_derivation_executes_to_the_live_caps(self) -> None:
        # STRENGTHENED 2026-08-08 after a mutation escaped. The first version of this
        # check asserted `str(150000) in block` — a bare grep. Measured: mutating the
        # `UNIT = 150000` term to `000000` left the suite fully green, because the
        # numeral 150000 still appeared elsewhere in the same block (in the prose that
        # weighs 1x/2x/3x). A grep proves a number was typed somewhere; it does not
        # prove the number is load-bearing.
        #
        # So the derivation is now EXECUTED: parse the stated terms, run the stated
        # arithmetic, and compare against what `resolve_threshold` actually computes.
        # The config, the anchor, and the resolver cannot come apart silently.
        terms = self._stated_terms()
        for required in ("UNIT", "HANDOFF", "RESERVE", "RUNWAY", "TIER_STEP"):
            assert required in terms, f"the block no longer states {required}: {terms}"

        assert terms["UNIT"] == _DOCUMENTED_COMPACTION_TRIGGER, (
            f"the config anchors on UNIT={terms['UNIT']}, but Anthropic's documented "
            f"server-side compaction default trigger is {_DOCUMENTED_COMPACTION_TRIGGER}. "
            "The whole point of the 2026-08-08 re-anchoring is that this number comes "
            "from a published document rather than a benchmark nobody here can rerun."
        )
        assert terms["RESERVE"] == HANDOFF_HEADROOM_TOKENS
        assert terms["TIER_STEP"] * 2 == terms["RUNWAY"]

        # The stated measured handoff cost must still bound the live measurement and
        # still fit the reserve — so growing BUILD_STATUS.md or the skill fails here.
        #
        # THE TWO SIDES ARE NOT THE SAME QUANTITY, and the message has to say so or
        # the next author "re-measures" the wrong thing. `live` is the four components
        # `_measured_handoff_cost_tokens()` reads off disk; stated `HANDOFF` is those
        # PLUS the measured-once ~1948-token BUILD_STATUS edit payload the config
        # itemizes. So this is the EARLIER of the two tripwires — it fires when the
        # live subtotal alone reaches the stated total, roughly 1948 tokens before
        # `TestHandoffHeadroomInvariant::test_measured_handoff_cost_still_fits_the_reserve`
        # fires at RESERVE. Both are deliberate; only the reserve is a hard floor.
        live = sum(_measured_handoff_cost_tokens().values())
        assert live <= terms["HANDOFF"] <= terms["RESERVE"], (
            f"the live handoff SUBTOTAL ({live} tokens: "
            f"{_measured_handoff_cost_tokens()}) has reached the stated HANDOFF TOTAL "
            f"({terms['HANDOFF']}, which also includes the measured-once ~1948-token "
            f"BUILD_STATUS edit payload), or that total no longer fits the reserve "
            f"({terms['RESERVE']}). This is the early tripwire, not the floor: "
            "re-measure and restate the itemization in the config and ADR-0033. Raising "
            "the RESERVE instead is a separate decision and requires re-checking the "
            "headroom of every profile."
        )
        assert terms["RUNWAY"] >= 4 * live, (
            f"RUNWAY={terms['RUNWAY']} is under 4x the measured handoff cost ({live}); "
            "the soft->hard gap no longer buys room to finish a step AND hand off."
        )

        # The arithmetic itself, against the resolver.
        expected = {
            "opus_1m": (2 * terms["UNIT"], 2 * terms["UNIT"] + terms["RUNWAY"]),
            "sonnet_1m": (
                2 * terms["UNIT"] - terms["TIER_STEP"],
                2 * terms["UNIT"] + terms["RUNWAY"] - terms["TIER_STEP"],
            ),
        }
        for name, (soft, hard) in expected.items():
            prof = _resolve_profile(name)
            assert (prof.soft_tok, prof.hard_tok) == (soft, hard), (
                f"the config's stated derivation produces {name} soft {soft} / hard "
                f"{hard}, but the resolver computes soft {prof.soft_tok} / hard "
                f"{prof.hard_tok}. The written arithmetic and the running arithmetic "
                "have come apart — which is the failure this block exists to prevent."
            )
        assert "cost" in TestCapRationaleIsRecorded._block().lower()

    def test_the_adr_states_the_same_terms_as_the_config(self) -> None:
        # Third leg of the binding. The cap VALUES are already checked against the ADR
        # by TestCapRationaleIsRecorded; the DERIVATION has to match too, or the ADR
        # can keep a retired anchor while the config moves to a new one.
        adr = _governing_adr_text()
        adr_terms = {
            name: int(value.replace(",", ""))
            for name, value in re.findall(r"^\|\s*`([A-Z_]+)`\s*\|\s*([\d,]+)\s*\|", adr, re.M)
        }
        config_terms = self._stated_terms()
        assert adr_terms, f"{_ADR_0033} states no derivation terms table"
        for name, value in adr_terms.items():
            assert config_terms.get(name) == value, (
                f"{_ADR_0033} says {name}={value}; the config says "
                f"{config_terms.get(name)}. The decision record and the live "
                "derivation disagree."
            )
        assert adr_terms.get("UNIT") == _DOCUMENTED_COMPACTION_TRIGGER


# ---------------------------------------------------------------------------
# ROUND 4: a total restated in three documents needs a test that READS THE
# DERIVATION, not one that compares two copies of the same claim.
#
# THE DEFECT. `HANDOFF` is stated in three places: the config's TERMS table, the
# config's own itemization sixty lines below it, and ADR-0033's derivation table.
# Round 3 added a third instalment (177 tok) to the SKILL.md component. It was
# written into the itemization and into the config's footnote prose, and into
# NEITHER total. Measured on disk: the config's TERMS table said `HANDOFF = 20391`
# while the itemization it is the sum of added to 20568 — one file, two answers for
# one measured quantity, sixty lines apart. The ADR said 20391 as well, but for a
# different reason: it was internally consistent and stale at the SOURCE, still
# itemizing the SKILL.md row at 8473 chars / 2420 tok for a file grown to 9091.
# A correct sum of a stale measurement, agreeing with a stale total.
#
# WHY THE SUITE WAS GREEN. `test_the_adr_states_the_same_terms_as_the_config`
# compares the ADR's terms table to the config's terms table. Both were stale in
# the same direction, so agreement held and the check passed — it proves the two
# documents were copied from each other, not that either is right. Nothing
# executed the itemization. The parallel is exact to
# `test_the_config_derivation_executes_to_the_live_caps`, which was strengthened
# for the same reason: a grep proves a number was typed, not that it is
# load-bearing.
#
# SO THIS CLASS ADDS THE COLUMN UP. It parses the `N chars -> M tok` lines out of
# both documents, runs the divisor the config documents (3.5 chars/token) on each
# one, sums them, and requires the result to equal every stated total — the
# config's `total ->` line, the config's `HANDOFF` term, the ADR's table, and the
# ADR's `HANDOFF` term. It does the same for the instalment enumeration, whose
# count word ("three") and amounts (636/72/177 tok) must agree with the stated
# spend (885). Re-stating a number consistently is no longer enough; the
# arithmetic underneath it has to close.
# ---------------------------------------------------------------------------

#: `[~Nx ]NNNN chars -> MMMM tok`, the config's itemized-line form. The optional
#: multiplier carries the `~2x 3409 chars` edit payload (old_string + new_string).
_ITEM_LINE_RE = re.compile(
    r"(?:~?\s*(\d+)\s*x\s+)?([\d,]+)\s*chars\s*->\s*([\d,]+)\s*tok\b", re.IGNORECASE
)
#: `\b` before `total` deliberately does NOT match inside `subtotal` (b|t is not a
#: word boundary), so these two never capture each other's line.
_SUBTOTAL_LINE_RE = re.compile(r"\bsubtotal\s*->\s*([\d,]+)\s*tok\b", re.IGNORECASE)
_TOTAL_LINE_RE = re.compile(r"\btotal\s*->\s*([\d,]+)\s*tok\b", re.IGNORECASE)

#: `\btok\b` excludes `tokens` by construction (`k`->`e` is no boundary), which is
#: what keeps "Margin ... is 4432 tokens" out of the instalment enumeration.
_TOK_AMOUNT_RE = re.compile(r"(\d[\d,]*)\s*tok\b", re.IGNORECASE)
_INSTALMENT_CLAIM_RE = re.compile(
    r"\bspent\s+([\d,]+)\s+of\s+it\s+in\s+([a-z]+)\s+instalments\b", re.IGNORECASE
)
_MARGIN_CLAIM_RE = re.compile(r"\bmargin\b[^.]{0,60}?\bis\s+([\d,]+)\s+tokens\b", re.IGNORECASE)
#: The config footnote's roll-up of the same instalments: `All three - 885 tok
#: together`. A second, independent enumeration of one quantity — which is exactly
#: why it needs reading (see `_instalment_site`). Any dash spelling is accepted so
#: the check does not become a hostage to em-dash vs hyphen.
_INSTALMENT_ROLLUP_RE = re.compile(
    r"\bAll\s+([a-z]+)\s*[—–-]\s*([\d,]+)\s*tok\s+together\b", re.IGNORECASE
)
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def _n(cell: str) -> int | None:
    """A markdown cell as an int, tolerating `**bold**`, backticks and a `~`."""
    match = re.fullmatch(r"[~*`\s]*([\d,]+)[~*`\s]*", cell)
    return int(match.group(1).replace(",", "")) if match else None


def _item_tokens(match: re.Match[str]) -> tuple[int, int, int]:
    """`(multiplier, chars, stated_tokens)` from one itemized line."""
    mult = int(match.group(1)) if match.group(1) else 1
    return mult, int(match.group(2).replace(",", "")), int(match.group(3).replace(",", ""))


def _divisor_errors(items: list[tuple[int, int, int]]) -> list[str]:
    """Lines whose stated token count is not `chars * multiplier / 3.5`, floored."""
    return [
        f"{mult}x {chars} chars / {_CHARS_PER_TOKEN} = "
        f"{int(mult * chars / _CHARS_PER_TOKEN)} tok, but the line states {tok} tok"
        for mult, chars, tok in items
        if int(mult * chars / _CHARS_PER_TOKEN) != tok
    ]


def _config_cost_block(text: str) -> str:
    """The config's `MEASURED HANDOFF COST` itemization, raw (line structure intact)."""
    match = re.search(
        r"^# MEASURED HANDOFF COST\b.*?(?=^# HEADROOM PER PROFILE\b)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, (
        "config/model_context_profiles.yaml no longer carries a `MEASURED HANDOFF COST` "
        "itemization ending at `HEADROOM PER PROFILE`. That itemization IS the derivation "
        "of the HANDOFF term; deleting it leaves the term an unsourced assertion in three "
        "documents, which is the defect this class exists to prevent."
    )
    return match.group(0)


def _config_itemization(block: str) -> dict[str, object]:
    """Split the config itemization into live components, payload, and its totals."""
    sub = _SUBTOTAL_LINE_RE.search(block)
    assert sub is not None, (
        "the config itemization no longer states a `live subtotal -> N tok` line. That "
        "line is what separates the four components `_measured_handoff_cost_tokens()` "
        "re-reads from the measured-once edit payload, and it is the earlier of the two "
        "growth tripwires. Restate it rather than deleting it."
    )
    head, tail = block[: sub.start()], block[sub.end() :]
    total = _TOTAL_LINE_RE.search(tail)
    assert total is not None, "the config itemization states no `total -> N tok` line"
    return {
        "live": [_item_tokens(m) for m in _ITEM_LINE_RE.finditer(head)],
        "payload": [_item_tokens(m) for m in _ITEM_LINE_RE.finditer(tail)],
        "subtotal": int(sub.group(1).replace(",", "")),
        "total": int(total.group(1).replace(",", "")),
    }


def _adr_cost_rows(text: str) -> list[list[str]]:
    """Rows of ADR-0033's `| Component | chars | tokens |` table.

    Anchored on that header rather than on "any markdown table": the same section
    also carries the headroom table, whose numeric columns would otherwise parse
    as components.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if cells == ["component", "chars", "tokens"]:
            rows = []
            for row in lines[i + 2 :]:
                if not row.strip().startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip().strip("|").split("|")])
            return rows
    return []


def _adr_itemization(text: str) -> dict[str, object]:
    """Classify the ADR's cost-table rows into components / subtotal / payload / total."""
    rows = _adr_cost_rows(text)
    assert rows, (
        f"{_ADR_0033} no longer carries a `| Component | chars | tokens |` table. It is "
        "the ADR-side copy of the derivation; without it the ADR states a HANDOFF total "
        "with nothing behind it."
    )
    out: dict[str, object] = {"components": [], "subtotal": None, "payload": None, "total": None}
    for cells in rows:
        label = re.sub(r"[*`]", "", cells[0]).strip().lower()
        tok = _n(cells[2]) if len(cells) > 2 else None
        if "subtotal" in label:
            out["subtotal"] = tok
        elif label == "total":
            out["total"] = tok
        elif "payload" in label:
            out["payload"] = tok
        else:
            chars = _n(cells[1]) if len(cells) > 1 else None
            if chars is not None and tok is not None:
                out["components"].append((1, chars, tok))  # type: ignore[union-attr]
    return out


def _instalment_site(scope: str) -> tuple[int | None, list[int], int | None, list[str]]:
    """Parse one instalment enumeration into `(count, amounts, stated_total, errors)`.

    TWO HEADER FORMS, because the file states the same three instalments twice in
    two different sentences and only one of them was ever read:

    * the **spend** form — ``spent 885 of it in three instalments`` — used by the
      config's `RESERVE` term and by ADR-0033's margin paragraph;
    * the **roll-up** form — ``All three - 885 tok together`` — used by the config's
      `MEASURED HANDOFF COST` footnote, sixty lines below the `RESERVE` term.

    The roll-up sentence states the SUM in the same ``N tok`` shape the instalments
    themselves use, so its span is removed before the instalments are harvested;
    otherwise the total would count itself as a fourth instalment.
    """
    claim = _INSTALMENT_CLAIM_RE.search(scope)
    rollup = _INSTALMENT_ROLLUP_RE.search(scope)
    if claim is None and rollup is None:
        return (
            None,
            [],
            None,
            [
                "no instalment header found — neither `spent N of it in <word> "
                "instalments` nor `All <word> - N tok together`. These sentences are "
                "the only place the amendment admits what it spent from the reserve; "
                "deleting one is not a way to make this pass."
            ],
        )
    if claim is not None:
        total, count_word = int(claim.group(1).replace(",", "")), claim.group(2)
    else:
        assert rollup is not None
        total, count_word = int(rollup.group(2).replace(",", "")), rollup.group(1)
    body = scope if rollup is None else scope[: rollup.start()] + scope[rollup.end() :]
    amounts = [int(a.replace(",", "")) for a in _TOK_AMOUNT_RE.findall(body)]
    count = _NUMBER_WORDS.get(count_word.lower())
    errors = []
    if count is None:
        errors.append(f"instalment count {count_word!r} is not a number word")
    elif len(amounts) != count:
        errors.append(
            f"the header says {count} instalments ({count_word}) but the text "
            f"enumerates {len(amounts)}: {amounts}"
        )
    if sum(amounts) != total:
        errors.append(f"the enumerated instalments {amounts} sum to {sum(amounts)}, not {total}")
    return count, amounts, total, errors


def _instalment_errors(scope: str) -> list[str]:
    """Does an instalment header agree with the enumeration next to it?"""
    return _instalment_site(scope)[3]


def _config_reserve_prose() -> str:
    """The `RESERVE` term's prose in the config TERMS table, unwrapped to one line."""
    match = re.search(
        r"^#\s+RESERVE\s+=.*?(?=^#\s+[A-Z_]+\s+=\s+\d|\Z)",
        TestCapRationaleIsRecorded._block(),
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "the config TERMS table no longer states a RESERVE term"
    return re.sub(r"\s+", " ", re.sub(r"\n\s*#\s?", " ", match.group(0))).strip()


def _adr_margin_paragraph() -> str:
    """ADR-0033's margin/instalment paragraph, markup stripped."""
    for para in _governing_adr_text().split("\n\n"):
        if _INSTALMENT_CLAIM_RE.search(re.sub(r"[*`]", "", para)):
            return re.sub(r"\s+", " ", re.sub(r"[*`]", "", para)).strip()
    return ""


def _config_instalment_footnote() -> str:
    """The config's SECOND enumeration of the instalments, unwrapped to one line.

    Scoped as *everything after the itemization's `total -> N tok` line*, up to the
    end of the `MEASURED HANDOFF COST` block. That is the whole footnote and nothing
    else, and the scope is structural rather than phrase-matched so re-wording the
    footnote cannot slide the enumeration out from under the check.

    THE COST OF THAT CHOICE, stated rather than discovered later: every `N tok`
    figure in this footnote is read as an instalment. A future author who wants to
    mention an unrelated token figure here will get a red test, not a silent pass —
    the safe direction, but they should move the figure or extend this parser rather
    than delete the enumeration.
    """
    block = _config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    total = _TOTAL_LINE_RE.search(block)
    assert total is not None, "the config itemization states no `total -> N tok` line"
    tail = block[total.end() :]
    return re.sub(r"\s+", " ", re.sub(r"\n\s*#\s?", " ", tail)).strip()


#: Every place the three instalments are enumerated. The round-4 defect lived in the
#: gap BETWEEN two of these: the config's `RESERVE` term said "708 in two" while its
#: own footnote sixty lines below listed three summing to 885. A per-site check is
#: blind to that by construction, so the sites are also compared against each other.
_INSTALMENT_SITES: dict[str, Callable[[], str]] = {
    "config RESERVE term": _config_reserve_prose,
    "config MEASURED HANDOFF COST footnote": _config_instalment_footnote,
    "ADR-0033 margin paragraph": _adr_margin_paragraph,
}

#: The config, as a path relative to the repo root — the form the document scans use.
_CONFIG_REL = "config/model_context_profiles.yaml"

#: The machine-read marker that distinguishes a figure that WAS the derived total
#: from one that IS. It must sit immediately after the numeral it retires; a
#: paragraph-wide marker was rejected because it would exempt the live figures
#: standing next to the historical one (ADR-0033's round-4 blockquote states both).
_SUPERSEDED_MARKER = "(SUPERSEDED)"

#: Markup, closing delimiters, comment/blockquote line prefixes and whitespace that
#: may separate a numeral from its marker. Bounded, so a marker further down the
#: paragraph cannot launder an unrelated figure.
_MARKER_TRAILER_RE = re.compile(r"^[`*_)\s>#]{0,24}\(SUPERSEDED\)")


def _derived_handoff_quantities() -> dict[str, int]:
    """The handoff figures the two documents restate, each DERIVED, never asserted.

    `total` and `subtotal` are read off the config's itemization — the same parse
    `TestHandoffCostDerivationIsSelfConsistent` sums — so every restatement is
    compared against the arithmetic rather than against another copy of the claim.
    `rounded` is the `~20600` form the prose uses when it wants a round number for
    the same quantity.
    """
    item = _config_itemization(_config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")))
    total = int(item["total"])  # type: ignore[arg-type]
    return {
        "total": total,
        "subtotal": int(item["subtotal"]),  # type: ignore[arg-type]
        "rounded": int(round(total, -2)),
        "reserve": HANDOFF_HEADROOM_TOKENS,
    }


def _restatement_band() -> tuple[int, int]:
    """The numeric neighbourhood in which a figure is read as restating the total.

    +/-10% of the derived figures. The failure mode being guarded is STALENESS, and a
    stale figure is by construction close to the one that replaced it — 20391 against
    20568, 18371 against 18620. A figure far outside this band is not a stale copy of
    the total; the named-site table below is what holds those.
    """
    values = [v for k, v in _derived_handoff_quantities().items() if k != "reserve"]
    return int(min(values) * 0.9), int(max(values) * 1.1)


def _unbound_restatements(rel: str) -> list[str]:
    """Figures near the derived total that neither equal it nor carry the marker."""
    path = PROJECT_ROOT / rel
    assert path.is_file(), f"{rel} is missing — this scan would pass vacuously"
    text = path.read_text(encoding="utf-8")
    allowed = set(_derived_handoff_quantities().values())
    low, high = _restatement_band()
    offenders = []
    for match in re.finditer(r"\b\d[\d,]*\b", text):
        value = int(match.group(0).replace(",", ""))
        if not low <= value <= high or value in allowed:
            continue
        if _MARKER_TRAILER_RE.match(text[match.end() :]):
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        line = text.splitlines()[line_no - 1].strip()
        offenders.append(f"{rel}:{line_no}: {value} — {line[:120]}")
    return offenders


#: Prose restatements of a derived handoff figure, by site. Each pattern runs over
#: the document with markup stripped and whitespace collapsed; each capture group
#: must equal the quantity named beside it. PRESENCE IS REQUIRED, so deleting a
#: restatement is not a way to pass — the deletion-as-a-fix escape the rest of this
#: module already closes everywhere else.
_RESTATEMENT_CLAIMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (_CONFIG_REL, r"the binding comparison: ([\d,]+) against", ("total",)),
    (_CONFIG_REL, r"HANDOFF total of ([\d,]+) \(currently ([\d,]+)", ("total", "subtotal")),
    (_ADR_0033, r"HANDOFF total of ([\d,]+) \(currently ([\d,]+)", ("total", "subtotal")),
    (_ADR_0033, r"At ([\d,]+) the bounds still hold", ("total",)),
    (_ADR_0033, r"and ([\d,]+) still fits inside the ([\d,]+) RESERVE", ("total", "reserve")),
    (_ADR_0033, r"is [\d.]+x the ([\d,]+) live subtotal", ("subtotal",)),
)

#: Ratios stated in prose that are DIVISIONS of two figures these documents already
#: define. Each entry: (document, pattern capturing the stated ratio, numerator TERM
#: from the config's TERMS table, denominator key from `_derived_handoff_quantities`).
#: Bound the same way the tightest-profile `1.26x HANDOFF` ratio already is — the
#: test performs the division rather than matching a literal, so the ratio cannot
#: keep an old denominator after the denominator moves.
_RATIO_CLAIMS: tuple[tuple[str, str, str, str], ...] = (
    (_CONFIG_REL, r"RUNWAY = [\d,]+ soft->hard gap\. ([\d.]+)x HANDOFF", "RUNWAY", "total"),
    (_ADR_0033, r"soft→hard gap; ([\d.]+)x HANDOFF", "RUNWAY", "total"),
    (_ADR_0033, r"RUNWAY [\d,]+ is ([\d.]+)x the [\d,]+ live subtotal", "RUNWAY", "subtotal"),
    (_ADR_0033, r"live subtotal and ([\d.]+)x HANDOFF", "RUNWAY", "total"),
)


def _flat_document(rel: str) -> str:
    """A document with comment/blockquote prefixes and markup stripped, one line.

    The claims above wrap across comment lines and blockquote lines, so matching them
    on raw text would make every check a hostage to where the line breaks fall — the
    same trap `test_no_governing_doc_justifies_a_cap_by_the_retired_band` records
    having fallen into once already.
    """
    text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    prefix = r"^[ \t]*#[ \t]?" if rel.endswith((".yaml", ".yml")) else r"^[ \t]*>[ \t]?"
    text = re.sub(prefix, "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", re.sub(r"[`*]", "", text)).strip()


class TestHandoffCostDerivationIsSelfConsistent:
    """The itemization must ADD UP to every total stated from it, in both documents.

    WHAT THIS CANNOT CATCH — stated so the next reader does not over-trust it:

    * **It does not verify the snapshot against disk.** The itemized char counts
      are a dated snapshot by design; `BUILD_STATUS.md` changes every session, so
      asserting equality with the live measurement would go red on ordinary work.
      Live drift is covered by the two existing tripwires
      (`test_the_config_derivation_executes_to_the_live_caps` at `HANDOFF`, and
      `test_measured_handoff_cost_still_fits_the_reserve` at `RESERVE`). This
      class covers the other axis: internal arithmetic, which those cannot see.
    * **It cannot tell a correct measurement from a self-consistent wrong one.**
      Someone who edits the itemization AND every total together passes here. What
      it forbids is exactly what happened: refreshing one and not the others.
    * **It reads two documents, not the four derived projects** that receive the
      config by propagation.
    """

    # -- the config's own arithmetic ------------------------------------------

    @staticmethod
    def _config() -> dict[str, object]:
        return _config_itemization(
            _config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        )

    def test_the_configs_itemization_sums_to_the_total_it_states(self) -> None:
        # THE DEFECT, executed. Measured 2026-08-08 before this fix: the components
        # summed to 20568 and the file's TERMS table said HANDOFF = 20391.
        item = self._config()
        live: list[tuple[int, int, int]] = item["live"]  # type: ignore[assignment]
        payload: list[tuple[int, int, int]] = item["payload"]  # type: ignore[assignment]
        assert len(live) >= 4, f"only {len(live)} live components itemized: {live}"
        assert payload, "the edit-payload line is gone from the itemization"
        assert sum(t for _, _, t in live) == item["subtotal"], (
            f"the config's live components sum to {sum(t for _, _, t in live)} tokens "
            f"but its `live subtotal` line states {item['subtotal']}. The itemization is "
            "the derivation; a subtotal that is not the sum of the lines above it is a "
            "second, contradicting source of truth."
        )
        stated_total = sum(t for _, _, t in live + payload)
        assert stated_total == item["total"], (
            f"the config itemizes {stated_total} tokens but states `total -> "
            f"{item['total']} tok`. Refresh the total when you refresh a component — "
            "restating it in one place and not the other is the drift this test exists "
            "to catch."
        )

    def test_every_itemized_line_executes_the_stated_divisor(self) -> None:
        # The chars->tokens conversion is documented in the same block (3.5
        # chars/token, chosen below the lowest observed BPE ratio). Documented and
        # unexecuted is how a number goes stale, so it is executed here.
        item = self._config()
        block = _config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        assert f"{_CHARS_PER_TOKEN} chars/token" in block, (
            "the itemization no longer states the divisor it converts with. Without it "
            "the chars column and the tokens column are two unrelated assertions."
        )
        errors = _divisor_errors(item["live"] + item["payload"])  # type: ignore[operator]
        assert not errors, (
            "itemized lines that do not execute the stated divisor:\n  " + "\n  ".join(errors)
        )

    def test_the_configs_itemized_total_is_its_own_handoff_term(self) -> None:
        # The seam that actually broke: the TERMS table and the itemization it
        # summarizes are sixty lines apart in one file, and only one was refreshed.
        terms = TestNoQualityCliffClaimSurvives._stated_terms()
        total = self._config()["total"]
        assert terms["HANDOFF"] == total, (
            f"the config's TERMS table states HANDOFF = {terms['HANDOFF']} while its own "
            f"itemization sixty lines below totals {total}. One file, two answers for one "
            "measured quantity. HANDOFF is DEFINED as the sum of that itemization — "
            "re-derive it rather than picking whichever number reads better."
        )

    def test_the_configs_live_subtotal_covers_exactly_the_re_measured_components(self) -> None:
        # The subtotal is the early tripwire's left-hand side, so the prose must
        # itemize exactly the components `_measured_handoff_cost_tokens()` re-reads.
        # If a fifth live component is ever added to one and not the other, the
        # tripwire silently starts comparing different quantities.
        live: list[tuple[int, int, int]] = self._config()["live"]  # type: ignore[assignment]
        assert len(live) == len(_measured_handoff_cost_tokens()), (
            f"the config itemizes {len(live)} live components but "
            f"`_measured_handoff_cost_tokens()` re-measures "
            f"{len(_measured_handoff_cost_tokens())}: {list(_measured_handoff_cost_tokens())}. "
            "The `live subtotal` line and the early tripwire must describe the same set."
        )

    # -- the ADR's copy of the same arithmetic --------------------------------

    def test_the_adrs_itemization_sums_to_the_totals_it_states(self) -> None:
        item = _adr_itemization(_governing_adr_text())
        components: list[tuple[int, int, int]] = item["components"]  # type: ignore[assignment]
        assert len(components) >= 4, f"{_ADR_0033} itemizes only {len(components)} components"
        for key in ("subtotal", "payload", "total"):
            assert item[key] is not None, f"{_ADR_0033}'s cost table states no {key} row"
        assert sum(t for _, _, t in components) == item["subtotal"], (
            f"{_ADR_0033}'s components sum to {sum(t for _, _, t in components)} but its "
            f"live-measured subtotal row says {item['subtotal']}."
        )
        assert item["subtotal"] + item["payload"] == item["total"], (  # type: ignore[operator]
            f"{_ADR_0033} states subtotal {item['subtotal']} + payload {item['payload']} "
            f"but a total of {item['total']}."
        )
        errors = _divisor_errors(components)
        assert not errors, f"{_ADR_0033} rows that do not execute the divisor:\n  " + "\n  ".join(
            errors
        )

    def test_the_adrs_itemized_total_is_its_own_handoff_term(self) -> None:
        adr = _governing_adr_text()
        terms = {
            name: int(value.replace(",", ""))
            for name, value in re.findall(r"^\|\s*`([A-Z_]+)`\s*\|\s*([\d,]+)\s*\|", adr, re.M)
        }
        total = _adr_itemization(adr)["total"]
        assert terms.get("HANDOFF") == total, (
            f"{_ADR_0033}'s terms table states HANDOFF = {terms.get('HANDOFF')} while its "
            f"own itemization totals {total}."
        )

    def test_the_adr_and_the_config_itemize_the_same_measurement(self) -> None:
        # The pre-existing terms-table comparison passed while BOTH documents were
        # stale. This compares the DERIVATIONS, so a document can no longer agree
        # with the other about a number neither of them derived.
        cfg = self._config()
        adr = _adr_itemization(_governing_adr_text())
        assert sorted((c, t) for _, c, t in cfg["live"]) == sorted(  # type: ignore[union-attr]
            (c, t)
            for _, c, t in adr["components"]  # type: ignore[union-attr]
        ), (
            f"the config itemizes {sorted((c, t) for _, c, t in cfg['live'])} and "  # type: ignore[union-attr]
            f"{_ADR_0033} itemizes {sorted((c, t) for _, c, t in adr['components'])}. "  # type: ignore[union-attr]
            "Same measurement, two component lists."
        )
        assert (cfg["subtotal"], cfg["total"]) == (adr["subtotal"], adr["total"]), (
            f"config subtotal/total {(cfg['subtotal'], cfg['total'])} vs {_ADR_0033} "
            f"{(adr['subtotal'], adr['total'])}."
        )

    # -- the instalment enumeration and the margin ----------------------------

    @pytest.mark.parametrize("where", sorted(_INSTALMENT_SITES))
    def test_the_instalment_enumeration_matches_its_stated_count_and_sum(self, where: str) -> None:
        # WHAT THIS LEG COVERS, stated accurately after round 4's own comment was
        # measured and found to over-claim. It checks ONE enumeration against the
        # header sentence standing next to it: a count word and a sum are both claims
        # about the list beside them, so "three instalments: 636, 72, 177" summing to
        # 885 has to close. That is an INTRA-SITE property.
        #
        # It is NOT the shipped defect. The shipped defect straddled two sites — the
        # config's `RESERVE` term said "SPENT 708 ... in two instalments" while the
        # footnote sixty lines below listed three summing to 885 — and each half was
        # internally consistent, so no per-site check could see it. That is
        # `test_every_site_enumerates_the_same_instalments`, below, and the previous
        # version of this comment claimed this test's coverage was the former when
        # measured it was only the latter. Prose outrunning its own measurement,
        # inside the guard written to stop prose outrunning its own measurement.
        #
        # The third site — the config footnote — was outside every scope this class
        # read until round 4's follow-up; `_INSTALMENT_SITES` is now what this
        # parametrization enumerates, so adding a site adds coverage automatically.
        scope = _INSTALMENT_SITES[where]()
        assert scope, f"no instalment enumeration found in the {where}"
        errors = _instalment_errors(scope)
        assert not errors, (
            f"the {where}'s instalment header disagrees with its own enumeration:\n  "
            + "\n  ".join(errors)
            + f"\n  scope: {scope[:400]}"
        )

    def test_every_site_enumerates_the_same_instalments(self) -> None:
        # THE SHIPPED DEFECT, executed. One quantity, three enumerations, in two
        # documents; round 4 refreshed some and not others and every intra-site check
        # stayed green because each half was self-consistent. Agreement between the
        # sites is the property that was actually violated, so it is the property
        # asserted here — order-insensitively, because the ADR lists the instalments
        # in a different order (72, 177, 636) than the config does (636, 72, 177).
        parsed = {}
        for label, source in _INSTALMENT_SITES.items():
            scope = source()
            assert scope, f"no instalment enumeration found in the {label}"
            count, amounts, total, _ = _instalment_site(scope)
            parsed[label] = (count, tuple(sorted(amounts)), total)
        distinct = set(parsed.values())
        assert len(distinct) == 1, (
            "the instalment enumerations disagree ACROSS sites. Each may be internally "
            "consistent and they still cannot all be right — this is the shape of the "
            "defect that shipped:\n  "
            + "\n  ".join(
                f"{label}: count={c} amounts={a} total={t}" for label, (c, a, t) in parsed.items()
            )
        )

    @pytest.mark.parametrize("where", ("config", "adr"))
    def test_the_stated_margin_is_the_reserve_minus_the_handoff_total(self, where: str) -> None:
        scope = _config_reserve_prose() if where == "config" else _adr_margin_paragraph()
        claim = _MARGIN_CLAIM_RE.search(scope)
        assert claim is not None, f"the {where} no longer states the margin over HANDOFF"
        terms = TestNoQualityCliffClaimSurvives._stated_terms()
        expected = terms["RESERVE"] - terms["HANDOFF"]
        assert int(claim.group(1).replace(",", "")) == expected, (
            f"the {where} states a margin of {claim.group(1)} tokens, but RESERVE "
            f"{terms['RESERVE']} - HANDOFF {terms['HANDOFF']} = {expected}. The margin is "
            "a subtraction, not an independent claim."
        )

    # -- teeth: each check must go red on a de-synced copy ---------------------

    def test_a_de_synced_total_is_caught(self) -> None:
        # Reproduces the shipped defect exactly: components refreshed, total not.
        block = _config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        item = _config_itemization(block)
        stale = block.replace(
            f"total -> {item['total']} tok",
            f"total -> {int(item['total']) - 177} tok",  # type: ignore[arg-type]
        )
        assert stale != block, "the total-line splice anchor has moved"
        mutant = _config_itemization(stale)
        assert (
            sum(t for _, _, t in mutant["live"] + mutant["payload"])  # type: ignore[operator]
            != mutant["total"]
        ), (
            "a total 177 tokens below its own itemization reads as consistent; the sum "
            "check is asleep"
        )

    def test_a_de_synced_component_is_caught(self) -> None:
        # The other direction: a component grows and the total is left behind.
        block = _config_cost_block(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        item = _config_itemization(block)
        _mult, chars, tok = item["live"][0]  # type: ignore[index]
        grown = block.replace(f"{chars} chars ->  {tok} tok", f"{chars} chars ->  {tok + 500} tok")
        assert grown != block, "the component-line splice anchor has moved"
        mutant = _config_itemization(grown)
        assert sum(t for _, _, t in mutant["live"]) != mutant["subtotal"], (
            "a component 500 tokens larger than the subtotal above it reads as consistent"
        )

    def test_a_component_line_that_misapplies_the_divisor_is_caught(self) -> None:
        assert _divisor_errors([(1, 9091, 2597)]) == []
        assert _divisor_errors([(1, 9091, 2420)]), (
            "a line stating the PREVIOUS token count for a grown file passes the divisor "
            "check. That is precisely the stale row this class exists to catch."
        )
        assert _divisor_errors([(1, 3409, 1948)]), (
            "the divisor check ignores the 2x multiplier on the edit-payload line"
        )
        assert _divisor_errors([(2, 3409, 1948)]) == []

    @pytest.mark.parametrize(
        ("mutation", "why"),
        (
            (
                "spent 885 of it in two instalments: 636 tok, 72 tok, and 177 tok",
                "count word behind the enumeration (the shipped defect)",
            ),
            (
                "spent 708 of it in three instalments: 636 tok, 72 tok, and 177 tok",
                "stated spend behind the enumeration (the other shipped half)",
            ),
            (
                "spent 885 of it in three instalments: 636 tok and 72 tok",
                "an instalment dropped from the enumeration",
            ),
            (
                "The margin is 4432 tokens and nothing was spent.",
                "the claim deleted rather than corrected",
            ),
            # The ROLL-UP header form, which the footnote uses and which nothing read
            # before round 4's follow-up. Same three failures, other sentence shape.
            (
                "grew by 636 tok, by 72 tok and by 177 tok. All three — 708 tok together.",
                "roll-up total behind its own enumeration",
            ),
            (
                "grew by 636 tok and by 72 tok. All three — 885 tok together.",
                "an instalment dropped from the roll-up enumeration",
            ),
            (
                "grew by 636 tok, by 72 tok and by 177 tok. All two — 885 tok together.",
                "roll-up count word behind its enumeration",
            ),
            (
                "The SKILL.md line above grew by 636 tok and by 72 tok and by 177 tok.",
                "the roll-up sentence deleted rather than corrected",
            ),
        ),
    )
    def test_the_instalment_check_fires_on_a_de_synced_enumeration(
        self, mutation: str, why: str
    ) -> None:
        assert _instalment_errors(mutation), f"the instalment check is blind to: {why}"

    @pytest.mark.parametrize(
        "consistent",
        (
            "spent 885 of it in three instalments: 636 tok, 72 tok, 177 tok",
            "grew by 636 tok, by 72 tok and by 177 tok more. All three — 885 tok together.",
        ),
    )
    def test_the_instalment_check_passes_a_consistent_enumeration(self, consistent: str) -> None:
        # The complement — a check no correct text can satisfy is not a check. Both
        # header forms must have a passing case, or the roll-up leg is just a tripwire.
        assert _instalment_errors(consistent) == []

    def test_the_roll_up_total_is_not_counted_as_a_fourth_instalment(self) -> None:
        # The parsing hazard the footnote creates: its total is stated in the same
        # `N tok` shape as the instalments. If the roll-up span were not removed
        # first, the correct footnote would read as four instalments summing to 1770
        # and this whole leg would be a permanent false red — which is how a check
        # gets "fixed" by deleting it.
        _count, amounts, total, errors = _instalment_site(
            "grew by 636 tok, by 72 tok and by 177 tok more. All three — 885 tok together."
        )
        assert (amounts, total, errors) == ([636, 72, 177], 885, [])

    def test_the_cross_site_check_fires_on_the_defect_that_shipped(self) -> None:
        # G1, executed as a unit rather than against the file: the RESERVE term is
        # rewound to the two-instalment wording while the footnote keeps three. Each
        # site is internally consistent; only the comparison between them is red.
        rewound = "spent 708 of it in two instalments: 636 tok and 72 tok"
        footnote = "grew by 636 tok, by 72 tok and by 177 tok more. All three — 885 tok together."
        assert _instalment_errors(rewound) == [], (
            "the rewound wording is supposed to be INTRA-site consistent — if it is not, "
            "this test is not demonstrating the cross-site gap it claims to"
        )
        assert _instalment_errors(footnote) == []
        left, right = _instalment_site(rewound), _instalment_site(footnote)
        assert (left[0], sorted(left[1]), left[2]) != (right[0], sorted(right[1]), right[2]), (
            "two sites disagreeing by a whole instalment read as agreement; the "
            "cross-site check guards nothing"
        )

    def test_the_cross_document_check_fires_when_only_one_document_is_refreshed(self) -> None:
        # The exact shape of the shipped defect, at the cross-document seam: the
        # config's itemization is refreshed and the ADR's is not. The pre-existing
        # terms-table comparison could not see this, because both terms tables were
        # stale together and therefore agreed.
        text = _governing_adr_text()
        live = _adr_itemization(text)
        stale = text.replace(
            f"| **live-measured subtotal** | | **{live['subtotal']}** |",
            f"| **live-measured subtotal** | | **{int(live['subtotal']) - 177}** |",  # type: ignore[arg-type]
        )
        assert stale != text, "the ADR subtotal splice anchor has moved"
        mutant = _adr_itemization(stale)
        cfg = self._config()
        assert cfg["subtotal"] != mutant["subtotal"], (
            "a 177-token de-sync between the two documents' derivations reads as "
            "agreement; the cross-document check guards nothing."
        )
        assert mutant["subtotal"] + mutant["payload"] != mutant["total"], (  # type: ignore[operator]
            "the ADR's own subtotal + payload still equals its total after the splice, "
            "so the intra-document check would not have caught it either."
        )


# ---------------------------------------------------------------------------
# ROUND 4 FOLLOW-UP: the itemization->total leg was solid; the RESTATEMENTS were
# not. `TestHandoffCostDerivationIsSelfConsistent` reads the itemization, the two
# TERMS tables and the two totals — but the derived total is restated in SEVEN more
# places across the same two files, and every one of them was a free literal.
#
# MEASURED before this class existed, by mutating a scratch mirror and running the
# full suite: rewinding `the binding comparison: 20568` to 20391 (config), the
# `HANDOFF total of 20568` tripwire prose to 20391 (config AND ADR), `At 20568 the
# bounds still hold` to 20391 (ADR), and `5.4x the 18620 live subtotal` to 18371
# (ADR) each left the suite GREEN. So did moving `4.9x HANDOFF` to `9.9x` in both
# documents. Nine mutations, nine passes.
#
# THE RULE THIS CLASS INSTALLS. A figure in these two documents that sits in the
# neighbourhood of the derived total is one of exactly two things, and the document
# has to say which:
#   * it IS the total (or the live subtotal, or the total rounded) — then it must
#     equal what the itemization computes; or
#   * it WAS the total — then it carries `(SUPERSEDED)` immediately after it.
# The marker is READ, not trusted to convention: a reader-honoured "this paragraph
# is historical" would have exempted the live 20568 standing two words from the
# stale 20391 in ADR-0033's own round-4 blockquote.
#
# And every ratio derived from the total is DIVIDED here rather than matched
# against a literal — the same treatment `1.26x HANDOFF` already got, extended to
# the `4.9x HANDOFF` and `5.4x the live subtotal` claims that were left behind.
# ---------------------------------------------------------------------------


class TestEveryRestatementOfTheDerivedTotalIsBound:
    """No free literal for a quantity the itemization already derives.

    WHAT THIS CANNOT CATCH — named, because the class exists to stop a guard from
    over-claiming its own reach:

    * **It is a staleness guard, not a plausibility guard.** The band is +/-10% of
      the derived figures, because a stale copy of a number is always near the number
      that replaced it. Someone who rewrites a restatement to 90000 escapes the scan
      — and is caught instead by `_RESTATEMENT_CLAIMS`, which pins the named sites by
      value regardless of distance. The two legs cover each other; neither alone is
      enough.
    * **A marked figure is exempt at that figure only.** `(SUPERSEDED)` must follow
      the numeral it retires, so it cannot launder its neighbours — but it does mean
      a *wrong* historical figure passes. History is not re-derivable; the marker
      claims only "this was once stated", which is a claim about the record.
    * **It reads two documents.** `.claude/skills/wrapping-up-sessions/SKILL.md`
      carries no handoff totals today (measured: no in-band figure), and the four
      derived projects that receive this config by propagation are not scanned.
    * **The ratio leg binds the HANDOFF-derived ratios only.** The headroom tables'
      `17.2x` / `19.2x` / `1.04x` / `1.44x` columns are divisions by `RESERVE`, not
      by `HANDOFF`, and are still free literals in both documents. That is a real
      remaining gap, stated rather than implied by silence.
    """

    @pytest.mark.parametrize("rel", (_CONFIG_REL, _ADR_0033))
    def test_no_figure_near_the_total_is_both_wrong_and_unmarked(self, rel: str) -> None:
        low, high = _restatement_band()
        derived = _derived_handoff_quantities()
        offenders = _unbound_restatements(rel)
        assert not offenders, (
            f"figures in the band [{low}, {high}] that neither equal a derived quantity "
            f"({derived}) nor carry the {_SUPERSEDED_MARKER} marker immediately after "
            "them. Either re-derive the figure from the itemization, or mark it as "
            "history — the point of the marker is that a reader can tell which of the "
            "two a number is without doing the arithmetic themselves:\n  " + "\n  ".join(offenders)
        )

    @pytest.mark.parametrize(
        ("rel", "pattern", "keys"), _RESTATEMENT_CLAIMS, ids=lambda v: str(v)[:40]
    )
    def test_each_named_restatement_states_the_derived_figure(
        self, rel: str, pattern: str, keys: tuple[str, ...]
    ) -> None:
        derived = _derived_handoff_quantities()
        match = re.search(pattern, _flat_document(rel))
        assert match is not None, (
            f"{rel} no longer states the restatement matched by {pattern!r}. These "
            "sentences are how a reader meets the number away from the derivation "
            "table; deleting one is not a way to make this pass."
        )
        stated = tuple(int(g.replace(",", "")) for g in match.groups())
        expected = tuple(derived[k] for k in keys)
        assert stated == expected, (
            f"{rel} restates {dict(zip(keys, stated, strict=True))} where the "
            f"itemization derives {dict(zip(keys, expected, strict=True))}. One quantity, "
            "two answers — the defect of round 4, in a sentence the derivation checks "
            "never looked at."
        )

    @pytest.mark.parametrize(
        ("rel", "pattern", "numerator", "denominator"), _RATIO_CLAIMS, ids=lambda v: str(v)[:40]
    )
    def test_each_stated_ratio_is_a_division_the_test_performs(
        self, rel: str, pattern: str, numerator: str, denominator: str
    ) -> None:
        # Same treatment as
        # `test_the_adrs_stated_handoff_ratio_is_computed_against_its_own_defined_term`,
        # extended to the ratios that were left as free literals. A ratio whose
        # denominator moves and whose value does not is how 1.42x got into the ADR.
        match = re.search(pattern, _flat_document(rel))
        assert match is not None, (
            f"{rel} no longer states the ratio matched by {pattern!r}. It is what tells "
            "a reader the soft->hard runway is wide enough to finish a step AND hand "
            "off; deleting it is not a way to make this pass."
        )
        stated_text = match.group(1)
        top = TestNoQualityCliffClaimSurvives._stated_terms()[numerator]
        bottom = _derived_handoff_quantities()[denominator]
        # Compared at the precision the document itself states, so this is an equality
        # rather than a tolerance: "4.9" must be 100000/20568 = 4.8619 rounded to one
        # decimal, and 4.8 or 5.0 are both wrong.
        places = len(stated_text.partition(".")[2])
        assert float(stated_text) == pytest.approx(round(top / bottom, places), abs=1e-9), (
            f"{rel} states {stated_text}x, but {numerator} {top} / {denominator} "
            f"{bottom} = {top / bottom:.4f}, i.e. {round(top / bottom, places)}x at the "
            "precision the document uses. The ratio is a division, not an independent "
            "claim, and it has to be re-divided when either side moves."
        )

    # -- teeth ----------------------------------------------------------------

    def test_a_stale_figure_is_caught_and_a_marked_one_is_not(self) -> None:
        # The scan, exercised as a unit on synthetic text so it does not depend on
        # the current wording of either document.
        low, _high = _restatement_band()
        derived = _derived_handoff_quantities()
        stale = derived["total"] - 177
        assert low <= stale, "the band no longer covers a one-instalment-stale total"
        assert not _MARKER_TRAILER_RE.match(" against sonnet_200k's headroom"), (
            "an unmarked figure reads as marked; the scan would exempt everything"
        )
        for trailer in (
            f" {_SUPERSEDED_MARKER}",
            f"` {_SUPERSEDED_MARKER}",
            f"** {_SUPERSEDED_MARKER}",
        ):
            assert _MARKER_TRAILER_RE.match(trailer), (
                f"the marker is not recognised through {trailer!r}, so marking a "
                "historical figure inside markup would produce a permanent false red"
            )
        far = f" {'.' * 40}{_SUPERSEDED_MARKER}"
        assert not _MARKER_TRAILER_RE.match(far), (
            "a marker 40 characters downstream still exempts the numeral; the marker "
            "must attach to the figure it retires, not to its paragraph"
        )

    def test_the_scan_is_not_vacuous_on_the_documents_it_reads(self) -> None:
        # A scan that finds no in-band figures at all would pass on an empty file.
        # This proves both documents actually contain figures the scan inspected.
        low, high = _restatement_band()
        for rel in (_CONFIG_REL, _ADR_0033):
            text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
            hits = [
                int(m.group(0).replace(",", ""))
                for m in re.finditer(r"\b\d[\d,]*\b", text)
                if low <= int(m.group(0).replace(",", "")) <= high
            ]
            assert len(hits) >= 3, f"{rel} carries only {hits} in the band — scan is vacuous"

    def test_the_marker_actually_appears_where_history_is_recorded(self) -> None:
        # The complement of the scan: if nothing in either document were marked, the
        # scan would be passing because the documents state no history — and the
        # round-4 record, which is mostly history, would have been quietly deleted.
        marked = sum(
            (PROJECT_ROOT / rel).read_text(encoding="utf-8").count(_SUPERSEDED_MARKER)
            for rel in (_CONFIG_REL, _ADR_0033)
        )
        assert marked >= 4, (
            f"only {marked} {_SUPERSEDED_MARKER} markers across both documents. Round 4 "
            "superseded a total in one file and a total plus a subtotal in the other; "
            "if the markers are gone, so is the record of what the numbers used to be."
        )


# ---------------------------------------------------------------------------
# The config's own cost claim must equal what the config actually computes.
#
# The defect this slice fixes was invisible because a fail-safe default is silent.
# The FIRST correction of the fix was wrong for the same species of reason: the
# config asserted the defect cost "a ~5x premature handoff", reasoning from the
# 1M/200K window ratio instead of measuring. The absolute caps bind before the
# percentage does, so the realised correction was ~1.4x at the time and is ~4.0x
# after the 2026-08-07 cap recalibration — the point being that it is a MEASURED
# quantity that moves when the caps move, not the window ratio. A prose number that
# nothing executes is exactly as silent as a default that nothing reports, so the
# numbers in that block are bound to the resolver here rather than to a reviewer's
# attention. See ADR-0032's third correction.
# ---------------------------------------------------------------------------


class TestConfigCostClaimIsMeasured:
    """Every number in the config's MEASURED COST block must be reproducible."""

    @staticmethod
    def _block() -> str:
        """The MEASURED COST comment block, unwrapped to one whitespace-normal line.

        The claims wrap across comment lines, so matching them on the raw text would
        make the test a hostage to where the line breaks fall.
        """
        text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        match = re.search(r"# MEASURED COST\b.*?(?=\n\s*#\s*\n)", text, re.DOTALL)
        assert match is not None, (
            "config/model_context_profiles.yaml no longer contains a `MEASURED COST` "
            "block. The defect cost figure must stay in the file AND stay checkable — "
            "deleting it is not a way to make this test pass."
        )
        unwrapped = re.sub(r"\n\s*#\s?", " ", match.group(0))
        return re.sub(r"\s+", " ", unwrapped).strip()

    @staticmethod
    def _floor_and_fixed() -> tuple[ThresholdProfile, ThresholdProfile]:
        """The pre-fix (defaulted) profile and the post-fix profile for the live id."""
        cfg = load_config()
        return resolve_threshold("totally-unknown-xyz", cfg), resolve_threshold(
            "claude-opus-5[1m]", cfg
        )

    @pytest.mark.regression
    def test_stated_threshold_transitions_match_the_resolver(self) -> None:
        # Regression: the block claimed a cost derived from the window ratio rather
        # than from these numbers. `soft A -> B` / `hard A -> B` must be the actual
        # floor -> fixed transition.
        floor, fixed = self._floor_and_fixed()
        block = self._block()
        expected = {
            "soft": (floor.soft_tok, fixed.soft_tok),
            "hard": (floor.hard_tok, fixed.hard_tok),
        }
        found = {
            kind: (int(before), int(after))
            for kind, before, after in re.findall(r"\b(soft|hard) (\d+) -> (\d+)", block)
        }
        assert found.keys() == expected.keys(), (
            f"the MEASURED COST block must state both a `soft A -> B` and a "
            f"`hard A -> B` transition; found {sorted(found)} in: {block}"
        )
        assert found == expected, (
            f"config claims {found}, resolver computes {expected}. The block's job is "
            "to report the measured correction, not one reasoned from the window ratio."
        )

    @pytest.mark.regression
    def test_stated_ratio_matches_the_computed_ratio(self) -> None:
        # Regression: "~5x" was the window ratio, not the threshold ratio.
        floor, fixed = self._floor_and_fixed()
        claimed = re.search(r"~([\d.]+)x", self._block())
        assert claimed is not None, "the MEASURED COST block states no ~Nx ratio"
        assert float(claimed.group(1)) == pytest.approx(
            fixed.soft_tok / floor.soft_tok, abs=0.05
        ), (
            f"config claims ~{claimed.group(1)}x; measured soft ratio is "
            f"{fixed.soft_tok / floor.soft_tok:.2f}x"
        )

    def test_stated_token_gain_matches_the_computed_delta(self) -> None:
        floor, fixed = self._floor_and_fixed()
        claimed = re.search(r"~(\d+) tokens of usable context per session", self._block())
        assert claimed is not None, "the MEASURED COST block states no per-session token gain"
        assert int(claimed.group(1)) == fixed.soft_tok - floor.soft_tok

    def test_the_window_ratio_is_labelled_as_the_wrong_basis(self) -> None:
        # The block keeps the window-ratio number so a reader sees WHY the old figure
        # was wrong; that number must itself be right, and must not be presented as
        # the handoff cost.
        floor, fixed = self._floor_and_fixed()
        block = self._block()
        claimed = re.search(r"NOT the (\d+)x the 1M/200K window ratio", block)
        assert claimed is not None, "the block must say the window ratio is NOT the cost"
        assert int(claimed.group(1)) == fixed.context_window // floor.context_window
        assert not re.search(
            r"~?\d+x premature", DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        ), "an unmeasured '~Nx premature ...' cost claim is back in the config"


class TestResolutionVisibility:
    """The defaulted state must be audible — silence is what hid ADR-0031."""

    @staticmethod
    def _prof(name: str, window: int, resolution: str) -> ThresholdProfile:
        return ThresholdProfile(name, window, 100, 200, 830, "m", True, resolution, "m")

    def test_window_disagreement_flags_the_live_pathology(self) -> None:
        # The exact state found on disk 2026-08-07: harness reported a 1M window,
        # the resolved profile assumed 200K, and nothing compared the two.
        occ = Occupancy(60000, 6.0, 1_000_000, "statusline", "claude-fable-5[1m]")
        assert window_disagreement(occ, self._prof("haiku_200k", 200000, RESOLUTION_DEFAULT))
        assert not window_disagreement(occ, self._prof("opus_1m", 1_000_000, RESOLUTION_EXACT))

    def test_transcript_estimate_source_is_not_flagged(self) -> None:
        # occ.window is derived FROM the profile there, so a comparison is vacuous.
        occ = Occupancy(500, 0.25, 200000, "transcript-estimate", "x")
        assert not window_disagreement(occ, self._prof("opus_1m", 1_000_000, RESOLUTION_EXACT))

    @pytest.mark.regression
    def test_sidecar_records_resolution_provenance(self, tmp_path: Path) -> None:
        # Regression: the sidecar recorded tier/soft_tok but nothing saying whether
        # the tier was CHOSEN or DEFAULTED, so a 10%-of-window soft threshold sat
        # on disk unremarked.
        payload = _make_statusline_json(model="claude-fable-5[1m]", session_id="sess-norm")
        process_statusline(payload, state_dir=tmp_path)
        path = sidecar_path("sess-norm", tmp_path)
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["resolution"] == RESOLUTION_NORMALIZED
        assert data["matched"] is True
        assert data["resolved_model_id"] == "claude-fable-5"
        assert data["tier"] == "opus_1m"
        assert data["soft_tok"] == _RECALIBRATED_CAPS["opus_1m"][0]
        assert data["profile_window"] == 1_000_000
        assert data["window_mismatch"] is False

    def test_sidecar_flags_a_defaulted_tier_against_a_larger_window(self, tmp_path: Path) -> None:
        payload = _make_statusline_json(model="who-knows-5[9x]", session_id="sess-unk")
        process_statusline(payload, state_dir=tmp_path)
        path = sidecar_path("sess-unk", tmp_path)
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["resolution"] == RESOLUTION_DEFAULT
        assert data["matched"] is False
        assert data["resolved_model_id"] is None
        assert data["window_mismatch"] is True  # 1M reported vs 200K assumed

    @pytest.mark.parametrize(
        ("model", "window", "expected"),
        [
            ("claude-opus-4-7", 1_000_000, "opus_1m"),  # exact, agreeing -> bare
            ("claude-fable-5[1m]", 1_000_000, "opus_1m~"),  # normalized
            ("who-knows-5[9x]", 200000, "haiku_200k?"),  # defaulted, agreeing
            ("who-knows-5[9x]", 1_000_000, "haiku_200k!"),  # defaulted + mismatch
        ],
    )
    def test_status_line_marks_how_the_tier_was_chosen(
        self, tmp_path: Path, model: str, window: int, expected: str
    ) -> None:
        line = process_statusline(
            _make_statusline_json(model=model, window=window, used_percentage=5.0),
            state_dir=tmp_path,
        )
        assert expected in line
        line.encode("cp1252")  # markers stay ASCII (see the cp1252 regression above)


# ---------------------------------------------------------------------------
# AC-2 / AC-2b: statusLine parsing + session-id allowlist.
# ---------------------------------------------------------------------------


class TestOccupancyFromStatusline:
    def test_valid_percentage_payload(self) -> None:
        occ = occupancy_from_statusline(_make_statusline_json(used_percentage=14.0))
        assert occ is not None
        assert occ.used_tokens == 140000
        assert occ.source == "statusline"
        assert occ.model == "claude-opus-4-7"

    def test_total_input_tokens_path(self) -> None:
        occ = occupancy_from_statusline(
            _make_statusline_json(used_percentage=None, total_input_tokens=50000, window=200000)
        )
        assert occ is not None and occ.used_tokens == 50000
        assert occ.used_percentage == pytest.approx(25.0)

    def test_model_as_object(self) -> None:
        payload = _make_statusline_json(model={"id": "claude-sonnet-4-6", "display_name": "x"})
        occ = occupancy_from_statusline(payload)
        assert occ is not None and occ.model == "claude-sonnet-4-6"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"context_window": {}},
            {"context_window": {"context_window_size": 200000, "used_percentage": None}},
            {"context_window": {"used_percentage": 50.0}},  # no window
        ],
    )
    def test_missing_fields_degrade_to_none(self, payload: dict) -> None:
        assert occupancy_from_statusline(payload) is None


class TestSessionIdValidation:
    @pytest.mark.parametrize(
        "value",
        ["../../etc/passwd", "", "a" * 65, None, 123, "has space", "semi;colon", "a/b"],
    )
    def test_invalid_ids_rejected(self, value: object) -> None:
        assert is_valid_session_id(value) is False

    @pytest.mark.parametrize("value", ["abc", "Sess-123_x", "A" * 64])
    def test_valid_ids_accepted(self, value: str) -> None:
        assert is_valid_session_id(value) is True

    def test_sidecar_path_none_for_invalid_id(self, tmp_path: Path) -> None:
        assert sidecar_path("../evil", tmp_path) is None

    def test_write_sidecar_rejects_invalid_id(self, tmp_path: Path) -> None:
        assert write_sidecar_atomic({"session_id": "../evil", "used_tokens": 1}, tmp_path) is None


# ---------------------------------------------------------------------------
# AC-3 / AC-3b: transcript fallback + sidecar freshness boundary.
# ---------------------------------------------------------------------------


class TestEstimateFromTranscript:
    def test_records_seam_sums_resident_tokens(self) -> None:
        rec = _make_record(input_tokens=1000, cache_read_tokens=500, cache_create_tokens=200)
        occ = estimate_from_transcript(records=[rec])
        assert occ is not None
        assert occ.used_tokens == 1700
        assert occ.source == "transcript-estimate"

    def test_picks_newest_record(self) -> None:
        old = _make_record(input_tokens=100, ts=datetime(2026, 5, 23, 10, 0, tzinfo=UTC))
        new = _make_record(input_tokens=900, ts=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
        occ = estimate_from_transcript(records=[old, new])
        assert occ is not None and occ.used_tokens == 900

    def test_empty_records_returns_none(self) -> None:
        assert estimate_from_transcript(records=[]) is None

    def test_all_unusable_records_returns_none(self) -> None:
        rec = _make_record(input_tokens=None, cache_read_tokens=None, cache_create_tokens=None)
        assert estimate_from_transcript(records=[rec]) is None

    def test_unknown_model_uses_conservative_window(self) -> None:
        rec = _make_record(
            input_tokens=500, cache_read_tokens=0, cache_create_tokens=0, model=None
        )
        occ = estimate_from_transcript(records=[rec], config=load_config())
        assert occ is not None
        # Conservative floor profile is the 200K window.
        assert occ.window == 200000

    def test_fixture_file_outside_projects_root_parses(self, tmp_path: Path) -> None:
        # Reuses the parse seam directly, bypassing the projects-root guard.
        line = json.dumps(
            {
                "message": {
                    "id": "msg_1",
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 4242},
                },
                "timestamp": "2026-05-23T12:00:00Z",
            }
        )
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(line + "\n", encoding="utf-8")
        occ = estimate_from_transcript(transcript)
        assert occ is not None and occ.used_tokens == 4242

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert estimate_from_transcript(tmp_path / "nope.jsonl") is None


class TestReadSidecarFreshness:
    def _write(self, tmp_path: Path, written_at: float) -> None:
        path = sidecar_path("sess", tmp_path)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"used_tokens": 5, "written_at_epoch": written_at}), "utf-8")

    def test_fresh_just_inside_window(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300 + 1)
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is not None

    def test_stale_just_outside_window(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300 - 1)
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is None

    def test_exact_boundary_is_fresh(self, tmp_path: Path) -> None:
        now = 1_000_000.0
        self._write(tmp_path, now - 300)  # strict '>' means exactly-at is fresh
        assert read_sidecar("sess", tmp_path, now=now, freshness_seconds=300) is not None

    def test_missing_sidecar_returns_none(self, tmp_path: Path) -> None:
        assert read_sidecar("sess", tmp_path) is None

    def test_corrupt_sidecar_returns_none(self, tmp_path: Path) -> None:
        path = sidecar_path("sess", tmp_path)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert read_sidecar("sess", tmp_path) is None


# ---------------------------------------------------------------------------
# Sidecar round-trip via process_statusline (the writer entry point).
# ---------------------------------------------------------------------------


class TestProcessStatusline:
    def test_writes_sidecar_and_returns_display(self, tmp_path: Path) -> None:
        payload = _make_statusline_json(used_percentage=14.0, session_id="sess1")
        line = process_statusline(payload, state_dir=tmp_path)
        assert "ctx" in line
        path = sidecar_path("sess1", tmp_path)
        assert path is not None and path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source"] == "statusline"
        assert data["tier"] == "opus_1m"
        assert (data["soft_tok"], data["hard_tok"]) == _RECALIBRATED_CAPS["opus_1m"]

    def test_missing_fields_no_sidecar(self, tmp_path: Path) -> None:
        line = process_statusline({}, state_dir=tmp_path)
        assert line == "ctx ?"
        assert not any(tmp_path.glob("context-occupancy.*.json"))

    def test_warn_marker_above_soft(self, tmp_path: Path) -> None:
        # 45% of the 1M window = 450000 >= the recalibrated soft cap of 300000.
        # This used to read 20% (200000), which cleared the old 140000 soft cap —
        # i.e. the assertion itself encoded the pre-recalibration behaviour.
        line = process_statusline(_make_statusline_json(used_percentage=45.0), state_dir=tmp_path)
        assert "wrap-up" in line

    def test_no_warn_marker_at_the_occupancy_that_used_to_trip_it(self, tmp_path: Path) -> None:
        # 20% of a 1M window is 200000 tokens: below soft (300000) after the
        # recalibration, so the status line must NOT advertise a wrap-up there.
        line = process_statusline(_make_statusline_json(used_percentage=20.0), state_dir=tmp_path)
        assert "wrap-up" not in line

    @pytest.mark.regression
    def test_display_is_ascii_encodable(self, tmp_path: Path) -> None:
        # Regression: statusLine prints to a raw terminal that may use cp1252;
        # a non-ASCII char (e.g. emoji) crashed the hook with UnicodeEncodeError.
        for pct in (5.0, 20.0, 60.0):
            line = process_statusline(
                _make_statusline_json(used_percentage=pct), state_dir=tmp_path
            )
            line.encode("cp1252")  # must not raise
        process_statusline({}, state_dir=tmp_path).encode("cp1252")


# ---------------------------------------------------------------------------
# AC-4: classify_level boundaries + the debounced guard state machine.
# ---------------------------------------------------------------------------


class TestClassifyLevel:
    @staticmethod
    def _prof() -> ThresholdProfile:
        return ThresholdProfile("p", 1000, 100, 200, 830, "m", True)

    @staticmethod
    def _occ(used: int) -> Occupancy:
        return Occupancy(used, used / 10.0, 1000, "statusline", "m")

    def test_just_below_soft(self) -> None:
        assert classify_level(self._occ(99), self._prof()) is None

    def test_at_soft_inclusive(self) -> None:
        assert classify_level(self._occ(100), self._prof()) == "soft"

    def test_just_above_soft(self) -> None:
        assert classify_level(self._occ(101), self._prof()) == "soft"

    def test_just_below_hard(self) -> None:
        assert classify_level(self._occ(199), self._prof()) == "soft"

    def test_at_hard_inclusive(self) -> None:
        assert classify_level(self._occ(200), self._prof()) == "hard"


class TestEvaluateGuardStateMachine:
    def test_four_step_soft_debounce_and_rearm(self, tmp_path: Path) -> None:
        sid = "sess-sm"
        # 1. soft zone -> fires. This step USED to assert the nudge carried the
        # occupancy (120) and the soft threshold (100) — the original AC-4/B-QA-7
        # requirement. That requirement is withdrawn by ADR-0033's 2026-08-08
        # amendment: injecting a budget countdown into the model's context is a
        # documented cause of premature wrap-up. The state machine is unchanged and
        # still under test here; only what the nudge SAYS changed. The figure-free
        # property has its own class, TestModelFacingNudgeCarriesNoFigures.
        _write_sidecar(tmp_path, sid, 120)
        first = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "soft" in first["additionalContext"]
        assert "`/handoff`" in first["additionalContext"]
        # 2. still soft -> silent.
        _write_sidecar(tmp_path, sid, 130)
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        # 3. drops below soft -> silent, flags cleared (re-arm).
        _write_sidecar(tmp_path, sid, 50)
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        # 4. back into soft -> fires again.
        _write_sidecar(tmp_path, sid, 140)
        again = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "additionalContext" in again

    def test_hard_fires_once_and_sets_both_flags(self, tmp_path: Path) -> None:
        sid = "sess-hard"
        _write_sidecar(tmp_path, sid, 250)
        out = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        # The level is still distinguishable (it drives what the model does next);
        # the occupancy 250 and threshold 200 it used to carry are gone by design —
        # see TestModelFacingNudgeCarriesNoFigures and ADR-0033 (2026-08-08).
        assert "HARD" in out["additionalContext"]
        assert "Stop starting new work" in out["additionalContext"]
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        assert (tmp_path / f"context-guard-armed.{sid}").exists()
        assert (tmp_path / f"context-guard-hard.{sid}").exists()

    def test_soft_then_hard_escalates(self, tmp_path: Path) -> None:
        sid = "sess-esc"
        _write_sidecar(tmp_path, sid, 120)
        evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        _write_sidecar(tmp_path, sid, 250)
        out = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        assert "HARD" in out["additionalContext"]

    def test_hard_then_soft_zone_silent(self, tmp_path: Path) -> None:
        sid = "sess-desc"
        _write_sidecar(tmp_path, sid, 250)
        evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        _write_sidecar(tmp_path, sid, 150)  # soft zone, soft flag already set
        assert evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG) == {}

    def test_session_isolation(self, tmp_path: Path) -> None:
        _write_sidecar(tmp_path, "sess-a", 120)  # soft
        _write_sidecar(tmp_path, "sess-b", 10)  # below soft
        assert "additionalContext" in evaluate_guard(
            {"session_id": "sess-a"}, state_dir=tmp_path, config=TINY_CONFIG
        )
        assert (
            evaluate_guard({"session_id": "sess-b"}, state_dir=tmp_path, config=TINY_CONFIG) == {}
        )

    def test_invalid_session_id_no_signal_silent(self, tmp_path: Path) -> None:
        # No session_id, no transcript_path, project_root with no transcripts -> silence.
        out = evaluate_guard({}, state_dir=tmp_path, config=TINY_CONFIG, project_root=tmp_path)
        assert out == {}
        assert not any(tmp_path.glob("context-guard-*"))


# ---------------------------------------------------------------------------
# Amendment 2 (2026-08-08): the model must not be shown a context countdown.
#
# THE DEFECT. The UserPromptSubmit guard injected a budget countdown into the
# MODEL's context on every prompt. Measured 2026-08-08 by piping a real payload
# through `.claude/hooks/context_guard.py`, a 1M session at 65% received:
#   "Context HARD wrap-up: ~651,312 tokens (~65% of the opus_1m window; hard
#    threshold 400,000). ... before context degrades / auto-compaction."
# Three budget figures plus a degradation claim, every turn.
#
# WHY THAT IS A DEFECT AND NOT A FEATURE. The authoritative Anthropic reference
# names this exact pattern as a CAUSE of the behaviour the machinery exists to
# prevent, twice: "surfacing remaining-token counts to the model can cause
# premature wrap-up behavior; avoid showing them where possible", and, for
# long-running agents, "it can worry about running out of context — suggesting a
# new session or trimming its own work — most often when the harness surfaces a
# remaining-token countdown. Avoid showing explicit context-budget counts."
#
# WHAT WAS KEPT. The checkpoint itself, at both levels. Deleting the nudge was the
# other option and was rejected: a session that is never told to checkpoint dies
# without a handoff and the thread is lost, which is the worse failure. The
# documentation objects to the countdown, not to being told to checkpoint.
#
# The pair of assertions below is the point. (a) alone could be satisfied by
# gutting the feature; (b) alone could be satisfied by leaving the countdown in.
# Together they pin the split: the human keeps the instrument, the model does not
# get a countdown.
# ---------------------------------------------------------------------------


class TestModelFacingNudgeCarriesNoFigures:
    """No digit may reach the model; every digit must still reach the developer."""

    #: Occupancies spanning below-soft, exactly-soft, mid, exactly-hard, and far
    #: past hard. The old text embedded `used_tokens` verbatim, so any of these
    #: would have leaked a distinct figure.
    _OCCUPANCIES = (99, 100, 150, 199, 200, 250, 900, 100_000)

    @pytest.mark.regression
    @pytest.mark.parametrize("used", _OCCUPANCIES)
    def test_injected_text_contains_no_digit_at_any_occupancy(
        self, tmp_path: Path, used: int
    ) -> None:
        sid = f"sess-nofig{used}"
        _write_sidecar(tmp_path, sid, used)
        out = evaluate_guard({"session_id": sid}, state_dir=tmp_path, config=TINY_CONFIG)
        text = out.get("additionalContext", "")
        leaked = re.findall(r"\d[\d,]*", text)
        assert not leaked, (
            f"the model-facing nudge leaked {leaked} at occupancy {used}. Surfacing a "
            "remaining-token count to the model is a documented cause of premature "
            "wrap-up (ADR-0033, 2026-08-08). The numbers belong on the developer's "
            f"status line. Text was: {text!r}"
        )

    def test_the_checkpoint_instruction_survives_at_both_levels(self) -> None:
        # De-numbering must not have quietly deleted the mechanism. A session that is
        # never told to checkpoint loses the thread — the harm this system exists to
        # prevent, and the reason "emit nothing" was rejected.
        for level in ("soft", "hard"):
            text = _nudge_text(level)
            assert "wrapping-up-sessions" in text and "/handoff" in text, (
                f"the {level} nudge no longer tells the model to write a handoff. "
                "Removing the countdown was the goal; removing the checkpoint was not."
            )
        assert "Stop starting new work" in _nudge_text("hard")
        assert _nudge_text("soft") != _nudge_text("hard")

    def test_the_nudge_does_not_claim_quality_is_degrading(self) -> None:
        # Amendment 1 reaching the model-facing text: the old nudges said "before
        # context degrades" / "before quality degrades". Anthropic publishes no
        # degradation threshold and states capability holds across the full window,
        # so those clauses asserted something unsupported — to the one reader who
        # cannot check it.
        for level in ("soft", "hard"):
            text = _nudge_text(level).lower()
            assert "degrad" not in text, f"the {level} nudge still claims degradation: {text!r}"
            # The reference's own recommended mitigation for context anxiety. The
            # clause must survive in SOME form or a bare "wrap up now" still reads as
            # scarcity pressure; which form is constrained by the test below.
            assert "reserved" in text, (
                f"the {level} nudge dropped its reassurance clause. Without one, a bare "
                "'wrap up now' reads as scarcity pressure — the very behaviour this "
                "amendment exists to stop."
            )

    @pytest.mark.regression
    def test_the_reassurance_is_true_on_the_tightest_profile_not_just_on_1m(self) -> None:
        # REGRESSION, 2026-08-08 (found reviewing this amendment, not by a user).
        #
        # THE DEFECT. The first version of this de-numbered nudge reassured the model
        # "Context remaining is ample - ... not because you are running out of room",
        # and told it "do not trim your work, shorten your answers, or suggest a new
        # session on account of context". That was justified from opus_1m alone, which
        # leaves 430000 tokens (17.2x the reserve) above its hard cap. But `_nudge_text`
        # is PROFILE-INDEPENDENT: the identical sentence goes to every profile.
        # Measured by piping a real payload through the two hooks, a `sonnet_200k`
        # session at 141K/200K -- 26000 tokens below the auto-compaction backstop,
        # 1.04x the reserve -- received exactly that sentence. The claim was false for
        # half the profiles this config defines, and false in the dangerous direction:
        # it tells the session nearest the mechanical floor to keep spending. ADR-0033
        # had the counter-evidence in its own headroom table ("`sonnet_200k` clears the
        # handoff reserve by 1000 tokens") while the nudge asserted the opposite.
        #
        # THE RULE THIS PINS. A constant emitted to every profile may only assert what
        # holds at the TIGHTEST profile. So the wording moved off "how much window is
        # left" (profile-dependent, false at 200K) and onto "room to write the handoff
        # is reserved" (guaranteed for every profile by TestHandoffHeadroomInvariant).
        # This test checks the claim's truth CONDITION, so adding a profile with too
        # little headroom fails here naming the nudge -- not just in the headroom class.
        live = sum(_measured_handoff_cost_tokens().values())
        for level in ("soft", "hard"):
            assert "reserved" in _nudge_text(level)
            assert "ample" not in _nudge_text(level).lower(), (
                f"the {level} nudge again claims remaining context is 'ample'. That is "
                "a claim about the window, and this text is emitted to every profile — "
                "it is false at sonnet_200k, which sits 1.04x the reserve from the "
                "auto-compaction backstop. Say what is reserved, not what is left."
            )
        tightest = min(
            (_resolve_profile(name) for name in _profile_names()),
            key=lambda p: p.auto_compact_tok - p.hard_tok,
        )
        headroom = tightest.auto_compact_tok - tightest.hard_tok
        assert headroom >= live, (
            f"the tightest profile ({tightest.profile_name}) leaves {headroom} tokens "
            f"between its hard nudge and auto-compaction, but writing one handoff "
            f"measures {live}. The model-facing nudge tells EVERY profile that room to "
            "write the handoff in full is reserved; on this one that is now a lie. "
            "Either restore the headroom or stop making the promise."
        )

    @pytest.mark.parametrize("used", _OCCUPANCIES)
    def test_the_developer_facing_status_line_still_carries_the_numbers(
        self, tmp_path: Path, used: int
    ) -> None:
        # The other half, and the reason this is not just a deletion. Fixing the
        # model-facing leak by blinding the developer would satisfy the assertion
        # above and destroy the only surface where a mis-resolved profile is visible.
        #
        # The assertion is on the SPECIFIC readouts, not on "contains a digit".
        # Measured 2026-08-08: a `re.search(r"\d", line)` version of this test passed
        # against a mutant that deleted the entire occupancy segment
        # (`ctx 65% | 651K/1000K |`) and kept only the static `soft 300K hard 400K`
        # tail — i.e. it would have green-lit blinding the developer to how full the
        # window actually is, which is exactly the thing this test exists to forbid.
        window = 1_000_000
        line = process_statusline(
            _make_statusline_json(used_percentage=used / 10_000, window=window),
            state_dir=tmp_path,
        )
        prof = resolve_threshold("claude-opus-4-7", load_config())
        required = {
            "occupancy %": f"{used / 10_000:.0f}%",
            "used/window": f"{used // 1000}K/{window // 1000}K",
            "soft threshold": f"soft {prof.soft_tok // 1000}K",
            "hard threshold": f"hard {prof.hard_tok // 1000}K",
        }
        missing = [f"{k} ({v!r})" for k, v in required.items() if v not in line]
        assert not missing, (
            f"the developer-facing status line lost {', '.join(missing)}. The "
            "2026-08-08 amendment removed figures from the MODEL's context only; the "
            "human keeps the instrument, and the occupancy readout is the only place a "
            f"mis-resolved profile is visible. Line was: {line!r}"
        )

    @pytest.mark.parametrize(
        ("model", "window", "pct", "expected"),
        [
            (
                "claude-opus-4-7",
                1_000_000,
                65.1312,
                "ctx 65% | 651K/1000K | opus_1m | soft 300K hard 400K [wrap-up]",
            ),
            (
                "claude-opus-5[1m]",
                1_000_000,
                65.1312,
                "ctx 65% | 651K/1000K | opus_1m~ | soft 300K hard 400K [wrap-up]",
            ),
            (
                "who-knows-9",
                1_000_000,
                65.1312,
                "ctx 65% | 651K/1000K | haiku_200k! | soft 100K hard 130K [wrap-up]",
            ),
            (
                "claude-sonnet-4-5",
                200_000,
                70.5,
                "ctx 70% | 141K/200K | sonnet_200k | soft 110K hard 140K [wrap-up]",
            ),
        ],
    )
    def test_the_status_line_reproduces_the_readings_the_records_quote(
        self, tmp_path: Path, model: str, window: int, pct: float, expected: str
    ) -> None:
        # The test above parametrizes occupancies that render as `ctx 0% | 0K/1000K`
        # for seven of its eight cases (measured), so it pins the SHAPE of the readout
        # far better than any VALUE. These cases pin values, and they are the exact
        # readings ADR-0033 and the two hook docstrings quote as measured — the three
        # resolution markers (exact / `~` normalized / `!` window-disagreement) and the
        # 200K reading behind the regression above. Prose that quotes a measured line
        # and code that emits it now cannot drift apart. A `context_statusline.py`
        # docstring showed a `~` against an input that resolves EXACTLY, which is the
        # specific drift this case set catches.
        line = process_statusline(
            _make_statusline_json(used_percentage=pct, window=window, model=model),
            state_dir=tmp_path,
        )
        assert line == expected, (
            "the developer-facing status line no longer reproduces the reading the "
            f"records quote as measured.\n  expected: {expected!r}\n  actual:   {line!r}"
        )

    def test_nudge_text_takes_no_data_to_interpolate(self) -> None:
        # Structural guard. `_nudge_text` used to take (level, occ, profile) and
        # formatted values out of both. It now takes only the level, so restoring a
        # figure requires changing the signature and every call site — a deliberate
        # act rather than an f-string edit that reads as harmless.
        params = list(inspect.signature(_nudge_text).parameters)
        assert params == ["level"], (
            f"_nudge_text now accepts {params}. Passing occupancy or a threshold back "
            "into it is how the countdown returns. Keep it a constant lookup."
        )


# ---------------------------------------------------------------------------
# Amendment 2, SECOND SURFACE: the wrap-up PROTOCOL must not order the recital.
#
# THE DEFECT, found in round 3 of this slice. De-numbering `_nudge_text` removed
# the figure from what the model is HANDED. It did not remove it from what the
# model is TOLD TO GO AND SAY. `.claude/skills/wrapping-up-sessions/SKILL.md` —
# the page the nudge sends the model to, and the page this same amendment had
# already edited — still opened its protocol with:
#
#     1. **Announce + choose.** State the trigger (`soft|hard`, profile, ~tokens).
#
# roughly ten lines under its own new warning against exactly that. It fires at
# the one moment the amendment exists to protect (the wrap-up itself), and it is
# worse than the guard's countdown was, because obeying it requires the model to
# go LOOK THE NUMBER UP. The skill is CORE and propagates verbatim to four
# derived projects.
#
# WHY A NEW TEST CLASS RATHER THAN ONE MORE ASSERTION. The suite already had
# `test_the_wrapup_skill_cites_a_governing_record_that_exists` — a point fix for
# the PREVIOUS defect on this same page (a severed ADR citation). Nothing read
# the page's INSTRUCTIONS at all, so the class of defect ("model-facing prose
# ordering behaviour the amendment forbids") was unguarded while one instance of
# it was pinned. A literal grep for "~tokens" would repeat that mistake one
# rewording later, so the detector below works by verb-and-term.
#
# Only SKILL.md is scanned. ADR-0033 and this file must be able to QUOTE the
# deleted instruction verbatim (both do, immediately above) or the record of the
# defect becomes unwritable — the same reason `_GOVERNING_DOCS` excludes ADR-0018.
# ---------------------------------------------------------------------------

#: Idioms that name a context-occupancy figure. Matching is on WORDS, never on
#: bare digits: the page legitimately contains `ADR-0033`, `1M`, and a retention
#: cap, and a digit-grep here would be noise the next author learns to ignore.
_FIGURE_TERM_RE = re.compile(
    r"~?\s*\d[\d,]*\s*(?:k\b|tokens?\b)"  # "~651,312 tokens", "300K"
    r"|\btokens?\b"
    r"|\bpercent(?:age)?\b|%"
    r"|\boccupanc\w*\b"
    r"|\bcountdown\b|\breadout\b"
    r"|\bfigures?\b|\bnumbers?\b|\bcounts?\b"
    r"|\bbudget\b|\bremaining\b"
    r"|how (?:full|much (?:context|room|window))",
    re.IGNORECASE,
)

#: Verbs that put something into output a human reads. Base forms only, matched
#: at the head of a sentence (imperative) or after an obligation word — so the
#: page can still describe the defect in the indicative ("Surfacing a
#: remaining-token count ... is a documented cause of premature wrap-up") without
#: tripping the check.
_EMIT_VERBS = (
    "state announce report surface include say print show display quote recite give note "
    "add list tell mention echo declare cite output emit relay share name carry write record "
    "append"
).split()

_EMIT_ALTERNATION = "|".join(_EMIT_VERBS)
_IMPERATIVE_EMIT_RE = re.compile(rf"^(?:{_EMIT_ALTERNATION})\b", re.IGNORECASE)
_OBLIGATION_EMIT_RE = re.compile(
    r"\b(?:must|should|shall|always|be sure to|make sure to|remember to|has to|have to)\s+"
    rf"(?:\w+\s+){{0,3}}?(?:{_EMIT_ALTERNATION})\b",
    re.IGNORECASE,
)

#: A sentence that mentions a figure is allowed iff it is forbidding one.
_PROHIBITION_RE = re.compile(
    r"\b(?:no|not|never|nor|without|avoid|stop|omit|cannot|can't|don't|free|figure-free)\b",
    re.IGNORECASE,
)

#: Headings whose bodies are IMPERATIVE — the steps a wrapping-up model executes.
#: Inside these, the rule is stricter (see `_figure_mention_offenders`).
_INSTRUCTION_HEADING_KEYWORDS = ("protocol", "continuation", "what not to do")

_LEAD_MARKUP_RE = re.compile(r"^[\s>*_`#-]*(?:\d+[.)]\s*)?[\s>*_`-]*")


def _sentences(chunk: str) -> list[str]:
    """Split a markdown chunk into whitespace-normalized sentence-ish units."""
    flat = " ".join(chunk.split())
    return [s for s in re.split(r"(?<=[.!?:])\s+", flat) if s.strip()]


def _numbered_units(text: str) -> list[tuple[int, str]]:
    """(line number, sentence) for every sentence, so a failure can be located."""
    return [(n, s) for n, line in enumerate(text.splitlines(), 1) for s in _sentences(line)]


def _instruction_sections(text: str) -> list[tuple[int, str]]:
    """The `##` sections whose bodies are instructions, with their start lines."""
    sections: list[tuple[int, str]] = []
    collecting = False
    buf: list[str] = []
    start = 1
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            if collecting:
                sections.append((start, "\n".join(buf)))
            collecting = any(k in line[3:].lower() for k in _INSTRUCTION_HEADING_KEYWORDS)
            buf, start = [], n
        elif collecting:
            buf.append(line)
    if collecting:
        sections.append((start, "\n".join(buf)))
    return sections


def _figure_order_offenders(text: str) -> list[str]:
    """Sentences anywhere that COMMAND the reader to emit an occupancy figure.

    An offender is an imperative (or obligation-marked) sentence built on an
    emission verb that also names a figure, and that is not itself a prohibition.
    """
    offenders = []
    for n, sent in _numbered_units(text):
        head = _LEAD_MARKUP_RE.sub("", sent)
        head = re.sub(r"^\*\*.*?\*\*\.?\s*", "", head)  # drop a bolded step label
        commands = bool(_IMPERATIVE_EMIT_RE.match(head)) or bool(_OBLIGATION_EMIT_RE.search(sent))
        if commands and _FIGURE_TERM_RE.search(sent) and not _PROHIBITION_RE.search(sent):
            offenders.append(f"orders a figure, line {n}: {sent[:160]}")
    return offenders


def _figure_mention_offenders(text: str) -> list[str]:
    """Any non-prohibitive MENTION of a figure inside the imperative sections.

    Stricter than `_figure_order_offenders` and deliberately so: inside the
    protocol steps every sentence is an instruction, so a figure may appear there
    only to be forbidden. This is the half that catches a verb-less rewrite
    ("Step 1 output: trigger, profile, and the resident-token figure.").
    """
    offenders = []
    for start, section in _instruction_sections(text):
        for n, sent in _numbered_units(section):
            if _FIGURE_TERM_RE.search(sent) and not _PROHIBITION_RE.search(sent):
                offenders.append(f"mentions a figure in an instruction, line ~{start + n}: {sent}")
    return offenders


def _wrapup_skill_figure_offenders(text: str) -> list[str]:
    """Both detectors, which is the whole check. Empty list == compliant."""
    return _figure_order_offenders(text) + _figure_mention_offenders(text)


class TestWrapupProtocolOrdersNoFigureRecital:
    """The wrap-up protocol must not instruct the model to utter an occupancy figure.

    Reads `.claude/skills/wrapping-up-sessions/SKILL.md` as INSTRUCTIONS, because
    that is what a CORE skill is to the model that loads it mid-wrap-up. Two
    detectors: one flags a command to emit a figure anywhere on the page, the
    other flags any non-prohibitive mention of one inside the imperative sections.

    WHAT THIS CANNOT CATCH — read this before treating it as coverage:

    * **Behaviour.** It reads prose. That a model given a clean page does not go
      hunting for the number anyway is not tested here, or anywhere in this repo.
    * **Synonyms outside the lists.** Detection is lexical. An order phrased with
      a verb absent from `_EMIT_VERBS` *and* a noun absent from `_FIGURE_TERM_RE`
      ("open with where you are in the window") passes — measured, it does.
    * **Negation is counted, not parsed.** Any prohibition word in the sentence
      exempts it, so "do not omit the token count" passes — measured, it does.
      The lists are a floor; a reviewer is still the ceiling.
    * **One file — and not the only file the protocol hands the model.**
      `/handoff`, the agent definitions, the hooks' own text, and every downstream
      copy in a derived project are unscanned. This guards the page that
      propagates, not the propagation. The sharpest omission was
      `docs/templates/handoff-template.md`: protocol step 5 orders the artifact be
      written *from* that template, so the template is a second set of
      instructions reaching the model through this page, and this class never read
      it. Measured 2026-08-08, its trigger field asks for `~tokens` — the exact
      literal deleted from step 1. `TestHandoffTemplateAgreesWithTheProtocol`
      below covers that one seam. Nothing covers the rest of the list above.
    * **Not the developer's surfaces.** The status line and the handoff artifact
      are where the human gets the number; `TestModelFacingNudgeCarriesNoFigures`
      is what keeps them populated. Nothing here should be read as forbidding a
      figure to the developer — only as forbidding an order to the model to fetch
      and recite one.
    """

    #: The instruction as it actually shipped, plus five rewordings of it. Each is
    #: spliced into a copy of the real page at the site of the real step 1 — the
    #: check is worthless if it only recognises the string that was deleted.
    _RESTORED_ORDERS = (
        "State the trigger (`soft|hard`, profile, ~tokens).",
        "Announce the trigger and roughly how many tokens are resident.",
        "Report the current occupancy percentage alongside the profile.",
        "State the trigger; you must include the token count so the developer can check it.",
        "Give the developer the context-budget figure you are wrapping up at.",
        "State the trigger. Step 1 output: trigger, profile, and the resident-token figure.",
    )

    @staticmethod
    def _page() -> str:
        path = PROJECT_ROOT / _WRAPUP_SKILL
        assert path.is_file(), f"{_WRAPUP_SKILL} is missing — this check would pass vacuously"
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _step_one(text: str) -> str:
        match = re.search(r"^1\.\s+\*\*Announce.*$", text, re.MULTILINE)
        assert match is not None, (
            f"{_WRAPUP_SKILL} no longer opens its protocol with a numbered "
            "'**Announce...**' step. The mutation cases below splice into that line; "
            "re-anchor them rather than deleting them."
        )
        return match.group(0)

    @pytest.mark.regression
    def test_the_protocol_orders_no_occupancy_figure(self) -> None:
        # THE REGRESSION. Protocol step 1 read "State the trigger (`soft|hard`,
        # profile, ~tokens)" — an order to announce the exact figure the guard had
        # just stopped supplying, in the file edited to remove it, at the moment it
        # is guaranteed to fire, in a CORE skill that propagates verbatim.
        offenders = _wrapup_skill_figure_offenders(self._page())
        assert not offenders, (
            "the wrap-up skill instructs the model to emit a context-occupancy "
            "figure. The developer gets that number from the status line; the model "
            "must not be sent to fetch and recite it (ADR-0033, amendment 2). Inside "
            "the protocol steps a figure may be NAMED only to be forbidden.\n  "
            + "\n  ".join(offenders)
        )

    @pytest.mark.parametrize("order", _RESTORED_ORDERS)
    def test_the_check_catches_the_order_however_it_is_phrased(self, order: str) -> None:
        # Teeth. Each phrasing is spliced into the REAL page, so this proves the
        # detector fires in context — not merely on a hand-built string. The last
        # case carries no emission verb at all and is caught only by the
        # instruction-section detector, which is why both exist.
        page = self._page()
        mutant = page.replace(self._step_one(page), f"1. **Announce + choose.** {order}")
        assert mutant != page, "the mutation did not apply; the splice anchor has moved"
        assert _wrapup_skill_figure_offenders(mutant), (
            f"the check passes a page whose step 1 reads {order!r}. A detector that "
            "only recognises the one phrasing that shipped is a point fix wearing the "
            "costume of a guard."
        )

    def test_the_check_is_not_vacuous_on_the_page_it_reads(self) -> None:
        # The complement: a detector that flags nothing because it matches nothing
        # would satisfy the regression test above forever. Assert both halves are
        # live — the figure vocabulary appears on this page (in prohibitions), and
        # the imperative sections it scans are non-empty.
        page = self._page()
        assert _FIGURE_TERM_RE.search(page), (
            "no figure vocabulary appears anywhere on the wrap-up page. Either the "
            "page was gutted, or `_FIGURE_TERM_RE` no longer matches the words the "
            "page uses — in which case this whole class is asleep."
        )
        sections = _instruction_sections(page)
        assert sections, (
            "no instruction sections found. `_INSTRUCTION_HEADING_KEYWORDS` is "
            f"{_INSTRUCTION_HEADING_KEYWORDS}; the page's `##` headings have moved "
            "and the stricter detector is now scanning nothing."
        )
        assert any("Announce" in body for _start, body in sections)

    def test_the_developer_facing_number_is_not_forbidden_by_accident(self) -> None:
        # Guard against over-reach in the OTHER direction. The point is not that the
        # figure is shameful; it is that the model must not be ordered to fetch it.
        # The page must still tell its reader the readout exists and where — that is
        # what stops a model "filling the gap" by estimating one.
        page = self._page().lower()
        assert "status line" in page, (
            "the wrap-up page no longer says where the occupancy readout lives. "
            "Removing the order to recite the figure must not turn into pretending "
            "the developer has no instrument."
        )


# ---------------------------------------------------------------------------
# Amendment 2, THIRD SURFACE: the FORM the protocol hands the model.
#
# THE GAP, found by an independent critic after the two surfaces above were
# closed. `_nudge_text` stopped handing the model a figure; SKILL.md step 1
# stopped ordering it to recite one. But SKILL.md step 5 orders the handoff
# artifact be written *from* `docs/templates/handoff-template.md`, and that
# template's first field reads (measured on disk 2026-08-08):
#
#     <3-5 lines: ... why a wrap-up fired (soft/hard, profile, ~tokens).>
#
# That is the same literal, in a file the protocol actively puts in front of the
# model at the same moment, reachable by the same propagation path — measured,
# `scripts/lineage/manifest.py` lists `docs/templates/` in FRAMEWORK_PATHS, and
# C:/Work/AI/CovenRPG, C:/Work/AI/VerificationPortal and C:/Work/AI/marrow each
# already carry one occurrence of it.
#
# WHAT THIS CLASS DOES AND DOES NOT DECIDE. It does not rule on whether the
# handoff ARTIFACT may carry the number — that artifact is developer-facing, and
# forbidding it there would be the over-reach `TestWrapupProtocolOrdersNoFigure-
# Recital.test_the_developer_facing_number_is_not_forbidden_by_accident` guards
# against. It rules only that the two files may not CONTRADICT each other in
# silence: if the template asks its writer for an occupancy figure, the protocol
# step that hands the template over must say, in terms, what the model is to do
# about it. The template itself was outside the authorized file scope of the
# slice that added this class, so the contradiction is resolved here at the point
# of use and carried forward as a named obligation in ADR-0033
# (§ *Carry-forward — the handoff template was not re-cut*). This test is what
# stops that obligation closing silently.
# ---------------------------------------------------------------------------

_HANDOFF_TEMPLATE = "docs/templates/handoff-template.md"


def _template_figure_requests(text: str) -> list[str]:
    """Fields of the handoff TEMPLATE that ask their writer for an occupancy figure.

    Same vocabulary as the skill detector, same prohibition escape hatch — a
    template line may name a figure to rule it out. Line-and-sentence granularity
    so a failure points at the field, not at the file.
    """
    offenders = []
    for n, line in enumerate(text.splitlines(), 1):
        for sent in _sentences(line):
            if _FIGURE_TERM_RE.search(sent) and not _PROHIBITION_RE.search(sent):
                offenders.append(f"line {n}: {sent[:160]}")
    return offenders


def _protocol_reconciles_the_template(skill_text: str) -> bool:
    """Does an IMPERATIVE step that names the template also settle the figure?

    Line-scoped rather than sentence-scoped on purpose: a protocol step is one
    markdown line, so this survives rewording inside the step and fails only when
    the step stops addressing the figure at all. Requires the reconciliation to
    live in an instruction section — a note in `## Related files` is a footnote,
    not an instruction, and the model reads the steps.
    """
    for _start, section in _instruction_sections(skill_text):
        for line in section.splitlines():
            if _HANDOFF_TEMPLATE not in line:
                continue
            if _FIGURE_TERM_RE.search(line) and _PROHIBITION_RE.search(line):
                return True
    return False


class TestHandoffTemplateAgreesWithTheProtocol:
    """The template step 5 hands over must not ask for what step 1 forbids.

    WHAT THIS CANNOT CATCH:

    * **It cannot fix the template.** If the template is re-cut to drop the field,
      `test_a_figure_the_template_asks_for_is_settled_by_the_protocol` goes
      vacuous by design and says so in its own body. The mutation cases keep the
      detectors honest after that happens.
    * **It reads two files, not the propagation.** Derived-project copies of
      either file are unscanned, exactly as for the class above.
    * **"Settled" is lexical.** A step that names the template, a figure term and
      any prohibition word passes, however incoherently it strings them together.
      A reviewer is still the ceiling.
    """

    @staticmethod
    def _page() -> str:
        path = PROJECT_ROOT / _WRAPUP_SKILL
        assert path.is_file(), f"{_WRAPUP_SKILL} is missing — this check would pass vacuously"
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _template() -> str:
        path = PROJECT_ROOT / _HANDOFF_TEMPLATE
        assert path.is_file(), (
            f"{_HANDOFF_TEMPLATE} is missing. It is the file protocol step 5 orders "
            "the handoff be written from; this check would pass vacuously without it."
        )
        return path.read_text(encoding="utf-8")

    def test_the_protocol_still_hands_this_template_to_the_model(self) -> None:
        # The anchor for everything below. If step 5 stops naming the template, the
        # seam this class guards has moved and the class is asleep rather than green.
        assert any(
            _HANDOFF_TEMPLATE in line
            for _start, section in _instruction_sections(self._page())
            for line in section.splitlines()
        ), (
            f"no instruction step in {_WRAPUP_SKILL} names {_HANDOFF_TEMPLATE} any "
            "more. Re-anchor this class on whatever the protocol now tells the model "
            "to write the handoff from — do not delete it."
        )

    @pytest.mark.regression
    def test_a_figure_the_template_asks_for_is_settled_by_the_protocol(self) -> None:
        # THE GAP. Step 1 forbids the figure "for every step below too"; step 5 hands
        # over a template whose first field asks for it. Blanket clause versus
        # concrete form, four steps apart, in a CORE file resident in three derived
        # projects. Either the template stops asking, or the step that hands it over
        # says what to do — silence is what shipped and what this forbids.
        requests = _template_figure_requests(self._template())
        if not requests:
            # Vacuous BY DESIGN, and only along the branch where the contradiction is
            # gone: the template was re-cut, so there is nothing for the protocol to
            # reconcile. The mutation cases below still have teeth in this state.
            return
        assert _protocol_reconciles_the_template(self._page()), (
            f"{_HANDOFF_TEMPLATE} asks its writer for an occupancy figure, and no "
            f"instruction step in {_WRAPUP_SKILL} says what the model should do about "
            "it. The model is handed a form asking for a number that step 1 forbids "
            "it to fetch. Fix EITHER file — strike the field, or have the step that "
            "hands the template over rule on it explicitly.\n  " + "\n  ".join(requests)
        )

    @pytest.mark.parametrize(
        "field",
        (
            "<3-5 lines: why a wrap-up fired (soft/hard, profile, ~tokens).>",
            "<the occupancy percentage at wrap-up>",
            "<how full the window was when this fired>",
            "<remaining context budget>",
        ),
    )
    def test_the_template_detector_catches_a_figure_field_however_phrased(
        self, field: str
    ) -> None:
        # Teeth for the template half, independent of what the template says today.
        assert _template_figure_requests(field), (
            f"the template detector passes a field reading {field!r}. A detector that "
            "only recognises the one literal that shipped is a point fix wearing the "
            "costume of a guard."
        )

    def test_the_template_detector_passes_a_re_cut_field(self) -> None:
        # The complement: the acceptable resolution must actually read as acceptable,
        # or the check is a demand no edit can satisfy.
        assert not _template_figure_requests(
            "<3-5 lines: why a wrap-up fired (soft/hard, profile).>"
        )

    def test_the_reconciliation_check_fires_when_the_protocol_goes_silent(self) -> None:
        # Teeth for the skill half. Splice the step back to the wording that shipped
        # — names the template, says nothing about the field — and require a failure.
        page = self._page()
        step = next(
            (
                line
                for line in page.splitlines()
                if _HANDOFF_TEMPLATE in line and line.lstrip().startswith("5.")
            ),
            None,
        )
        assert step is not None, (
            "protocol step 5 no longer names the template on a numbered line; "
            "re-anchor this mutation rather than deleting it."
        )
        silent = (
            "5. **Write the handoff artifact** to "
            f"`docs/handoff/HANDOFF-<YYYYMMDD-HHMMSS>.md` from `{_HANDOFF_TEMPLATE}`."
        )
        mutant = page.replace(step, silent)
        assert mutant != page, "the mutation did not apply; the splice anchor has moved"
        assert not _protocol_reconciles_the_template(mutant), (
            "the check reports a protocol that says nothing about the template's "
            "figure field as having reconciled it. That is the exact state that "
            "shipped, so a check green on it guards nothing."
        )


# ---------------------------------------------------------------------------
# AC-5: handoff retention (FIFO).
# ---------------------------------------------------------------------------


class TestEnforceRetention:
    def test_evicts_oldest_keeps_cap(self, tmp_path: Path) -> None:
        for i in range(6):
            (tmp_path / f"HANDOFF-2026052{i}-120000.md").write_text("x", encoding="utf-8")
        removed = enforce_retention(handoff_dir=tmp_path, cap=5)
        remaining = sorted(p.name for p in tmp_path.glob("HANDOFF-*.md"))
        assert len(remaining) == 5
        assert len(removed) == 1
        assert removed[0].name == "HANDOFF-20260520-120000.md"  # oldest by name

    def test_under_cap_removes_nothing(self, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"HANDOFF-2026052{i}-120000.md").write_text("x", encoding="utf-8")
        assert enforce_retention(handoff_dir=tmp_path, cap=5) == []

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert enforce_retention(handoff_dir=tmp_path / "nope", cap=5) == []


# ---------------------------------------------------------------------------
# AC-6: auto-launch command builder (no process spawned).
# ---------------------------------------------------------------------------


class TestBuildLaunchCommand:
    def _handoff(self, tmp_path: Path) -> Path:
        path = tmp_path / "HANDOFF-20260523-120000.md"
        path.write_text("handoff", encoding="utf-8")
        return path

    def test_none_when_auth_off(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=False,
                allow_launch=True,
                depth=0,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_allow_launch_off(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=True,
                allow_launch=False,
                depth=0,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_depth_cap_reached(self, tmp_path: Path) -> None:
        assert (
            build_launch_command(
                self._handoff(tmp_path),
                auth=True,
                allow_launch=True,
                depth=1,
                max_depth=1,
                handoff_dir=tmp_path,
            )
            is None
        )

    def test_none_when_path_escapes_handoff_dir(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape.md"
        assert (
            build_launch_command(
                outside, auth=True, allow_launch=True, depth=0, max_depth=1, handoff_dir=tmp_path
            )
            is None
        )

    def test_valid_returns_single_positional_prompt_with_validated_path(
        self, tmp_path: Path
    ) -> None:
        handoff = self._handoff(tmp_path)
        cmd = build_launch_command(
            handoff, auth=True, allow_launch=True, depth=0, max_depth=1, handoff_dir=tmp_path
        )
        assert cmd is not None
        assert cmd[:2] == ["claude", "--print"]
        # Single-positional prompt (what `claude --print` accepts); the validated,
        # containment-checked path is inlined — injection-safe under shell=False.
        assert len(cmd) == 3
        assert str(handoff.resolve()) in cmd[2]


# ---------------------------------------------------------------------------
# build_sidecar_record shape.
# ---------------------------------------------------------------------------


def test_build_sidecar_record_has_required_fields() -> None:
    occ = Occupancy(140000, 14.0, 1_000_000, "statusline", "claude-opus-4-7")
    prof = resolve_threshold("claude-opus-4-7")
    rec = build_sidecar_record(occ, prof, "sess-1", now=123.0)
    assert rec["session_id"] == "sess-1"
    assert rec["tier"] == "opus_1m"
    assert rec["written_at_epoch"] == 123.0
    assert rec["source"] == "statusline"
