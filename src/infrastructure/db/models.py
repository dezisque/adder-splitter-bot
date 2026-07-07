from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain import limits
from src.infrastructure.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(128))
    # последняя открытая комната — сюда попадает быстрый ввод «Мясо 2450»
    current_room_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("rooms.id", ondelete="SET NULL", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class RoomModel(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(limits.MAX_ROOM_TITLE_LEN))
    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    invite_token: Mapped[str] = mapped_column(String(32), unique=True)
    currency: Mapped[str] = mapped_column(
        String(3), default=limits.DEFAULT_CURRENCY, server_default=text("'RUB'")
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    deletion_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class ParticipantModel(Base):
    __tablename__ = "participants"
    __table_args__ = (
        Index("ix_participants_room_id", "room_id"),
        Index(
            "uq_participants_room_id_user_id",
            "room_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    room_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("rooms.id"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    display_name: Mapped[str] = mapped_column(String(limits.MAX_MEMBER_NAME_LEN))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class ExpenseModel(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_expenses_room_id_created_at", "room_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    room_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("rooms.id"))
    kind: Mapped[str] = mapped_column(String(16), server_default=text("'expense'"))
    paid_by_participant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("participants.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(limits.MAX_EXPENSE_DESCRIPTION_LEN))
    split_type: Mapped[str] = mapped_column(String(16), server_default=text("'equal'"))
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    shares: Mapped[list["ExpenseShareModel"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class ExpenseShareModel(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index("ix_expense_shares_participant_id", "participant_id"),
    )

    expense_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    participant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("participants.id"), primary_key=True
    )
    amount: Mapped[int] = mapped_column(BigInteger)
