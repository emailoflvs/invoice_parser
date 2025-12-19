"""
Add section_label field to document_fields to store _label from JSON.

Revision ID: 007_add_section_label
Revises: 006_populate_field_definitions
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

revision = '007_add_section_label'
down_revision = '006_populate_field_definitions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add section_label column to document_fields to store _label from JSON.
    This allows displaying original section labels like "Постачальник:" from the document.
    """
    # Add section_label column
    op.add_column('document_fields',
        sa.Column('section_label', sa.Text(), nullable=True,
                  comment='Original section label from document (_label from JSON, e.g., "Постачальник:")')
    )

    # Create index for faster queries by section_label
    op.create_index('ix_document_fields_section_label', 'document_fields', ['section_label'],
                    postgresql_where=sa.text('section_label IS NOT NULL'))


def downgrade() -> None:
    """
    Remove section_label column.
    """
    op.drop_index('ix_document_fields_section_label', table_name='document_fields')
    op.drop_column('document_fields', 'section_label')










