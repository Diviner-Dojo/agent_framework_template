"""Assess the framework's hook wiring from already-loaded, read-only facts.

Layer B Phase 4 Unit 4.1 (SPEC-20260610-005602 — self-monitoring). Pure logic
over already-resolved inputs: the file IO (reading ``settings.json`` text,
stat-ing script files, tailing the quality-gate log) happens in the transport
layer (``scripts/telemetry/dashboard_server.py``); this module knows nothing
about files, never executes anything, and imports stdlib only — which is what
keeps the parent spec's AC3(a) no-inject import allowlist trivially true.

The *health claim* is deliberately narrow (ADR-0020 honesty):

* **Configuration presence** — the top-level ``"hooks"`` key of
  ``settings.json`` declares hook command entries; each entry that references
  a ``.claude/hooks/<script>`` file can be checked for on-disk presence.
  ``statusLine`` (a TOP-LEVEL SIBLING of ``"hooks"``, not nested inside it)
  is **intentionally excluded**: it is a context sensor, not an enforcement
  hook, and counting it would inflate the enforcement claim.
* **Recency evidence** — the last quality-gate run timestamp evidences
  exactly ONE hook's underlying gate (the pre-commit gate). The renderer must
  label it as such ("quality gate last ran ..."), never as "hooks last
  fired" — one activity signal is not evidence that all hooks fire.

Minimum disclosure (spec security F1): only the script file *basename* is
ever captured from a hook ``command`` string. The full command (which in a
derived project could embed flags, absolute paths, or tokens) is never
stored, returned, or rendered.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

#: Health status: at least one hook command configured and every referenced
#: ``.claude/hooks/`` script present on disk.
HOOK_STATUS_OK = "ok"

#: Health status: at least one referenced ``.claude/hooks/`` script is absent.
HOOK_STATUS_MISSING_SCRIPTS = "missing_scripts"

#: Health status: settings absent/unreadable/malformed, or zero hook entries.
#: This is the typed honest-absence state (ADR-0020) — never a crash and never
#: a fabricated "ok".
HOOK_STATUS_NOT_CONFIGURED = "not_configured"

#: Canonical tuple of the three health statuses (stable vocabulary for tests
#: and the render-side label map in ``src/telemetry/dashboard.py``).
HOOK_HEALTH_STATUSES: tuple[str, ...] = (
    HOOK_STATUS_OK,
    HOOK_STATUS_MISSING_SCRIPTS,
    HOOK_STATUS_NOT_CONFIGURED,
)

#: Path-pattern extraction strategy pinned by the spec (qa F2): a substring
#: match for ``.claude/hooks/<basename>`` covers BOTH production command forms
#: (``bash .claude/hooks/x.sh`` and ``powershell ... -File .claude/hooks/y.ps1``)
#: by construction, and captures ONLY the final path component — the full
#: command string never propagates past the parser (security F1). Both slash
#: directions are accepted because the repo is Windows-first.
_HOOK_SCRIPT_REF = re.compile(r"\.claude[/\\]hooks[/\\]([A-Za-z0-9_.\-]+)")


@dataclass(frozen=True)
class HookConfigParse:
    """Structured result of parsing the ``"hooks"`` block of settings text.

    Attributes:
        script_refs: Deduplicated ``.claude/hooks/`` script file basenames in
            first-seen order. Basenames only — never full command strings.
        hook_count: Total number of hook command entries found, including
            commands that reference no ``.claude/hooks/`` script.
    """

    script_refs: tuple[str, ...]
    hook_count: int


@dataclass(frozen=True)
class HookHealthReport:
    """The chip's read-only health claim, assembled from resolved facts.

    Attributes:
        status: One of :data:`HOOK_HEALTH_STATUSES`.
        hooks_configured: Number of configured hook command entries.
        scripts_missing: Deduplicated basenames of referenced-but-absent
            ``.claude/hooks/`` scripts.
        last_gate_run: Timezone-aware timestamp of the last well-formed
            quality-gate log entry, or ``None`` when no run was observed.
            This evidences the pre-commit gate ONLY (see module docstring).
    """

    status: str
    hooks_configured: int
    scripts_missing: tuple[str, ...]
    last_gate_run: datetime | None


def _iter_hook_commands(hooks_block: object) -> list[str]:
    """Collect ``command`` string values from a ``"hooks"`` block, tolerantly.

    The real shape is ``{event: [{matcher?, hooks: [{type, command, ...}]}]}``
    but this walk accepts structural variation (missing ``matcher``, extra
    keys) and ignores anything that is not shaped like a command entry — an
    unrecognized shape degrades toward ``not_configured``, never a raise.
    """
    commands: list[str] = []
    if not isinstance(hooks_block, dict):
        return commands
    for entries in hooks_block.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            inner = entry.get("hooks")
            if not isinstance(inner, list):
                continue
            for hook in inner:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.append(hook["command"])
    return commands


def parse_hook_script_refs(settings_text: str | None) -> HookConfigParse:
    """Parse settings JSON text into the hook inventory the chip reports on.

    Walks ONLY the top-level ``"hooks"`` key — ``statusLine`` is intentionally
    out of scope (see module docstring). Extraction is the pinned path-pattern
    strategy: each command string is scanned for ``.claude/hooks/<basename>``
    references; only the basename is captured and the result is deduplicated
    in first-seen order.

    Args:
        settings_text: The raw text of ``settings.json``, or ``None`` when the
            file is missing/unreadable.

    Returns:
        A :class:`HookConfigParse`. Malformed JSON, a non-dict document, a
        missing/``null``/non-dict ``"hooks"`` value, or zero command entries
        all yield ``hook_count == 0`` (the ``not_configured`` input state) —
        never a raise.
    """
    if settings_text is None:
        return HookConfigParse(script_refs=(), hook_count=0)
    try:
        document = json.loads(settings_text)
    except json.JSONDecodeError:
        return HookConfigParse(script_refs=(), hook_count=0)
    if not isinstance(document, dict):
        return HookConfigParse(script_refs=(), hook_count=0)
    commands = _iter_hook_commands(document.get("hooks"))
    seen: dict[str, None] = {}
    for command in commands:
        for match in _HOOK_SCRIPT_REF.finditer(command):
            seen.setdefault(match.group(1))
    return HookConfigParse(script_refs=tuple(seen), hook_count=len(commands))


def assess_hook_health(
    parsed: HookConfigParse,
    missing: tuple[str, ...],
    last_gate_run: datetime | None,
) -> HookHealthReport:
    """Assemble the health report from already-resolved facts.

    Args:
        parsed: The parsed hook inventory from :func:`parse_hook_script_refs`.
        missing: Deduplicated basenames of referenced scripts the transport
            layer found absent on disk.
        last_gate_run: Timezone-aware timestamp of the last well-formed
            quality-gate log entry, or ``None``.

    Returns:
        A :class:`HookHealthReport` whose ``status`` is ``not_configured``
        when zero hooks are configured, ``missing_scripts`` when any
        referenced script is absent, and ``ok`` otherwise.
    """
    if parsed.hook_count == 0:
        status = HOOK_STATUS_NOT_CONFIGURED
    elif missing:
        status = HOOK_STATUS_MISSING_SCRIPTS
    else:
        status = HOOK_STATUS_OK
    return HookHealthReport(
        status=status,
        hooks_configured=parsed.hook_count,
        scripts_missing=missing,
        last_gate_run=last_gate_run,
    )
