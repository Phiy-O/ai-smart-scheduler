
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ScheduleEventDB(Base):
    __tablename__ = "schedule_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    title: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    category: Mapped[str] = mapped_column(
        String(20), default="fixed"
    )


class ScheduleProposalDB(Base):
    __tablename__ = "schedule_proposals"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    title: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date] = mapped_column(Date)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    preferred_period: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    original_instruction: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )

    approved_option_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    options: Mapped[list["ProposalOptionDB"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ProposalOptionDB.id",
    )


class ProposalOptionDB(Base):
    __tablename__ = "proposal_options"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_proposals.id"),
        index=True,
    )

    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    score: Mapped[float] = mapped_column(Float)

    proposal: Mapped[ScheduleProposalDB] = relationship(
        back_populates="options"
    )
