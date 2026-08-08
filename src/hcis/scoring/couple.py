from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoupleCombination:
    william_job_id: str
    girlfriend_job_id: str
    coordination_type: str
    coordination_bonus: float
    combined_score: float


def combine(
    william_job_id: str,
    girlfriend_job_id: str,
    william_metro: str,
    girlfriend_metro: str,
    william_score: float,
    girlfriend_score: float,
) -> CoupleCombination:
    if william_metro == girlfriend_metro:
        coordination_type, bonus = "SAME_METRO", 5.0
    elif {william_metro, girlfriend_metro} <= {"New York", "Philadelphia"}:
        coordination_type, bonus = "COMMUTABLE", 3.0
    else:
        coordination_type, bonus = "TEMPORARY_LONG_DISTANCE", 0.0
    return CoupleCombination(
        william_job_id,
        girlfriend_job_id,
        coordination_type,
        bonus,
        round((william_score + girlfriend_score) / 2 + bonus, 2),
    )
