from datetime import datetime, timedelta, timezone

from triage.agent.policy import AgentPolicy, Decision
from triage.agent.tools.base import ToolResult
from triage.domain.incident_policy import recurrence_needs_human


def _after(policy: AgentPolicy, **kwargs):
    defaults = dict(
        round_index=1,
        tokens_used=10,
        repeats={},
        tool_name=None,
        result=None,
        claimed_fix=False,
        verified_healthy=False,
    )
    defaults.update(kwargs)
    return policy.after_round(**defaults)


def test_escalate_tool_needs_human():
    policy = AgentPolicy()
    verdict = _after(
        policy, result=ToolResult(ok=True, output="secrets", escalate=True)
    )
    assert verdict is not None
    assert verdict.decision == Decision.NEEDS_HUMAN


def test_repeat_tool_args_three_times():
    policy = AgentPolicy(repeat_limit=3)
    key = 'read_file:{"path": "a.py"}'
    assert (
        _after(
            policy,
            repeats={key: 2},
            tool_name=key,
            result=ToolResult(ok=True, output=""),
        )
        is None
    )
    verdict = _after(
        policy, repeats={key: 3}, tool_name=key, result=ToolResult(ok=True, output="")
    )
    assert verdict.decision == Decision.NEEDS_HUMAN


def test_sandbox_and_shell_denied():
    policy = AgentPolicy()
    assert (
        _after(
            policy, result=ToolResult(ok=False, output="out", sandbox_violation=True)
        ).decision
        == Decision.NEEDS_HUMAN
    )
    assert (
        _after(
            policy, result=ToolResult(ok=False, output="denied", denied=True)
        ).decision
        == Decision.NEEDS_HUMAN
    )


def test_claimed_fix_and_health_resolves():
    policy = AgentPolicy()
    verdict = _after(policy, claimed_fix=True, verified_healthy=True)
    assert verdict.decision == Decision.RESOLVED
    assert _after(policy, claimed_fix=True, verified_healthy=False) is None


def test_rounds_and_tokens():
    policy = AgentPolicy(max_rounds=12, token_budget=100)
    assert _after(policy, round_index=12).decision == Decision.NEEDS_HUMAN
    assert _after(policy, tokens_used=101).decision == Decision.NEEDS_HUMAN


def test_recurrence_cooldown():
    now = datetime.now(timezone.utc)
    assert not recurrence_needs_human(None, now, 3600)
    assert recurrence_needs_human(now - timedelta(minutes=10), now, 3600)
    assert not recurrence_needs_human(now - timedelta(hours=2), now, 3600)
    policy = AgentPolicy(cooldown_seconds=3600)
    early = policy.on_start(
        last_resolved_at=now - timedelta(minutes=5), now=now, auto_fix=True
    )
    assert early is not None and early.decision == Decision.NEEDS_HUMAN
    assert (
        policy.on_start(last_resolved_at=None, now=now, auto_fix=False).decision
        == Decision.NEEDS_HUMAN
    )
    assert policy.on_start(last_resolved_at=None, now=now, auto_fix=True) is None
