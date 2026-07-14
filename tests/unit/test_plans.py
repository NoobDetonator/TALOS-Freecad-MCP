from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from aicad.core.context import DocumentStateToken
from aicad.core.tool_registry import build_default_registry
from aicad.orchestration import OrchestrationPlan, PlannedToolCall
from aicad.orchestration.plans import (
    ApprovalGrant,
    PlanApprovalError,
    PlanExecutionError,
    SingleMutationPlanExecutor,
    StalePlanError,
    ValidatedPlan,
)


SESSION = UUID("12345678-1234-5678-1234-567812345678")


def state(revision: int, fingerprint: str) -> DocumentStateToken:
    return DocumentStateToken(
        session_id=SESSION,
        document_id="Document" if revision else None,
        revision=revision,
        document_fingerprint=fingerprint * 64,
        selection_fingerprint="f" * 64,
    )


def proposed_box_plan() -> OrchestrationPlan:
    return OrchestrationPlan(
        intention="Criar uma caixa paramétrica.",
        assumptions=("Dimensões em milímetros.",),
        steps=("Criar e validar a caixa.",),
        message="Plano pronto para aprovação.",
        tool_calls=(
            PlannedToolCall(
                call_id="box-1",
                name="cad.create_box",
                arguments={"length": 10, "width": 20, "height": 30},
                risk="modify",
                requires_confirmation=True,
            ),
        ),
    )


def frozen_plan() -> ValidatedPlan:
    return ValidatedPlan.build(
        proposed_box_plan(),
        state(1, "a"),
        build_default_registry(),
        plan_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )


def test_validated_plan_hash_covers_arguments_and_state() -> None:
    plan = frozen_plan()
    payload = plan.model_dump(mode="json")

    assert len(plan.plan_hash) == 64
    payload["call"]["arguments"]["height"] = 31
    with pytest.raises(ValidationError, match="hash"):
        ValidatedPlan.model_validate(payload)


def test_approval_is_exact_and_short_lived() -> None:
    plan = frozen_plan()
    grant = ApprovalGrant.issue(plan, now=100.0, ttl_seconds=10.0)

    grant.authorize(plan, now=109.0)
    with pytest.raises(PlanApprovalError, match="expired"):
        grant.authorize(plan, now=111.0)

    changed = plan.model_copy(
        update={"plan_hash": "b" * 64},
    )
    with pytest.raises(PlanApprovalError, match="another plan"):
        grant.authorize(changed, now=105.0)


def test_executor_rejects_stale_state_before_mutation() -> None:
    registry = build_default_registry()
    executed: list[dict[str, object]] = []
    registry.bind("cad.create_box", lambda **args: executed.append(args))
    executor = SingleMutationPlanExecutor(
        registry,
        lambda: {"state_token": state(2, "b").model_dump(mode="json")},
        clock=lambda: 101.0,
    )
    plan = ValidatedPlan.build(proposed_box_plan(), state(1, "a"), registry)
    grant = ApprovalGrant.issue(plan, now=100.0)

    with pytest.raises(StalePlanError, match="changed"):
        executor.execute(plan, grant)

    assert executed == []


def test_executor_runs_exactly_one_mutation_and_post_condition() -> None:
    registry = build_default_registry()
    calls: list[str] = []
    registry.bind(
        "cad.create_box",
        lambda **args: calls.append("create") or {"name": "Box", "valid": True},
    )
    registry.bind(
        "cad.validate_document",
        lambda: calls.append("validate") or {"valid": True, "errors": []},
    )
    tokens = iter((state(1, "a"), state(2, "b")))
    executor = SingleMutationPlanExecutor(
        registry,
        lambda: {"state_token": next(tokens).model_dump(mode="json")},
        clock=lambda: 101.0,
    )
    plan = ValidatedPlan.build(proposed_box_plan(), state(1, "a"), registry)

    result = executor.execute(plan, ApprovalGrant.issue(plan, now=100.0))

    assert calls == ["create", "validate"]
    assert result.tool_result["name"] == "Box"
    assert result.state_before.revision == 1
    assert result.state_after.revision == 2


def test_executor_rejects_failed_post_condition_without_retrying_mutation() -> None:
    registry = build_default_registry()
    calls: list[str] = []
    registry.bind(
        "cad.create_box",
        lambda **args: calls.append("create") or {"name": "Box"},
    )
    registry.bind(
        "cad.validate_document",
        lambda: calls.append("validate") or {"valid": False, "errors": ["x"]},
    )
    executor = SingleMutationPlanExecutor(
        registry,
        lambda: {"state_token": state(1, "a").model_dump(mode="json")},
        clock=lambda: 101.0,
    )
    plan = ValidatedPlan.build(proposed_box_plan(), state(1, "a"), registry)

    with pytest.raises(PlanExecutionError, match="post-condition"):
        executor.execute(plan, ApprovalGrant.issue(plan, now=100.0))

    assert calls == ["create", "validate"]
