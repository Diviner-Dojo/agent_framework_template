"""Audit classifier calibration drift and emit human-gated tightening proposals.

Closes the audit->tighten loop the template otherwise leaves open. The template
already *computes* ``agent_effectiveness.confidence_calibration`` and classifies
findings (severity/category/is_noise), but never reads those signals back to tighten
its classifier. This script READS them from ``metrics/evaluation.db``, surfaces drift
signals, and writes PROPOSALS to a human-approved queue under
``memory/calibration-proposals/``. It NEVER edits a classifier surface
(``scripts/extract_findings.py`` patterns or ``.claude/skills/severity-calibration/``);
a human applies proposals. Proposals are ``status: pending`` communication artifacts,
not instruction files (ADR-0024; Principle #7; Prime Objective human-mediated gate).

Backflow origin: the confidence-calibration loop of ``dan_research_karpathy_wiki``
(SPEC-20260610-205507 decision D2, pattern 2 of 5; ADR-0024).

ADVISORY, NEVER A GATE. This script's exit code is 0 whenever it ran successfully,
*regardless of how many proposals it emits*. Drift signals must never fail a build,
block a commit, or gate a workflow: they are inputs to human judgment. A non-zero exit
here would turn a soft proxy metric into a mechanical enforcement surface, which is
exactly the self-modification pressure ADR-0024 exists to prevent. A non-zero exit
means the AUDIT ITSELF failed to run, never that calibration drifted.

EXIT CODES (the contract the command files quote — enforced, not merely described)
----------------------------------------------------------------------------------
* ``0`` — the audit RAN. Zero proposals and fifty proposals both exit 0.
* ``1`` — BROKEN INSTRUMENT: the database was absent or unreadable, so no signal was
  computed. This is gating on the audit having *run*, never on what it *found*. The
  distinction is the entire point: without it, "the instrument was missing" and
  "calibration is healthy" arrive at the reader as the same silent success.

RUN LOG. Every invocation appends one line to ``metrics/calibration_log.jsonl``,
including runs that emit zero proposals and runs where the instrument was broken
(``"ok": false``). A clean audit that left no trace is indistinguishable from an audit
that never happened — the same collapse the yield report exists to prevent, one level
up. ``--report-only`` suppresses the proposal QUEUE artifact, never the run log.

Usage:
    python scripts/audit_calibration.py              # audit; print report + write queue/log
    python scripts/audit_calibration.py --report-only  # print report + run log; no queue
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "metrics" / "evaluation.db"
QUEUE_DIR = PROJECT_ROOT / "memory" / "calibration-proposals"
LOG_PATH = PROJECT_ROOT / "metrics" / "calibration_log.jsonl"

# Conservative thresholds — drift signals are inputs to HUMAN judgment, not verdicts.
# confidence_calibration is a rough proxy (|conf_avg - uniqueness_ratio|), so the bar
# is set high and a single-signal proposal is flagged low-confidence (ADR-0024).
CALIBRATION_DRIFT_THRESHOLD = 0.30
NOISE_RATE_THRESHOLD = 0.40
SEVERITY_DISAGREEMENT_THRESHOLD = 0.25
MIN_SAMPLE = 8  # below this, a rate is too noisy to act on
SAMPLE_EVIDENCE = 3  # sample findings shown per proposal (raw evidence for the human)


@dataclass
class Proposal:
    """A single human-gated proposal to tighten a named classifier surface."""

    surface: str
    kind: str  # "classifier-code" | "skill-rubric"
    signal: str
    metric: str
    recommendation: str
    evidence: list[str] = field(default_factory=list)
    low_confidence: bool = False


@dataclass
class AuditResult:
    """Structured outcome of one calibration audit run."""

    proposals: list[Proposal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: False when the audit could not run at all (database absent or unreadable).
    #: A STRUCTURED field, deliberately not a substring test against ``notes``: the exit
    #: code the command files quote must not depend on the wording of a human-readable
    #: sentence that any later edit could reword. ``instrument_ok is False`` means "no
    #: signal was computed" — it never means "drift was found".
    instrument_ok: bool = True


def _agent_calibration_drift(conn: sqlite3.Connection) -> list[Proposal]:
    """Flag agents whose mean confidence_calibration exceeds the drift threshold.

    Reads the pre-computed ``agent_effectiveness`` metric (does not touch
    ``findings.severity``, so the is_noise filter is not applicable here).
    """
    rows = conn.execute(
        """SELECT agent, AVG(confidence_calibration) AS avg_cal, COUNT(*) AS n
           FROM agent_effectiveness
           WHERE confidence_calibration IS NOT NULL
           GROUP BY agent
           HAVING n >= ?""",
        (MIN_SAMPLE,),
    ).fetchall()
    over = [
        (agent, avg_cal, n)
        for agent, avg_cal, n in rows
        if avg_cal is not None and avg_cal > CALIBRATION_DRIFT_THRESHOLD
    ]
    if not over:
        return []
    # One aggregate proposal, not one-per-agent: confidence_calibration is a rough proxy
    # (|conf_avg - uniqueness_ratio|), so a broad exceedance points at the proxy/rubric,
    # not at each agent individually (ADR-0024 residual risk). Always low-confidence.
    over.sort(key=lambda r: r[1], reverse=True)
    return [
        Proposal(
            surface=".claude/skills/severity-calibration/SKILL.md",
            kind="skill-rubric",
            signal="agent-calibration-drift",
            metric=f"{len(over)} agent(s) exceed mean confidence_calibration "
            f"{CALIBRATION_DRIFT_THRESHOLD}",
            recommendation=(
                "Stated confidence diverges from uniqueness-ratio accuracy for several agents. "
                "Because the calibration metric is a rough proxy, review the proxy itself and the "
                "severity-calibration rubric before concluding any single agent is mis-calibrated."
            ),
            evidence=[f"{agent}: {avg_cal:.3f} over {n} records" for agent, avg_cal, n in over],
            low_confidence=True,  # calibration proxy alone is a soft signal
        )
    ]


def _category_noise_rate(conn: sqlite3.Connection) -> list[Proposal]:
    """Flag categories with a high boilerplate (is_noise) rate.

    Subject IS is_noise, so this query intentionally counts noise rows; it does not
    aggregate severity, so the ADR-0022 ``is_noise = 0`` rule does not apply here.
    """
    rows = conn.execute(
        """SELECT category,
                  SUM(is_noise) AS noise_n,
                  COUNT(*) AS total_n
           FROM findings
           GROUP BY category
           HAVING total_n >= ?""",
        (MIN_SAMPLE,),
    ).fetchall()
    proposals: list[Proposal] = []
    for category, noise_n, total_n in rows:
        rate = noise_n / total_n if total_n else 0.0
        if rate < NOISE_RATE_THRESHOLD:
            continue
        samples = conn.execute(
            """SELECT summary FROM findings
               WHERE category = ? AND is_noise = 1
               ORDER BY created_at DESC LIMIT ?""",
            (category, SAMPLE_EVIDENCE),
        ).fetchall()
        proposals.append(
            Proposal(
                surface="scripts/extract_findings.py (_is_verdict_boilerplate)",
                kind="classifier-code",
                signal="category-noise-rate",
                metric=f"category '{category}': {noise_n}/{total_n} is_noise ({rate:.0%})",
                recommendation=(
                    f"A high share of '{category}' findings are boilerplate. Either the "
                    f"boilerplate filter under-catches at extraction time (tighten the "
                    f"_is_verdict_boilerplate patterns) or this category is a scaffold magnet."
                ),
                evidence=[f"noise sample: {s[0][:160]}" for s in samples],
            )
        )
    return proposals


def _load_classifier() -> Callable[[str], str] | None:
    """Load the single-source ``_classify_severity`` from ``scripts/extract_findings.py``.

    Loads by file path (not ``import extract_findings``) so it resolves whether this
    module is run as a script or imported by a test, without depending on ``sys.path``.
    Returns None if the classifier cannot be loaded (the signal degrades gracefully).
    """
    target = PROJECT_ROOT / "scripts" / "extract_findings.py"
    if not target.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("extract_findings", target)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._classify_severity  # type: ignore[no-any-return]
    except (ImportError, AttributeError, OSError):
        return None


def _severity_marker_disagreement(
    conn: sqlite3.Connection, classifier: Callable[[str], str]
) -> list[Proposal]:
    """Flag drift between the keyword-heuristic severity and the recorded severity.

    Only NON-NOISE rows are considered (ADR-0022: noise rows carry an unmaintained
    severity). Re-derives a heuristic severity from each finding's topical summary via
    the single-source ``extract_findings._classify_severity`` and compares it to the
    recorded severity; a high disagreement rate means the static keyword patterns are
    diverging from the authoritative (explicit-marker-respecting) outcomes.
    """
    rows = conn.execute(
        "SELECT summary, severity FROM findings WHERE is_noise = 0 AND summary IS NOT NULL"
    ).fetchall()
    if len(rows) < MIN_SAMPLE:
        return []
    disagreements: list[tuple[str, str, str]] = []
    for summary, recorded in rows:
        heuristic = classifier(summary)  # display-only text; never a sink
        if heuristic != recorded:
            disagreements.append((summary, recorded, heuristic))
    rate = len(disagreements) / len(rows)
    if rate < SEVERITY_DISAGREEMENT_THRESHOLD:
        return []
    samples = disagreements[:SAMPLE_EVIDENCE]
    return [
        Proposal(
            surface="scripts/extract_findings.py (_SEVERITY_PATTERNS)",
            kind="classifier-code",
            signal="severity-heuristic-disagreement",
            metric=f"{len(disagreements)}/{len(rows)} non-noise findings ({rate:.0%}) disagree",
            recommendation=(
                "The keyword-heuristic severity (on the topical summary) diverges from the "
                "recorded severity at a high rate. Tighten _SEVERITY_PATTERNS so the heuristic "
                "better matches the authoritative explicit-marker outcomes."
            ),
            evidence=[
                f"summary={summary[:120]!r} recorded={rec} heuristic={heur}"
                for summary, rec, heur in samples
            ],
        )
    ]


def audit_calibration(
    db_path: Path | None = None,
    *,
    write: bool = True,
    write_queue: bool | None = None,
    queue_dir: Path | None = None,
    log_path: Path | None = None,
) -> AuditResult:
    """Run the calibration audit. Read-only on the DB; writes only the queue + log.

    Args:
        db_path: Path to the evaluation database. None resolves :data:`DB_PATH` at CALL
            time (a ``= DB_PATH`` default would bind at def time and silently ignore a
            monkeypatched destination — the same reason :func:`_write_queue` defers).
        write: Master switch for persistence. False writes NOTHING — no queue, no log.
            Tests pass False.
        write_queue: Whether to write the proposal QUEUE artifact. Defaults to ``write``.
            Split out because the two writes answer different questions: the queue says
            *what to change*, the run log says *that the audit happened at all*.
            ``--report-only`` sets this False while leaving the run log on, so a
            report-only invocation still leaves a durable trace.
        queue_dir: Override for the proposal queue directory (tests pass a tmp_path).
        log_path: Override for the run-log path (tests pass a tmp_path).

    Returns:
        The structured :class:`AuditResult` (proposals + notes + instrument_ok).
    """
    db_path = db_path if db_path is not None else DB_PATH
    write_queue = write if write_queue is None else write_queue
    result = AuditResult()
    if not db_path.exists():
        result.instrument_ok = False
        result.notes.append("Database not found — nothing to audit (run scripts/init_db.py).")
        return _persist(
            result, write=write, write_queue=write_queue, queue_dir=queue_dir, log_path=log_path
        )

    conn: sqlite3.Connection | None = None
    try:
        # Opened read-only at the driver level, not merely by convention: this script
        # only ever reads evaluation.db, and an audit tool that could mutate the
        # evidence it audits is not an audit tool.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        result.proposals.extend(_agent_calibration_drift(conn))
        result.proposals.extend(_category_noise_rate(conn))
        classifier = _load_classifier()
        if classifier is None:
            result.notes.append(
                "Severity-disagreement signal unavailable (classifier not loadable)."
            )
        else:
            sev = _severity_marker_disagreement(conn, classifier)
            result.proposals.extend(sev)
            if not sev:
                result.notes.append("Severity-disagreement signal healthy (below threshold).")
    except sqlite3.Error as exc:
        # Never expose raw DB/internal errors (Always-On invariant).
        result.instrument_ok = False
        result.proposals.clear()
        result.notes.append(
            f"Calibration audit unavailable — database error ({type(exc).__name__})."
        )
        return _persist(
            result, write=write, write_queue=write_queue, queue_dir=queue_dir, log_path=log_path
        )
    finally:
        if conn is not None:
            conn.close()

    return _persist(
        result, write=write, write_queue=write_queue, queue_dir=queue_dir, log_path=log_path
    )


def _persist(
    result: AuditResult,
    *,
    write: bool,
    write_queue: bool,
    queue_dir: Path | None,
    log_path: Path | None,
) -> AuditResult:
    """Persist one run: the queue artifact only if there is something to queue, the run
    log ALWAYS.

    The two writes are deliberately gated differently.

    * The QUEUE is a to-do list for a human, so an empty one is noise: it is written only
      when ``write_queue`` and there is at least one proposal.
    * The RUN LOG is the record that the audit HAPPENED, so it is written on every run
      that persistence is enabled for — zero proposals included, broken instrument
      included. Gating it on ``result.proposals`` (as an earlier version did) erased
      exactly the clean case: an audit that ran and found nothing left no trace, making
      "measured, no drift" indistinguishable from "never measured". That is the same
      collapse ``efficiency_report.py`` exists to prevent, reproduced inside the
      instrument meant to prevent it. Capture is automatic (Principle #2) or it is not
      capture.

    ``write`` remains the master switch: False writes nothing at all, so a library caller
    (every test in the suite) cannot leave artifacts behind.
    """
    if not write:
        return result
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if write_queue and result.proposals:
        _write_queue(result, ts, queue_dir or QUEUE_DIR)
    _append_log(result, ts, log_path or LOG_PATH)
    return result


def _write_queue(result: AuditResult, ts: str, queue_dir: Path | None = None) -> Path:
    """Write a dated, append-safe proposal queue artifact (never overwrites a prior run).

    ``queue_dir`` defaults to None rather than to ``QUEUE_DIR`` so the module global is
    resolved at CALL time — a ``= QUEUE_DIR`` default would bind at def time and silently
    ignore a monkeypatched destination, sending test artifacts into the real repo.
    """
    queue_dir = queue_dir if queue_dir is not None else QUEUE_DIR
    queue_dir.mkdir(parents=True, exist_ok=True)
    path = queue_dir / f"CALIB-{ts}.md"
    lines = [
        f"# Calibration proposals — {ts}",
        "",
        "> status: pending. This is a COMMUNICATION artifact, not an instruction file.",
        "> A human applies each proposal by editing the named classifier surface;",
        "> the agent must not. Origin: dan_research_karpathy_wiki loop (ADR-0024).",
        "",
    ]
    for i, p in enumerate(result.proposals, 1):
        lines += [
            f"## Proposal {i} — {p.signal} [{p.kind}]"
            + ("  _(low-confidence: single soft signal)_" if p.low_confidence else ""),
            f"- **surface:** `{p.surface}`",
            f"- **metric:** {p.metric}",
            f"- **recommendation:** {p.recommendation}",
            "- **evidence:**",
            *[f"  - {e}" for e in p.evidence],
            "- **status:** pending",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _append_log(result: AuditResult, ts: str, log_path: Path | None = None) -> None:
    """Append one line to the calibration run log (capture is automatic — Principle #2).

    Called on EVERY persisted run, including zero-proposal runs and runs where the
    instrument was broken — see :func:`_persist`. ``ok`` carries that distinction into
    the log so a reader can tell "audited, no drift" from "could not audit" without
    re-deriving it from the absence of a line.

    ``log_path`` defaults to None for the same call-time-resolution reason as
    :func:`_write_queue`.
    """
    log_path = log_path if log_path is not None else LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": ts,
        "ok": result.instrument_ok,
        "proposals": len(result.proposals),
        "signals": sorted({p.signal for p in result.proposals}),
        "kinds": sorted({p.kind for p in result.proposals}),
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def render_report(result: AuditResult) -> str:
    """Render a human-readable calibration report (display-only; no execution)."""
    out = ["Calibration audit", "=" * 17]
    for note in result.notes:
        out.append(f"note: {note}")
    if not result.instrument_ok:
        # Never render a failed audit as a clean one. Before this branch existed, a
        # missing or corrupt database printed "classifier calibration looks healthy" —
        # a broken instrument reporting a passing grade for the thing it failed to
        # measure. The exit code says the same thing (1); this says it to a human.
        out.append(
            "BROKEN INSTRUMENT: the audit could not run, so NOTHING was measured.\n"
            "  This is not a clean bill of health. No conclusion about calibration —\n"
            "  healthy or drifting — may be drawn from this run. Repair the database\n"
            "  (scripts/init_db.py) and re-run."
        )
        return "\n".join(out)
    if not result.proposals:
        out.append("No drift signals crossed threshold — classifier calibration looks healthy.")
        return "\n".join(out)
    out.append(
        f"{len(result.proposals)} proposal(s) — HUMAN approval required before applying any:"
    )
    out.append(
        "  ADVISORY ONLY. These are communication artifacts, not instructions. The agent\n"
        "  must NEVER edit a classifier surface off its own proposal — that is\n"
        "  self-modification (ADR-0024; Principle #6, curated memory needs human\n"
        "  approval). A human applies each one."
    )
    for i, p in enumerate(result.proposals, 1):
        flag = " [low-confidence]" if p.low_confidence else ""
        out.append(f"\n[{i}] {p.signal} ({p.kind}){flag}")
        out.append(f"    surface: {p.surface}")
        out.append(f"    metric:  {p.metric}")
        out.append(f"    -> {p.recommendation}")
        for e in p.evidence:
            out.append(f"    evidence: {e}")
    return "\n".join(out)


def main() -> int:
    """CLI entry point.

    Returns 0 whenever the audit RAN, however many proposals it emitted, and 1 when the
    instrument itself was unavailable (database absent or unreadable). This is an
    advisory instrument, never a gate on its FINDINGS: see the module docstring. A caller
    that reads exit 1 as "drift detected" is misreading it — it means "nothing was
    measured", and the correct response is to repair the instrument, never to conclude
    anything about calibration.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Audit classifier calibration drift. ADVISORY ONLY — exits 0 regardless of "
            "how many proposals are emitted; it never gates a build or a commit. Exit 1 "
            "means the audit could not run at all."
        )
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help=(
            "Do not write the proposal queue artifact. The run log is still appended: "
            "that the audit ran is recorded even when its output is not queued."
        ),
    )
    args = parser.parse_args()
    # write=True always: the run log is capture, not output. --report-only suppresses
    # only the queue artifact, so a /retro or /knowledge-health invocation still leaves
    # the durable "the audit ran on this date" record it previously never wrote.
    result = audit_calibration(write=True, write_queue=not args.report_only)
    print(render_report(result))
    return 0 if result.instrument_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
