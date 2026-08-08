from __future__ import annotations

from dataclasses import dataclass

from hcis.domain.runtime import DesiredState


@dataclass(frozen=True)
class RecoveryPlan:
    run_services: bool
    run_scheduler: bool
    catch_up_incremental: bool


def plan_recovery(state: DesiredState) -> RecoveryPlan:
    if state == DesiredState.SCHEDULED:
        return RecoveryPlan(True, True, True)
    if state == DesiredState.PAUSED:
        return RecoveryPlan(True, False, False)
    return RecoveryPlan(False, False, False)
