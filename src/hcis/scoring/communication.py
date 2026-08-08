from __future__ import annotations

from pydantic import BaseModel, Field


class CommunicationDemand(BaseModel):
    spoken_english_intensity: int = Field(ge=1, le=5)
    customer_facing_ratio: str
    presentation_frequency: str
    sales_persuasion_load: str
    negotiation_load: str
    unstructured_conversation_load: str
    prepared_communication_ratio: str
    current_communication_fit: float = Field(ge=0, le=100)
    improvement_feasibility: float = Field(ge=0, le=100)


def communication_lane(demand: CommunicationDemand) -> str:
    if demand.current_communication_fit >= 70:
        return "PRIORITIZE"
    if demand.improvement_feasibility >= 65:
        return "PREPARE_AND_STRETCH"
    return "HIGH_DIFFICULTY_KEEP"
