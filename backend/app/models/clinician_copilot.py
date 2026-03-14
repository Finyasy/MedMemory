"""Persistence models for clinician copilot runs, steps, and suggestions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ClinicianAgentRun(Base, TimestampMixin):
    """One bounded clinician copilot execution for a patient."""

    __tablename__ = "clinician_agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinician_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="completed",
        comment="running|completed|failed",
    )
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    steps: Mapped[list["ClinicianAgentStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ClinicianAgentStep.step_order.asc()",
    )
    suggestions: Mapped[list["ClinicianAgentSuggestion"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ClinicianAgentSuggestion.suggestion_order.asc()",
    )

    __table_args__ = (
        Index(
            "ix_clinician_agent_runs_patient_created",
            "patient_id",
            "created_at",
        ),
        Index(
            "ix_clinician_agent_runs_clinician_created",
            "clinician_user_id",
            "created_at",
        ),
    )


class ClinicianAgentStep(Base, TimestampMixin):
    """One tool execution within a clinician copilot run."""

    __tablename__ = "clinician_agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("clinician_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="completed",
        comment="completed|failed",
    )
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["ClinicianAgentRun"] = relationship(back_populates="steps")

    __table_args__ = (
        Index(
            "ix_clinician_agent_steps_run_order",
            "run_id",
            "step_order",
        ),
    )


class ClinicianAgentSuggestion(Base, TimestampMixin):
    """Non-side-effectful clinician suggestions derived from a run."""

    __tablename__ = "clinician_agent_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("clinician_agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggestion_order: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action_target: Mapped[str | None] = mapped_column(String(160), nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["ClinicianAgentRun"] = relationship(back_populates="suggestions")

    __table_args__ = (
        Index(
            "ix_clinician_agent_suggestions_run_order",
            "run_id",
            "suggestion_order",
        ),
    )
