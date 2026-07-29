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

Usage:
    python scripts/audit_calibration.py              # audit; print report + write queue/log
    python scripts/audit_calibration.py --report-only  # print report only; write nothing
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


def audit_calibration(db_path: Path = DB_PATH, *, write: bool = True) -> AuditResult:
    """Run the calibration audit. Read-only on the DB; writes only the queue + log.

    Args:
        db_path: Path to the evaluation database.
        write: When True, write the proposal queue artifact and append the run log.

    Returns:
        The structured :class:`AuditResult` (proposals + notes).
    """
    result = AuditResult()
    if not db_path.exists():
        result.notes.append("Database not found — nothing to audit (run scripts/init_db.py).")
        return result

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
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
        result.proposals.clear()
        result.notes.append(
            f"Calibration audit unavailable — database error ({type(exc).__name__})."
        )
        return result
    finally:
        if conn is not None:
            conn.close()

    if write and result.proposals:
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        _write_queue(result, ts)
        _append_log(result, ts)
    return result


def _write_queue(result: AuditResult, ts: str) -> Path:
    """Write a dated, append-safe proposal queue artifact (never overwrites a prior run)."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"CALIB-{ts}.md"
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


def _append_log(result: AuditResult, ts: str) -> None:
    """Append one line to the calibration run log (capture is automatic — Principle #2)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": ts,
        "proposals": len(result.proposals),
        "signals": sorted({p.signal for p in result.proposals}),
        "kinds": sorted({p.kind for p in result.proposals}),
    }
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def render_report(result: AuditResult) -> str:
    """Render a human-readable calibration report (display-only; no execution)."""
    out = ["Calibration audit", "=" * 17]
    for note in result.notes:
        out.append(f"note: {note}")
    if not result.proposals:
        out.append("No drift signals crossed threshold — classifier calibration looks healthy.")
        return "\n".join(out)
    out.append(
        f"{len(result.proposals)} proposal(s) — HUMAN approval required before applying any:"
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
    """CLI entry point. Returns a process exit code (0 = clean run)."""
    parser = argparse.ArgumentParser(description="Audit classifier calibration drift.")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print the report without writing the proposal queue or run log.",
    )
    args = parser.parse_args()
    result = audit_calibration(write=not args.report_only)
    print(render_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
