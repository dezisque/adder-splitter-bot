"""user current room

Revision ID: 0003
Revises: 0002

"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("current_room_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_users_current_room_id_rooms",
        "users",
        "rooms",
        ["current_room_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_current_room_id_rooms", "users", type_="foreignkey")
    op.drop_column("users", "current_room_id")
