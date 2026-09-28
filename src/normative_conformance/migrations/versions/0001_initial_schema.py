from alembic import op

revision: str = "0001"
down_revision: str | None = None

TABLES = (
    "intervention_source",
    "intervention",
    "assessment",
    "normative_model_version",
    "observation",
    "case_log",
    "experiment_config",
)


def upgrade() -> None:
    """Create the seven application tables and protect retained records."""
    op.execute("""
CREATE TABLE experiment_config (
    experiment_id INTEGER PRIMARY KEY CHECK (experiment_id = 1),
    subject_speaker_id TEXT NOT NULL,
    created_at_us INTEGER NOT NULL
) STRICT
""")
    op.execute("""
CREATE TABLE case_log (
    case_id TEXT PRIMARY KEY NOT NULL,
    created_at_us INTEGER NOT NULL
) STRICT
""")
    op.execute("""
CREATE TABLE observation (
    case_id TEXT NOT NULL REFERENCES case_log(case_id),
    observation_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    received_at_us INTEGER NOT NULL,
    speaker_id TEXT NOT NULL,
    start_at_us INTEGER NOT NULL,
    end_at_us INTEGER NOT NULL CHECK (end_at_us > start_at_us),
    transcript TEXT NOT NULL,
    signal_level_min REAL NOT NULL CHECK (signal_level_min BETWEEN -120 AND 0),
    signal_level_avg REAL NOT NULL CHECK (signal_level_avg BETWEEN -120 AND 0),
    signal_level_max REAL NOT NULL CHECK (signal_level_max BETWEEN -120 AND 0),
    CHECK (signal_level_min <= signal_level_avg AND signal_level_avg <= signal_level_max),
    PRIMARY KEY (case_id, observation_id),
    UNIQUE (case_id, sequence)
) STRICT
""")
    op.execute("""
CREATE TABLE normative_model_version (
    model_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'undesired' CHECK (type IN ('undesired', 'repairs')),
    repair_allowance_us INTEGER
        CHECK (repair_allowance_us IS NULL OR (type = 'undesired' AND repair_allowance_us > 0)),
    rules_json TEXT NOT NULL CHECK (json_valid(rules_json)),
    parameters_json TEXT NOT NULL CHECK (json_valid(parameters_json)),
    PRIMARY KEY (model_id, version)
) STRICT
""")
    op.execute("""
CREATE TABLE assessment (
    assessment_id INTEGER PRIMARY KEY CHECK (assessment_id > 0),
    evaluation_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    evaluated_at_us INTEGER NOT NULL,
    through_sequence INTEGER NOT NULL CHECK (through_sequence > 0),
    status TEXT NOT NULL
        CHECK (status IN ('conformant', 'non-conformant', 'pending', 'conflicted')),
    explanation_json TEXT NOT NULL CHECK (json_valid(explanation_json)),
    next_due_at_us INTEGER,
    resolves_assessment_id INTEGER UNIQUE REFERENCES assessment(assessment_id),
    CHECK (resolves_assessment_id IS NULL OR status IN ('conformant', 'non-conformant')),
    UNIQUE (evaluation_id, model_id, model_version),
    FOREIGN KEY (model_id, model_version) REFERENCES normative_model_version(model_id, version),
    FOREIGN KEY (case_id, through_sequence) REFERENCES observation(case_id, sequence)
) STRICT
""")
    op.execute("""
CREATE TABLE intervention (
    intervention_id INTEGER PRIMARY KEY CHECK (intervention_id > 0),
    case_id TEXT NOT NULL REFERENCES case_log(case_id),
    message TEXT NOT NULL,
    created_at_us INTEGER NOT NULL,
    sent_at_us INTEGER CHECK (sent_at_us IS NULL OR sent_at_us >= created_at_us)
) STRICT
""")
    op.execute("""
CREATE TABLE intervention_source (
    intervention_id INTEGER NOT NULL REFERENCES intervention(intervention_id),
    assessment_id INTEGER NOT NULL UNIQUE REFERENCES assessment(assessment_id),
    PRIMARY KEY (intervention_id, assessment_id)
) STRICT
""")
    # Stored evidence cannot be updated or deleted. Ingestion must assign
    # increasing per-case sequence numbers to keep assessed prefixes stable.
    op.execute("""
CREATE TRIGGER observation_no_update BEFORE UPDATE ON observation
BEGIN SELECT RAISE(ABORT, 'observation is append-only'); END
""")
    op.execute("""
CREATE TRIGGER observation_no_delete BEFORE DELETE ON observation
BEGIN SELECT RAISE(ABORT, 'observation is append-only'); END
""")
    op.execute("""
CREATE TRIGGER model_no_update BEFORE UPDATE ON normative_model_version
BEGIN SELECT RAISE(ABORT, 'model version is immutable'); END
""")
    op.execute("""
CREATE TRIGGER model_no_delete BEFORE DELETE ON normative_model_version
BEGIN SELECT RAISE(ABORT, 'model version is immutable'); END
""")
    op.execute("""
CREATE TRIGGER assessment_no_update BEFORE UPDATE ON assessment
BEGIN SELECT RAISE(ABORT, 'assessment is immutable'); END
""")
    op.execute("""
CREATE TRIGGER assessment_no_delete BEFORE DELETE ON assessment
BEGIN SELECT RAISE(ABORT, 'assessment is immutable'); END
""")
    op.execute("""
CREATE TRIGGER assessment_resolution BEFORE INSERT ON assessment
WHEN NEW.resolves_assessment_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM assessment original
    WHERE original.assessment_id = NEW.resolves_assessment_id AND original.status = 'pending'
      AND original.case_id = NEW.case_id AND original.model_id = NEW.model_id
      AND original.model_version = NEW.model_version
      AND NEW.evaluated_at_us >= original.evaluated_at_us
      AND NEW.through_sequence >= original.through_sequence
)
BEGIN SELECT RAISE(ABORT, 'resolution must reference a matching pending assessment'); END
""")
    op.execute("""
CREATE TRIGGER intervention_no_delete BEFORE DELETE ON intervention
BEGIN SELECT RAISE(ABORT, 'intervention is retained'); END
""")
    # Delivery is the only change after a decision: it sets the sent time once.
    op.execute("""
CREATE TRIGGER intervention_delivery BEFORE UPDATE ON intervention
WHEN OLD.sent_at_us IS NOT NULL OR NEW.sent_at_us IS NULL
  OR NEW.intervention_id <> OLD.intervention_id OR NEW.case_id <> OLD.case_id
  OR NEW.message <> OLD.message OR NEW.created_at_us <> OLD.created_at_us
BEGIN SELECT RAISE(ABORT, 'intervention can only be marked sent once'); END
""")
    op.execute("""
CREATE TRIGGER intervention_source_eligible BEFORE INSERT ON intervention_source
WHEN NOT EXISTS (
    SELECT 1 FROM assessment
    JOIN normative_model_version model
      ON model.model_id = assessment.model_id AND model.version = assessment.model_version
    JOIN intervention ON intervention.intervention_id = NEW.intervention_id
    WHERE assessment.assessment_id = NEW.assessment_id
      AND assessment.status = 'conformant' AND model.type = 'undesired'
      AND assessment.case_id = intervention.case_id
)
BEGIN SELECT RAISE(ABORT, 'intervention source must be an eligible assessment in its case'); END
""")
    op.execute("""
CREATE TRIGGER intervention_source_no_update BEFORE UPDATE ON intervention_source
BEGIN SELECT RAISE(ABORT, 'intervention source is immutable'); END
""")
    op.execute("""
CREATE TRIGGER intervention_source_no_delete BEFORE DELETE ON intervention_source
BEGIN SELECT RAISE(ABORT, 'intervention source is immutable'); END
""")
    op.execute("""
CREATE TRIGGER experiment_no_update BEFORE UPDATE ON experiment_config
BEGIN SELECT RAISE(ABORT, 'experiment configuration is immutable'); END
""")
    op.execute("""
CREATE TRIGGER experiment_no_delete BEFORE DELETE ON experiment_config
BEGIN SELECT RAISE(ABORT, 'experiment configuration is immutable'); END
""")


def downgrade() -> None:
    """Drop the application tables, and with them their indexes and triggers."""
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
