"""initial schema

Revision ID: 0001
Revises:

"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(32), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("title", sa.String(64), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("invite_token", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_rooms_owner_user_id_users"
        ),
        sa.UniqueConstraint("invite_token", name="uq_rooms_invite_token"),
    )
    op.create_table(
        "participants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_participants"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_participants_room_id_rooms"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_participants_user_id_users"),
    )
    op.create_index("ix_participants_room_id", "participants", ["room_id"])
    op.create_index(
        "uq_participants_room_id_user_id",
        "participants",
        ["room_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(16), server_default=sa.text("'expense'"), nullable=False),
        sa.Column("paid_by_participant_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(128), nullable=False),
        sa.Column("split_type", sa.String(16), server_default=sa.text("'equal'"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_expenses_room_id_rooms"),
        sa.ForeignKeyConstraint(
            ["paid_by_participant_id"],
            ["participants.id"],
            name="fk_expenses_paid_by_participant_id_participants",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_expenses_created_by_user_id_users"
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )
    op.create_index("ix_expenses_room_id_created_at", "expenses", ["room_id", "created_at"])
    op.create_table(
        "expense_shares",
        sa.Column("expense_id", sa.BigInteger(), nullable=False),
        sa.Column("participant_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("expense_id", "participant_id", name="pk_expense_shares"),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
            name="fk_expense_shares_expense_id_expenses",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="fk_expense_shares_participant_id_participants",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_expense_shares_amount_non_negative"),
    )
    op.create_index("ix_expense_shares_participant_id", "expense_shares", ["participant_id"])


def downgrade() -> None:
    op.drop_table("expense_shares")
    op.drop_table("expenses")
    op.drop_index("uq_participants_room_id_user_id", table_name="participants")
    op.drop_index("ix_participants_room_id", table_name="participants")
    op.drop_table("participants")
    op.drop_table("rooms")
    op.drop_table("users")
