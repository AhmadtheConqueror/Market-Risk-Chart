"""Evidence-linked cross-document intelligence synthesis."""
from alembic import op
import sqlalchemy as sa
revision="0011_intelligence_synthesis"
down_revision="0010_intelligence_pulse"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table("intelligence_synthesis_runs",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("window_start",sa.Date(),nullable=False),sa.Column("window_end",sa.Date(),nullable=False),
        sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(20),nullable=False),
        sa.Column("model_version",sa.String(120),nullable=False),sa.Column("input_hash",sa.String(64),nullable=False),
        sa.Column("metrics",sa.JSON(),nullable=False),sa.Column("error_message",sa.String(250),nullable=True))
    for column in ("window_start","window_end"):
        op.create_index("ix_intelligence_synthesis_runs_"+column,"intelligence_synthesis_runs",[column])
    op.create_table("intelligence_syntheses",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("run_id",sa.Integer(),sa.ForeignKey("intelligence_synthesis_runs.id",ondelete="CASCADE"),nullable=False),
        sa.Column("synthesis_type",sa.String(30),nullable=False),sa.Column("title",sa.String(255),nullable=False),
        sa.Column("summary",sa.Text(),nullable=False),sa.Column("commodity",sa.String(120),nullable=False),
        sa.Column("geography",sa.String(120),nullable=False),sa.Column("signal_type",sa.String(40),nullable=False),
        sa.Column("direction",sa.String(40),nullable=False),sa.Column("time_horizon",sa.String(120),nullable=False),
        sa.Column("confidence",sa.String(10),nullable=False),sa.Column("confidence_basis",sa.JSON(),nullable=False),
        sa.Column("evidence_count",sa.Integer(),nullable=False))
    op.create_index("ix_intelligence_syntheses_run_id","intelligence_syntheses",["run_id"])
    op.create_table("intelligence_synthesis_evidence",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("synthesis_id",sa.Integer(),sa.ForeignKey("intelligence_syntheses.id",ondelete="CASCADE"),nullable=False),
        sa.Column("finding_id",sa.Integer(),sa.ForeignKey("intelligence_findings.id",ondelete="CASCADE"),nullable=False),
        sa.Column("evidence_hash",sa.String(64),nullable=False),sa.UniqueConstraint("synthesis_id","finding_id",name="uq_synthesis_evidence"))
    for column in ("synthesis_id","finding_id"):
        op.create_index("ix_intelligence_synthesis_evidence_"+column,"intelligence_synthesis_evidence",[column])


def downgrade():
    op.drop_table("intelligence_synthesis_evidence")
    op.drop_table("intelligence_syntheses")
    op.drop_table("intelligence_synthesis_runs")
