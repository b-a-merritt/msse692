from alembic import op

revision: str = "0001"
down_revision: str | None = None

TABLES = (
    "intervention",
    "assessment_action_probability",
    "classification_topic_score",
    "classification_behavior_score",
    "classification",
    "assessment",
    "replaced_observation",
    "observation",
    "speaker_revision",
    "target_assignment",
    "case_log",
)


def upgrade() -> None:
    """Create the application tables and protect retained records."""
    op.execute("""
CREATE TABLE case_log (
    case_id TEXT PRIMARY KEY NOT NULL,
    created_at_us INTEGER NOT NULL,
    target_speaker_order INTEGER CHECK (target_speaker_order IN (1, 2)),
    last_handled_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_handled_sequence >= 0),
    last_handled_target_revision INTEGER NOT NULL DEFAULT 0
        CHECK (last_handled_target_revision >= 0)
) STRICT
""")
    # Each change of target speaker gets the next revision, so earlier work can be recognized.
    op.execute("""
CREATE TABLE target_assignment (
    case_id TEXT NOT NULL REFERENCES case_log(case_id),
    target_revision INTEGER NOT NULL CHECK (target_revision > 0),
    assigned_at_us INTEGER NOT NULL,
    speaker_id TEXT CHECK (length(trim(speaker_id)) > 0 AND speaker_id <> 'PENDING'),
    PRIMARY KEY (case_id, target_revision)
) STRICT
""")
    op.execute("""
CREATE TABLE speaker_revision (
    speaker_revision_id INTEGER PRIMARY KEY CHECK (speaker_revision_id > 0),
    case_id TEXT NOT NULL REFERENCES case_log(case_id),
    received_at_us INTEGER NOT NULL
) STRICT
""")
    # Ingested speech has a sequence; speech from a speaker revision has a revision instead.
    op.execute("""
CREATE TABLE observation (
    observation_key INTEGER PRIMARY KEY CHECK (observation_key > 0),
    case_id TEXT NOT NULL REFERENCES case_log(case_id),
    observation_id TEXT NOT NULL,
    speaker_revision_id INTEGER REFERENCES speaker_revision(speaker_revision_id),
    sequence INTEGER CHECK (sequence > 0),
    received_at_us INTEGER,
    speaker_id TEXT NOT NULL,
    start_at_us INTEGER NOT NULL,
    end_at_us INTEGER NOT NULL CHECK (end_at_us > start_at_us),
    transcript TEXT NOT NULL,
    signal_level_min REAL NOT NULL CHECK (signal_level_min BETWEEN -120 AND 0),
    signal_level_avg REAL NOT NULL CHECK (signal_level_avg BETWEEN -120 AND 0),
    signal_level_max REAL NOT NULL CHECK (signal_level_max BETWEEN -120 AND 0),
    CHECK (signal_level_min <= signal_level_avg AND signal_level_avg <= signal_level_max),
    CHECK ((speaker_revision_id IS NULL) = (sequence IS NOT NULL)),
    CHECK ((speaker_revision_id IS NULL) = (received_at_us IS NOT NULL)),
    UNIQUE (case_id, sequence),
    UNIQUE (speaker_revision_id, observation_id)
) STRICT
""")
    op.execute("""
CREATE UNIQUE INDEX observation_ingested ON observation (case_id, observation_id)
WHERE speaker_revision_id IS NULL
""")
    op.execute("""
CREATE TRIGGER observation_revision_case BEFORE INSERT ON observation
WHEN NEW.speaker_revision_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM speaker_revision
    WHERE speaker_revision_id = NEW.speaker_revision_id AND case_id = NEW.case_id
)
BEGIN SELECT RAISE(ABORT, 'revised observation must belong to its revision case'); END
""")
    op.execute("""
CREATE TABLE replaced_observation (
    speaker_revision_id INTEGER NOT NULL REFERENCES speaker_revision(speaker_revision_id),
    observation_key INTEGER NOT NULL REFERENCES observation(observation_key),
    PRIMARY KEY (speaker_revision_id, observation_key)
) STRICT
""")
    op.execute("""
CREATE TRIGGER replaced_observation_eligible BEFORE INSERT ON replaced_observation
WHEN NOT EXISTS (
    SELECT 1 FROM observation
    JOIN speaker_revision USING (case_id)
    WHERE observation.observation_key = NEW.observation_key
      AND observation.speaker_revision_id IS NULL
      AND speaker_revision.speaker_revision_id = NEW.speaker_revision_id
)
BEGIN SELECT RAISE(ABORT, 'a revision replaces ingested observations in its case'); END
""")
    op.execute("""
CREATE TABLE assessment (
    assessment_id INTEGER PRIMARY KEY CHECK (assessment_id > 0),
    case_id TEXT NOT NULL,
    target_revision INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    evaluated_at_us INTEGER NOT NULL,
    completed_at_us INTEGER NOT NULL,
    after_sequence INTEGER NOT NULL CHECK (after_sequence >= 0),
    through_sequence INTEGER NOT NULL CHECK (through_sequence > after_sequence),
    action TEXT NOT NULL
        CHECK (action IN ('remain_silent', 'await_context', 'reflect_later', 'intervene')),
    action_confidence REAL NOT NULL CHECK (action_confidence BETWEEN 0 AND 1),
    selection_threshold REAL NOT NULL CHECK (selection_threshold BETWEEN 0 AND 1),
    request_json TEXT NOT NULL CHECK (json_valid(request_json)),
    FOREIGN KEY (case_id, target_revision)
        REFERENCES target_assignment(case_id, target_revision),
    FOREIGN KEY (case_id, through_sequence) REFERENCES observation(case_id, sequence)
) STRICT
""")
    op.execute("""
CREATE TABLE assessment_action_probability (
    assessment_id INTEGER NOT NULL REFERENCES assessment(assessment_id),
    action TEXT NOT NULL
        CHECK (action IN ('remain_silent', 'await_context', 'reflect_later', 'intervene')),
    probability REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
    PRIMARY KEY (assessment_id, action)
) STRICT
""")
    # Primary topic is the model's raw choice; readers decide how to present weak topics.
    op.execute("""
CREATE TABLE classification (
    classification_id INTEGER PRIMARY KEY CHECK (classification_id > 0),
    assessment_id INTEGER NOT NULL REFERENCES assessment(assessment_id),
    observation_key INTEGER NOT NULL REFERENCES observation(observation_key),
    primary_topic TEXT NOT NULL,
    intensity REAL,
    UNIQUE (assessment_id, observation_key)
) STRICT
""")
    for table, label in (
        ("classification_topic_score", "topic"),
        ("classification_behavior_score", "behavior"),
    ):
        op.execute(f"""
CREATE TABLE {table} (
    classification_id INTEGER NOT NULL REFERENCES classification(classification_id),
    {label} TEXT NOT NULL,
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
    PRIMARY KEY (classification_id, {label})
) STRICT
""")
    op.execute("""
CREATE TABLE intervention (
    intervention_id INTEGER PRIMARY KEY CHECK (intervention_id > 0),
    assessment_id INTEGER NOT NULL UNIQUE REFERENCES assessment(assessment_id),
    message TEXT NOT NULL,
    created_at_us INTEGER NOT NULL,
    sent_at_us INTEGER CHECK (sent_at_us IS NULL OR sent_at_us >= created_at_us)
) STRICT
""")
    op.execute("CREATE INDEX speaker_revision_case ON speaker_revision (case_id)")
    op.execute("CREATE INDEX assessment_case ON assessment (case_id, assessment_id)")
    op.execute("""
CREATE INDEX intervention_pending ON intervention (intervention_id) WHERE sent_at_us IS NULL
""")
    op.execute("""
CREATE TRIGGER intervention_eligible BEFORE INSERT ON intervention
WHEN NOT EXISTS (
    SELECT 1 FROM assessment
    WHERE assessment_id = NEW.assessment_id AND action = 'intervene'
)
BEGIN SELECT RAISE(ABORT, 'intervention must come from an intervene assessment'); END
""")
    op.execute("""
CREATE TRIGGER intervention_no_delete BEFORE DELETE ON intervention
BEGIN SELECT RAISE(ABORT, 'intervention is retained'); END
""")
    # Delivery is the only change after a decision: it sets the sent time once.
    op.execute("""
CREATE TRIGGER intervention_delivery BEFORE UPDATE ON intervention
WHEN OLD.sent_at_us IS NOT NULL OR NEW.sent_at_us IS NULL
  OR NEW.intervention_id <> OLD.intervention_id OR NEW.assessment_id <> OLD.assessment_id
  OR NEW.message <> OLD.message OR NEW.created_at_us <> OLD.created_at_us
BEGIN SELECT RAISE(ABORT, 'intervention can only be marked sent once'); END
""")
    # Everything except case progress and delivery is append-only.
    for table in TABLES:
        if table in ("case_log", "intervention"):
            continue
        for operation in ("update", "delete"):
            op.execute(f"""
CREATE TRIGGER {table}_no_{operation} BEFORE {operation.upper()} ON {table}
BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END
""")


def downgrade() -> None:
    """Drop the application tables, and with them their indexes and triggers."""
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
