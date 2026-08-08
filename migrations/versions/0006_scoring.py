"""candidate scoring and couple combinations

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source_provenance", sa.JSON(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "candidate_job_scores",
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("candidate_profile_version", sa.Integer(), primary_key=True),
        sa.Column("scoring_algorithm_version", sa.String(50), primary_key=True),
        sa.Column("action_lane", sa.String(40), nullable=False),
        sa.Column("identity_path_score", sa.Float(), nullable=False),
        sa.Column("role_fit_score", sa.Float(), nullable=False),
        sa.Column("experience_feasibility_score", sa.Float(), nullable=False),
        sa.Column("degree_role_relation_score", sa.Float(), nullable=False),
        sa.Column("communication_load_score", sa.Float(), nullable=False),
        sa.Column("communication_fit_score", sa.Float(), nullable=False),
        sa.Column("company_quality_score", sa.Float(), nullable=False),
        sa.Column("startup_growth_score", sa.Float(), nullable=False),
        sa.Column("company_survival_score", sa.Float(), nullable=False),
        sa.Column("location_score", sa.Float(), nullable=False),
        sa.Column("compensation_score", sa.Float(), nullable=False),
        sa.Column("verification_value_score", sa.Float(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("score_components_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        *_common(),
    )
    op.create_table(
        "couple_job_combinations",
        sa.Column("william_job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("girlfriend_job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("scoring_version", sa.String(50), primary_key=True),
        sa.Column("coordination_type", sa.String(50), nullable=False),
        sa.Column("coordination_bonus", sa.Float(), nullable=False),
        sa.Column("combined_score", sa.Float(), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    op.drop_table("couple_job_combinations")
    op.drop_table("candidate_job_scores")
