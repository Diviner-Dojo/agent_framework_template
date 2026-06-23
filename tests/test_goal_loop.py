"""Tests for the deterministic /goal-loop driver (scripts/goal_loop.py).

Covers the deterministic, fake-injectable behaviors: contract validation (AC1/AC3 caps),
the termination ladder incl. oscillation (AC4/AC4-osc), the verifier-tamper tripwire
(AC5-tamper), loop-state integrity + untrusted-on-read reconstruct (AC8 pos/neg), and
fail-closed L2 autonomy (AC10). Model-invocation-dependent assertions (AC3 distinct
agent id; judge re-verify semantics) land once that seam is wired (T4).
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import goal_loop as gl  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes + helpers
# --------------------------------------------------------------------------- #
class FakeVerifier:
    def __init__(self, *, gate=True, commands=None):
        self._gate = gate
        self._commands = commands or {}
        self.calls: list[str] = []

    def run_quality_gate(self) -> bool:
        self.calls.append("quality_gate")
        return self._gate() if callable(self._gate) else self._gate

    def run_command(self, command: str) -> bool:
        self.calls.append(command)
        v = self._commands.get(command, True)
        return v() if callable(v) else v


class FakeModel:
    def __init__(
        self,
        *,
        diff=None,
        build_tokens=10,
        judge_green=True,
        judge_tokens=5,
        build_agent="builder",
        judge_agent="checker",
    ):
        self._diff = diff or gl.Diff((), ())
        self._build_tokens = build_tokens
        self._judge_green = judge_green
        self._judge_tokens = judge_tokens
        self._build_agent = build_agent
        self._judge_agent = judge_agent
        self.builds: list[str] = []
        self.judges: list[str] = []

    def build(self, contract, target, context):
        self.builds.append(target.id)
        return gl.BuildResult(self._diff, self._build_tokens, agent_id=self._build_agent)

    def judge(self, criterion, delta):
        self.judges.append(criterion.id)
        green = self._judge_green(criterion) if callable(self._judge_green) else self._judge_green
        return gl.JudgeResult(green, self._judge_tokens, agent_id=self._judge_agent, reason="r")


class FakeSink:
    """Records the capture event stream so AC7 ordering can be asserted."""

    def __init__(self):
        self.events: list[tuple] = []

    def builder_turn(self, iteration, target_id, summary):
        self.events.append(("builder", iteration, target_id))

    def checker_turn(self, iteration, verifications):
        self.events.append(("checker", iteration, verifications))

    def gate_result(self, iteration, question, label):
        self.events.append(("gate", iteration, label))

    def termination_decision(self, outcome, report):
        self.events.append(("termination", outcome, report))

    def close(self):
        self.events.append(("close",))


class FakeGate:
    def __init__(self, label="Approve"):
        self.label = label
        self.requests: list[tuple] = []

    def request(self, question, choices, token):
        self.requests.append((question, choices, token))
        return self.label


class FakeDiff:
    def tick_diff(self):
        return gl.Diff((), ())


class FakeAuth:
    def __init__(self, results):
        self._results = results
        self.calls = 0

    def affirm_l2(self, branch: str) -> bool:
        self.calls += 1
        if isinstance(self._results, bool):
            return self._results
        idx = min(self.calls - 1, len(self._results) - 1)
        return self._results[idx]


def alternator(start=True):
    seq = [start, not start]
    state = {"n": 0}

    def f():
        v = seq[state["n"] % 2]
        state["n"] += 1
        return v

    return f


def det(cid="SC1", verify="quality_gate"):
    return gl.Criterion(id=cid, text="", verify=verify, verify_owner="gate")


def judge(cid="J1"):
    return gl.Criterion(id=cid, text="", verify="llm-judge", verify_owner="checker")


def make_contract(
    criteria, *, max_iterations=8, no_progress=2, budget=200_000, autonomy="L1", max_judge=0.5
):
    return gl.GoalContract(
        goal_id="GOAL-T",
        goal="t",
        success_criteria=tuple(criteria),
        termination=gl.Termination(max_iterations, no_progress, "net-progress", budget),
        max_judge_fraction=max_judge,
        autonomy_level=autonomy,
    )


def run(
    contract,
    path,
    *,
    verifier=None,
    model=None,
    gate=None,
    auth=None,
    branch="feature/x",
    sink=None,
):
    return gl.run_goal_loop(
        contract,
        verifier=verifier or FakeVerifier(),
        model=model or FakeModel(),
        gate=gate or FakeGate(),
        diff_source=FakeDiff(),
        auth=auth or FakeAuth(True),
        loop_state_path=path,
        discussion_id="DISC-T",
        branch=branch,
        nonce_factory=lambda: "nonce",
        sink=sink,
    )


# --------------------------------------------------------------------------- #
# AC1 — contract loading from a GOAL-... file
# --------------------------------------------------------------------------- #
_VALID_CONTRACT = """---
goal_id: GOAL-20260622-000000-demo
goal: Make the docs reflect the code.
success_criteria:
  - id: SC1
    text: link-check passes
    verify: "python scripts/check_docs.py"
    verify_owner: gate
  - id: J1
    text: public symbols are documented
    verify: llm-judge
    verify_owner: checker
termination:
  max_iterations: 6
  no_progress: 2
  no_progress_definition: net-progress
  budget_output_tokens: 120000
max_judge_fraction: 0.5
non_goals:
  - rewriting unchanged docs
anchor_context:
  - README.md
autonomy_level: L1
mandatory_full_review: false
derived_from: SPEC-20260621-064937-goal-loop-phase1
---

## Notes
demo contract
"""


def test_load_contract_valid_file_parses_all_fields(tmp_path):
    path = tmp_path / "GOAL-demo.md"
    path.write_text(_VALID_CONTRACT, encoding="utf-8")
    c = gl.load_contract(path)
    assert c.goal_id == "GOAL-20260622-000000-demo"
    assert len(c.success_criteria) == 2
    assert c.derived_from == "SPEC-20260621-064937-goal-loop-phase1"
    assert c.termination.no_progress_definition == "net-progress"
    assert c.termination.budget_output_tokens == 120000


def test_load_contract_no_frontmatter_rejected(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("no frontmatter here\n", encoding="utf-8")
    with pytest.raises(gl.ContractError):
        gl.load_contract(path)


def test_load_contract_missing_trio_rejected(tmp_path):
    path = tmp_path / "GOAL-trio.md"
    path.write_text("---\ngoal_id: GOAL-x\ngoal: g\nsuccess_criteria: []\n---\n", encoding="utf-8")
    with pytest.raises(gl.ContractError):
        gl.load_contract(path)


# --------------------------------------------------------------------------- #
# AC1 / AC3 — contract validation
# --------------------------------------------------------------------------- #
def test_empty_criteria_rejected():
    with pytest.raises(gl.ContractError):
        gl.validate_contract(make_contract([]))


def test_all_judge_contract_rejected():
    with pytest.raises(gl.ContractError, match="all-judge"):
        gl.validate_contract(make_contract([judge("J1")], max_judge=1.0))


def test_judge_fraction_cap_enforced():
    crits = [det("SC1"), judge("J1"), judge("J2")]  # 2/3 > 0.5
    with pytest.raises(gl.ContractError, match="judge fraction"):
        gl.validate_contract(make_contract(crits, max_judge=0.5))


def test_judge_must_be_checker_owned():
    bad = gl.Criterion(id="J1", text="", verify="llm-judge", verify_owner="gate")
    with pytest.raises(gl.ContractError, match="verify_owner: checker"):
        gl.validate_contract(make_contract([det("SC1"), bad]))


def test_duplicate_criterion_ids_rejected():
    with pytest.raises(gl.ContractError, match="duplicate"):
        gl.validate_contract(make_contract([det("SC1"), det("SC1")]))


def test_unknown_no_progress_definition_rejected():
    c = make_contract([det("SC1")])
    c = gl.GoalContract(
        goal_id=c.goal_id,
        goal=c.goal,
        success_criteria=c.success_criteria,
        termination=gl.Termination(8, 2, "bogus", 200_000),
    )
    with pytest.raises(gl.ContractError, match="no_progress_definition"):
        gl.validate_contract(c)


# --------------------------------------------------------------------------- #
# AC4 — termination ladder
# --------------------------------------------------------------------------- #
def test_goal_met_when_verifier_green(tmp_path):
    res = run(make_contract([det("SC1")]), tmp_path / "s.json", verifier=FakeVerifier(gate=True))
    assert res.outcome is gl.Outcome.GOAL_MET
    assert res.green == ("SC1",)


def test_max_iterations_backstop(tmp_path):
    model = FakeModel()
    res = run(
        # no_progress disabled (99) so the max_iterations rung is the binding backstop
        make_contract([det("SC1")], max_iterations=3, no_progress=99),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=False),
        model=model,
    )
    assert res.outcome is gl.Outcome.MAX_ITERATIONS
    assert "PARKED" in res.report
    assert len(model.builds) == 3  # three build ticks then park


def test_no_progress_oscillation_does_not_evade_backstop(tmp_path):
    # SC1 never passes; SC2 flips green/red. Net green never rises above 1, so the
    # net-progress counter must still fire despite SC2 going green repeatedly.
    crits = [det("SC1", verify="cmd1"), det("SC2", verify="cmd2")]
    verifier = FakeVerifier(commands={"cmd1": False, "cmd2": alternator(start=True)})
    res = run(
        make_contract(crits, no_progress=2, max_iterations=50),
        tmp_path / "s.json",
        verifier=verifier,
    )
    assert res.outcome is gl.Outcome.NO_PROGRESS


def test_budget_backstop_reports_overshoot(tmp_path):
    res = run(
        make_contract([det("SC1")], budget=50),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=False),
        model=FakeModel(build_tokens=100),
    )
    assert res.outcome is gl.Outcome.BUDGET
    assert res.output_tokens >= 50  # a complete tick may overshoot the ceiling


# --------------------------------------------------------------------------- #
# AC5 — verifier-tamper tripwire
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "paths,added,expected",
    [
        (("tests/test_x.py",), (), True),
        (("conftest.py",), (), True),
        (("pyproject.toml",), (), True),
        (("tox.ini",), (), True),
        (("scripts/quality_gate.py",), (), True),
        (("scripts/goal_loop.py",), (), True),  # the driver itself is verifier surface
        (("src/app.py",), ("x = 1",), False),
        (("src/app.py",), ("y = 2  # pragma: no cover",), True),
    ],
)
def test_tamper_tripwire_paths(paths, added, expected):
    contract = make_contract([det("SC1")])
    assert gl.tamper_tripwire(gl.Diff(paths, added), contract) is expected


def test_tamper_tripwire_catches_script_verifier():
    contract = make_contract([det("SC1", verify="bash check.sh")])
    assert "check.sh" in gl.verify_command_targets(contract)
    assert gl.tamper_tripwire(gl.Diff(("check.sh",), ()), contract) is True


def test_tamper_tick_forces_gate_and_does_not_count(tmp_path):
    # Every build touches a test file and the gate rejects -> no criterion counts.
    model = FakeModel(diff=gl.Diff(("tests/test_x.py",), ()))
    gate = FakeGate(label="Reject")
    res = run(
        make_contract([det("SC1")], max_iterations=2),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        model=model,
        gate=gate,
    )
    assert gate.requests  # the tamper gate fired
    assert res.outcome is not gl.Outcome.GOAL_MET  # rejected tick never reached goal-met


# --------------------------------------------------------------------------- #
# AC8 — loop-state integrity + untrusted-on-read reconstruct
# --------------------------------------------------------------------------- #
def test_loop_state_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T", iteration=2)
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=True, verified_by="gate")
    gl.write_loop_state(path, state)
    loaded = gl.read_loop_state(path)
    assert loaded is not None
    assert loaded.iteration == 2
    assert loaded.criteria["SC1"].green is True


def test_tampered_loop_state_raises_integrity_error(tmp_path):
    path = tmp_path / "s.json"
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=False)
    gl.write_loop_state(path, state)
    raw = json.loads(path.read_text())
    raw["criteria"]["SC1"]["green"] = True  # flip without recomputing the integrity hash
    path.write_text(json.dumps(raw))
    with pytest.raises(gl.LoopStateIntegrityError):
        gl.read_loop_state(path)


def test_reconstruct_resets_false_green_for_deterministic(tmp_path):
    # AC8-neg: a stored green that no longer verifies is re-derived to red.
    contract = make_contract([det("SC1")])
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=True, verified_by="gate")
    rebuilt = gl.reconstruct(
        contract, state, verifier=FakeVerifier(gate=False), checker_verified_green=frozenset()
    )
    assert rebuilt.criteria["SC1"].green is False


def test_integrity_failure_parks_the_run(tmp_path):
    path = tmp_path / "s.json"
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=False)
    gl.write_loop_state(path, state)
    raw = json.loads(path.read_text())
    raw["criteria"]["SC1"]["green"] = True
    path.write_text(json.dumps(raw))
    res = run(make_contract([det("SC1")]), path)
    assert res.outcome is gl.Outcome.PARKED


def test_resume_does_not_rebuild_a_verified_green(tmp_path):
    # AC8-pos: a legitimately green criterion is re-derived green and never rebuilt.
    path = tmp_path / "s.json"
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T", iteration=1)
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=True, verified_by="gate")
    gl.write_loop_state(path, state)
    model = FakeModel()
    res = run(make_contract([det("SC1")]), path, verifier=FakeVerifier(gate=True), model=model)
    assert res.outcome is gl.Outcome.GOAL_MET
    assert model.builds == []  # the green criterion was never rebuilt


# --------------------------------------------------------------------------- #
# AC10 — fail-closed L2 autonomy
# --------------------------------------------------------------------------- #
def test_l2_unaffirmable_runs_as_l1_not_park(tmp_path):
    res = run(
        make_contract([det("SC1")], autonomy="L2"),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        auth=FakeAuth(False),
    )
    assert res.outcome is gl.Outcome.GOAL_MET  # report-only L1, still does useful work


def test_l2_revoked_mid_run_parks(tmp_path):
    # affirmed at start + tick 1, revoked by tick 2 -> park.
    res = run(
        make_contract([det("SC1")], autonomy="L2", max_iterations=10),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=False),
        auth=FakeAuth([True, True, False]),
    )
    assert res.outcome is gl.Outcome.PARKED
    assert "revoked" in res.report


# --------------------------------------------------------------------------- #
# AC3 — judge governance: distinct checker agent id, re-verify, corroboration
# --------------------------------------------------------------------------- #
def test_judge_green_attributed_to_distinct_checker_agent(tmp_path):
    crits = [det("SC1"), judge("J1")]
    model = FakeModel(build_agent="builder-1", judge_agent="checker-1", judge_green=True)
    path = tmp_path / "s.json"
    res = run(make_contract(crits), path, verifier=FakeVerifier(gate=True), model=model)
    assert res.outcome is gl.Outcome.GOAL_MET
    state = gl.read_loop_state(path)
    # the judge green is recorded as a CHECKER turn with a DISTINCT agent id (AC3)
    assert state.criteria["J1"].verified_by == "checker"
    assert state.criteria["J1"].verified_by_agent == "checker-1"
    assert state.criteria["J1"].verified_by_agent != "builder-1"
    # the deterministic criterion is gate-verified, never a conductor turn
    assert state.criteria["SC1"].verified_by == "gate"
    assert state.criteria["SC1"].verified_by_agent == "deterministic"


def test_goal_met_reverify_rejudges_no_stale_green(tmp_path):
    # AC3/R5.4: a judge green on the building tick that flips red on the goal-met
    # re-verify must NOT carry the exit.
    seq = iter([True, False, False, False, False])
    model = FakeModel(judge_green=lambda c: next(seq, False))
    res = run(
        make_contract([det("SC1"), judge("J1")], max_iterations=2),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        model=model,
    )
    assert res.outcome is not gl.Outcome.GOAL_MET
    assert "J1" in res.red
    assert len(model.judges) >= 2  # the criterion was actually re-judged


def test_delta_only_checker_catches_builder_defect(tmp_path):
    # AC5-adversarial: a judge criterion the builder would self-approve is judged RED by
    # the independent checker (a separate process), so the defect never counts green.
    crits = [det("SC1"), judge("J1")]
    model = FakeModel(judge_green=False, build_agent="builder-1", judge_agent="checker-1")
    res = run(
        make_contract(crits, max_iterations=3),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        model=model,
    )
    assert res.outcome is not gl.Outcome.GOAL_MET
    assert "J1" in res.red
    assert model.judges  # the checker really ran on the delta


def test_reconstruct_judge_green_requires_event_corroboration(tmp_path):
    # AC8-neg for judge criteria: a claimed judge green is trusted on resume only if an
    # append-only checker event corroborates it; otherwise it is reset to red.
    contract = make_contract([det("SC1"), judge("J1")])
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.criteria["SC1"] = gl.CriterionStatus(
        id="SC1", green=True, verified_by="gate", verified_by_agent="deterministic"
    )
    state.criteria["J1"] = gl.CriterionStatus(
        id="J1", green=True, verified_by="checker", verified_by_agent="checker-1"
    )
    uncorroborated = gl.reconstruct(
        contract, state, verifier=FakeVerifier(gate=True), checker_verified_green=frozenset()
    )
    assert uncorroborated.criteria["J1"].green is False
    corroborated = gl.reconstruct(
        contract, state, verifier=FakeVerifier(gate=True), checker_verified_green=frozenset({"J1"})
    )
    assert corroborated.criteria["J1"].green is True
    assert corroborated.criteria["J1"].verified_by_agent == "checker-1"


def test_checker_greens_from_events_collects_green_judge_tags(tmp_path):
    events = tmp_path / "events.jsonl"
    rows = [
        {"intent": "proposal", "tags": ["builder", "tick-1"]},
        {"intent": "critique", "tags": ["checker", "tick-1", "green:J1"]},
        {"intent": "critique", "tags": ["checker", "tick-2", "red:J2"]},  # red not collected
        {"intent": "critique", "tags": ["other"]},  # not a checker turn
    ]
    with events.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.write("not-json-line\n")  # tolerated, skipped
    assert gl.checker_greens_from_events(events) == frozenset({"J1"})


def test_checker_greens_from_events_absent_file(tmp_path):
    assert gl.checker_greens_from_events(tmp_path / "nope.jsonl") == frozenset()


# --------------------------------------------------------------------------- #
# AC7 — capture (structural ordering)
# --------------------------------------------------------------------------- #
def test_capture_emits_builder_then_checker_per_tick_and_terminal(tmp_path):
    sink = FakeSink()
    res = run(
        make_contract([det("SC1")]),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        sink=sink,
    )
    kinds = [e[0] for e in sink.events]
    assert kinds[0] == "builder"  # a tick opens with the builder turn
    assert kinds[-1] == "close"  # the run seals the discussion last (R7)
    assert kinds[-2] == "termination"  # preceded by exactly one termination decision
    assert kinds.count("termination") == 1 and kinds.count("close") == 1
    assert kinds.count("builder") == res.iterations  # one build per tick == loop-state iteration
    assert kinds.count("checker") >= res.iterations  # each tick contributes a checker turn


@pytest.mark.parametrize(
    "gate_result,maxit,expected",
    [
        (True, 8, gl.Outcome.GOAL_MET),
        (False, 2, gl.Outcome.MAX_ITERATIONS),
    ],
)
def test_capture_terminal_decision_for_each_exit(tmp_path, gate_result, maxit, expected):
    sink = FakeSink()
    res = run(
        make_contract([det("SC1")], max_iterations=maxit, no_progress=99),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=gate_result),
        sink=sink,
    )
    assert res.outcome is expected
    terminal = [e for e in sink.events if e[0] == "termination"]
    assert len(terminal) == 1 and terminal[0][1] is expected


# --------------------------------------------------------------------------- #
# AC6 — gate binding (per-gate token, one-shot, transport parity)
# --------------------------------------------------------------------------- #
def test_gate_binding_one_shot_and_at_most_one_open():
    b = gl.GateBinding()
    b.open("tok-A")
    with pytest.raises(gl.GateError):
        b.open("tok-B")  # at most one open gate at a time
    assert b.consume("tok-A", "Approve") == "Approve"
    assert b.consume("tok-A", "Approve") is None  # one-shot: already consumed -> no open gate


def test_bound_gate_router_parity_across_transports():
    # The same binding resolves identically whether the transport simulates AskUserQuestion
    # (keyboard) or collab_loop (AFK).
    keyboard = gl.BoundGateRouter(lambda q, c, t: "Approve")
    afk = gl.BoundGateRouter(lambda q, c, t: "Approve")
    assert keyboard.request("q", ("Approve", "Reject"), "t1") == "Approve"
    assert afk.request("q", ("Approve", "Reject"), "t1") == "Approve"


def test_bound_gate_router_nonmatch_and_timeout_are_no_action():
    nonmatch = gl.BoundGateRouter(lambda q, c, t: "Banana")  # label not in choices
    timeout = gl.BoundGateRouter(lambda q, c, t: None)  # no reply
    assert nonmatch.request("q", ("Approve", "Reject"), "t") == gl.NO_ACTION
    assert timeout.request("q", ("Approve", "Reject"), "t") == gl.NO_ACTION


def test_bound_gate_router_replayed_token_finds_no_open_gate():
    binding = gl.GateBinding()
    router = gl.BoundGateRouter(lambda q, c, t: "Approve", binding)
    assert router.request("q", ("Approve", "Reject"), "t1") == "Approve"
    assert binding.consume("t1", "Approve") is None  # a replayed/pre-armed label is inert


# --------------------------------------------------------------------------- #
# Pure helpers — diff parsing, prompts, verdict parsing, claude JSON
# --------------------------------------------------------------------------- #
def test_parse_unified_diff_extracts_paths_and_added_lines():
    diff = (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1,2 @@\n"
        " existing\n"
        "+new line\n"
        "+sneaky  # pragma: no cover\n"
    )
    d = gl.parse_unified_diff(diff)
    assert "src/x.py" in d.paths
    assert "new line" in d.added_lines
    assert any("pragma" in line for line in d.added_lines)  # tripwire can see it


def test_parse_unified_diff_captures_deletion_path():
    # Review fold (security HIGH-1): a deletion (+++ /dev/null) must surface its path so
    # deleting the test that enforces a criterion trips the tamper tripwire.
    d = gl.parse_unified_diff("--- a/tests/test_x.py\n+++ /dev/null\n")
    assert d.paths == ("tests/test_x.py",)
    assert gl.tamper_tripwire(d, make_contract([det("SC1")])) is True


def test_parse_unified_diff_captures_rename_paths():
    diff = "rename from tests/old_test.py\nrename to tests/new_test.py\n"
    d = gl.parse_unified_diff(diff)
    assert "tests/old_test.py" in d.paths and "tests/new_test.py" in d.paths


def test_parse_unified_diff_ignores_removed_content_line_lookalike():
    # A removed content line "--- foo" (no a/ b/ prefix) must NOT be read as a file header.
    d = gl.parse_unified_diff("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n---- not a header\n")
    assert d.paths == ("x.py",)


def test_paths_from_name_status_includes_deletes_and_renames():
    text = "M\tsrc/a.py\nD\ttests/test_b.py\nR100\told/c.py\tnew/c.py\n"
    paths = gl._paths_from_name_status(text)
    assert "src/a.py" in paths and "tests/test_b.py" in paths
    assert "old/c.py" in paths and "new/c.py" in paths


@pytest.mark.parametrize(
    "text,green",
    [
        ('{"green": true, "reason": "ok"}', True),
        ('noise {"green": false, "reason": "no"} tail', False),
        ("not json at all", False),  # fail-closed
        ('{"reason": "missing green key"}', False),  # fail-closed
    ],
)
def test_parse_judge_verdict_fail_closed(text, green):
    g, reason = gl.parse_judge_verdict(text)
    assert g is green
    assert reason  # a reason is always present, especially on red


def test_parse_claude_json_extracts_usage_and_session():
    out = json.dumps({"result": "done", "usage": {"output_tokens": 42}, "session_id": "abc"})
    assert gl._parse_claude_json(out) == ("done", 42, "abc")


def test_parse_claude_json_tolerates_non_json():
    text, tokens, sid = gl._parse_claude_json("plain text not json")
    assert tokens == 0 and sid == ""


def test_build_prompt_delimits_anchor_as_untrusted():
    c = gl.GoalContract(
        goal_id="G",
        goal="do x",
        success_criteria=(det("SC1"),),
        termination=gl.Termination(),
        anchor_context=("spec.md",),
    )
    p = gl.build_prompt(c, det("SC1"), "ctx")
    assert "UNTRUSTED" in p and "spec.md" in p and "orchestrating-goal-loops" in p


def test_judge_prompt_is_delta_only_and_skeptical():
    p = gl.judge_prompt(judge("J1"), gl.Diff(("src/x.py",), ("+code",)))
    assert "INDEPENDENT CHECKER" in p and "src/x.py" in p
    assert "default to red" in p.lower()


# --------------------------------------------------------------------------- #
# IO seams — exercised with injected runner / writer (no real CLI / pipeline)
# --------------------------------------------------------------------------- #
class _FakeProc:
    def __init__(self, stdout):
        self.stdout = stdout


class _FixedDiffSource:
    def tick_diff(self):
        return gl.Diff(("src/x.py",), ("+x",))


def test_subprocess_invoker_build_and_judge_have_distinct_agents(tmp_path):
    def runner(cmd, **kwargs):
        prompt = cmd[2]
        if "BUILDER" in prompt:
            return _FakeProc(
                json.dumps(
                    {"result": "built", "usage": {"output_tokens": 10}, "session_id": "sess-build"}
                )
            )
        return _FakeProc(
            json.dumps(
                {
                    "result": '{"green": true, "reason": "ok"}',
                    "usage": {"output_tokens": 5},
                    "session_id": "sess-judge",
                }
            )
        )

    inv = gl.SubprocessModelInvoker(
        tmp_path, _FixedDiffSource(), claude_bin="claude.CMD", runner=runner
    )
    contract = make_contract([det("SC1"), judge("J1")])
    b = inv.build(contract, det("SC1"), "ctx")
    j = inv.judge(judge("J1"), gl.Diff((), ()))
    assert b.agent_id == "sess-build" and b.diff.paths == ("src/x.py",)
    assert j.green is True and j.agent_id == "sess-judge"
    assert b.agent_id != j.agent_id  # builder and checker are distinct (AC3/R4)


def test_resolve_claude_uses_shutil_which(monkeypatch):
    import shutil

    monkeypatch.setattr(
        shutil, "which", lambda name: "C:/x/claude.CMD" if name == "claude" else None
    )
    assert gl._resolve_claude() == "C:/x/claude.CMD"


def test_resolve_claude_raises_when_absent(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(gl.GoalLoopError):
        gl._resolve_claude()


def test_real_capture_sink_intents_and_corroboration_tags():
    written = []

    def writer(disc, agent, intent, content, tags=None):
        written.append((agent, intent, tuple(tags or [])))
        return len(written)

    sink = gl.RealCaptureSink("DISC-T", writer=writer)
    sink.builder_turn(1, "SC1", "delta")
    sink.checker_turn(
        1,
        (
            gl.Verification("J1", True, True, "checker-1"),
            gl.Verification("SC1", True, False, "deterministic"),
        ),
    )
    sink.gate_result(1, "q?", "Approve")
    sink.termination_decision(gl.Outcome.GOAL_MET, "done")
    assert [w[1] for w in written] == ["proposal", "critique", "decision", "decision"]
    assert written[0][0] == "facilitator" and written[1][0] == "independent-perspective"
    checker_tags = written[1][2]
    assert "checker" in checker_tags and "green:J1" in checker_tags
    assert "green:SC1" not in checker_tags  # only judge greens are corroborated via events


def test_failclosed_auth_never_affirms_main():
    a = gl.FailClosedAuthAffirmer(frozenset({"main", "feature/x"}))
    assert a.affirm_l2("main") is False
    assert a.affirm_l2("feature/x") is True
    assert a.affirm_l2("feature/other") is False


def test_default_loop_state_path_sanitizes(tmp_path):
    p = gl.default_loop_state_path(tmp_path, "GOAL-2026/slug")
    assert p.parent.name == ".state"
    assert "/" not in p.name and p.suffix == ".json"


def test_goal_met_report_demands_review_and_education(tmp_path):
    res = run(make_contract([det("SC1")]), tmp_path / "s.json", verifier=FakeVerifier(gate=True))
    assert res.outcome is gl.Outcome.GOAL_MET
    assert "/review" in res.report and "education" in res.report


# --------------------------------------------------------------------------- #
# AC9 / AC12 — bounded facilitator delta + ADR present (doc anchors)
# --------------------------------------------------------------------------- #
_REPO = Path(__file__).resolve().parent.parent


def test_facilitator_has_single_goal_loop_subsection():
    text = (_REPO / ".claude/agents/facilitator.md").read_text(encoding="utf-8")
    assert "Goal-Seeking Loop Mode" in text


def test_adr_0026_present():
    assert (_REPO / "docs/adr/ADR-0026-goal-driven-loop-orchestration.md").exists()


def test_loops_in_claude_md_directory_layout():
    text = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert "loops/" in text  # AC12: loops/ added to the Directory Layout


# --------------------------------------------------------------------------- #
# Review folds — termination semantics, capture sealing, claude JSON, CLI
# --------------------------------------------------------------------------- #
def test_no_progress_criterion_id_consecutive_resets_on_improvement():
    # QA F1: the criterion-id-consecutive branch is live, selectable logic — it resets
    # when this tick's green count beats the PREVIOUS tick's (not the historical best).
    c = make_contract([det("SC1"), det("SC2")])
    c = dataclasses.replace(
        c, termination=gl.Termination(8, 2, "criterion-id-consecutive", 200_000)
    )
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.green_count_history = [1, 0]  # was 1, dropped to 0
    state.no_progress_counter = 1
    state.criteria = {
        "SC1": gl.CriterionStatus("SC1", green=True),
        "SC2": gl.CriterionStatus("SC2", green=False),
    }
    gl.update_no_progress(state, c)
    assert state.no_progress_counter == 0  # current 1 > previous 0 -> reset


def test_fixed_red_set_no_progress_definition_now_rejected():
    # Arch LOW-3: "fixed-red-set" silently aliased net-progress; it is now rejected
    # (deferred to Phase 2) rather than shipped as a synonym.
    c = make_contract([det("SC1")])
    c = dataclasses.replace(c, termination=gl.Termination(8, 2, "fixed-red-set", 200_000))
    with pytest.raises(gl.ContractError, match="no_progress_definition"):
        gl.validate_contract(c)


def test_no_progress_equals_1_halts_after_one_red_tick(tmp_path):
    # QA F9: the tightest no_progress boundary.
    res = run(
        make_contract([det("SC1")], no_progress=1, max_iterations=50),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=False),
    )
    assert res.outcome is gl.Outcome.NO_PROGRESS
    assert res.iterations == 1


def test_verify_command_targets_unmatched_quote_falls_back():
    # QA F2 (canary): a malformed verify string must not raise inside the tamper path.
    bad = gl.Criterion(id="SC1", text="", verify='python "bad.py', verify_owner="gate")
    targets = gl.verify_command_targets(make_contract([bad]))
    assert isinstance(targets, set)  # shlex.ValueError -> fallback split, did not raise


def test_verify_command_targets_make_resolves_to_makefile():
    # QA F10: `make test` resolves to the Makefile so editing it trips the tripwire.
    c = gl.Criterion(id="SC1", text="", verify="make test", verify_owner="gate")
    targets = gl.verify_command_targets(make_contract([c]))
    assert "Makefile" in targets and "makefile" in targets
    assert gl.tamper_tripwire(gl.Diff(("Makefile",), ()), make_contract([c])) is True


def test_verify_command_targets_normalizes_dot_slash():
    # Security LOW-6: `bash ./check.sh` target matches a diff path of `check.sh`.
    c = gl.Criterion(id="SC1", text="", verify="bash ./check.sh", verify_owner="gate")
    assert "check.sh" in gl.verify_command_targets(make_contract([c]))
    assert gl.tamper_tripwire(gl.Diff(("check.sh",), ()), make_contract([c])) is True


def test_parse_claude_json_non_dict_valid_json():
    # QA F3: valid JSON that is not an object -> raw text, 0 tokens, no session.
    text, tokens, sid = gl._parse_claude_json('["not", "an", "object"]')
    assert tokens == 0 and sid == "" and "not" in text


def test_parse_claude_json_non_integer_output_tokens():
    # QA F4: a non-int output_tokens fails safe to 0 (budget accounting must not crash).
    out = json.dumps({"result": "r", "usage": {"output_tokens": "bad"}, "session_id": "s"})
    text, tokens, sid = gl._parse_claude_json(out)
    assert tokens == 0 and text == "r" and sid == "s"


def test_main_invalid_contract_exits_2(tmp_path, capsys):
    # QA F5: the CLI's contract-load-error -> exit 2 contract (callers gate on it).
    bad = tmp_path / "GOAL-bad.md"
    bad.write_text("no frontmatter here\n", encoding="utf-8")
    rc = gl.main([str(bad)])
    assert rc == 2 and "goal-loop:" in capsys.readouterr().err


def test_main_validate_only_exits_0(tmp_path):
    path = tmp_path / "GOAL-demo.md"
    path.write_text(_VALID_CONTRACT, encoding="utf-8")
    assert gl.main([str(path), "--validate-only"]) == 0


def test_load_contract_unterminated_frontmatter_rejected(tmp_path):
    # QA F6: an unterminated frontmatter block is a realistic authoring mistake.
    path = tmp_path / "GOAL-unt.md"
    path.write_text("---\ngoal_id: GOAL-x\ngoal: g\n", encoding="utf-8")
    with pytest.raises(gl.ContractError):
        gl.load_contract(path)


def test_load_contract_list_frontmatter_rejected(tmp_path):
    path = tmp_path / "GOAL-list.md"
    path.write_text("---\n- a\n- b\n---\n", encoding="utf-8")
    with pytest.raises(gl.ContractError, match="not a mapping"):
        gl.load_contract(path)


def test_reverify_overshoot_does_not_block_goal_met(tmp_path):
    # QA F7: budget exhausted during the goal-met re-verify must not flip the exit to
    # BUDGET -- goal_met takes ladder priority once all criteria are green.
    crits = [det("SC1"), judge("J1")]
    model = FakeModel(judge_green=True, judge_tokens=300_000)
    res = run(
        make_contract(crits, budget=100_000),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        model=model,
    )
    assert res.outcome is gl.Outcome.GOAL_MET


def test_goal_met_report_surfaces_mandatory_full_review(tmp_path):
    # QA F8 / AC2: a critical-risk contract (mandatory_full_review) surfaces it at goal-met.
    contract = gl.GoalContract(
        goal_id="GOAL-T",
        goal="g",
        success_criteria=(det("SC1"),),
        termination=gl.Termination(),
        mandatory_full_review=True,
    )
    res = run(contract, tmp_path / "s.json", verifier=FakeVerifier(gate=True))
    assert res.outcome is gl.Outcome.GOAL_MET
    assert "mandatory_full_review" in res.report


def test_checker_greens_from_events_empty_file(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text("", encoding="utf-8")
    assert gl.checker_greens_from_events(p) == frozenset()


def test_capture_ordering_on_approved_tamper_is_builder_gate_checker(tmp_path):
    # QA F12: on an approved tamper tick the events are builder -> gate -> checker.
    sink = FakeSink()
    model = FakeModel(diff=gl.Diff(("tests/test_x.py",), ()))
    run(
        make_contract([det("SC1")], max_iterations=1),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        model=model,
        gate=FakeGate(label="Approve"),
        sink=sink,
    )
    kinds = [e[0] for e in sink.events]
    assert kinds.index("gate") < kinds.index("checker")


def test_run_seals_discussion_via_sink_close(tmp_path):
    # Arch HIGH-1 / Scenario-C: every terminal path seals the discussion (R7).
    sink = FakeSink()
    run(
        make_contract([det("SC1")]),
        tmp_path / "s.json",
        verifier=FakeVerifier(gate=True),
        sink=sink,
    )
    assert ("close",) in sink.events


def test_integrity_park_also_seals(tmp_path):
    path = tmp_path / "s.json"
    state = gl.LoopState(goal_id="GOAL-T", discussion_id="DISC-T")
    state.criteria["SC1"] = gl.CriterionStatus(id="SC1", green=False)
    gl.write_loop_state(path, state)
    raw = json.loads(path.read_text())
    raw["criteria"]["SC1"]["green"] = True
    path.write_text(json.dumps(raw))
    sink = FakeSink()
    res = run(make_contract([det("SC1")]), path, sink=sink)
    assert res.outcome is gl.Outcome.PARKED
    assert ("close",) in sink.events  # sealed even on the early integrity-park


def test_real_capture_sink_close_calls_closer():
    closed = []
    sink = gl.RealCaptureSink("DISC-T", writer=lambda *a, **k: 1, closer=closed.append)
    sink.close()
    assert closed == ["DISC-T"]
