import json

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: str | None = "0001"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE normative_model_version ADD COLUMN type TEXT NOT NULL
        DEFAULT 'undesired' CHECK (type IN ('undesired', 'repairs'))
    """)
    op.execute("""
        ALTER TABLE normative_model_version ADD COLUMN repairable INTEGER NOT NULL
        DEFAULT 1 CHECK (repairable IN (0, 1) AND (type = 'undesired' OR repairable = 0))
    """)
    models = [
        {
            "model_id": "repeated_interruption",
            "name": "Repeated interruption",
            "type": "undesired",
            "repairable": True,
            "parameters": {"overlap_min_us": 150_000, "interruption_count": 2},
            "rules": [
                {
                    "rule_id": "distinct_interruptions",
                    "description": "The subject makes at least two distinct interruptions",
                    "sql": """
SELECT 1
FROM observation s
JOIN observation o ON o.case_id = s.case_id AND o.speaker_id != s.speaker_id
WHERE s.case_id = :case_id AND s.speaker_id = :subject_speaker_id
  AND s.sequence <= :through_sequence AND o.sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (s.start_at_us, s.end_at_us, s.sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND o.start_at_us < s.start_at_us AND s.start_at_us < o.end_at_us
  AND min(s.end_at_us, o.end_at_us) - s.start_at_us >= :overlap_min_us
  AND NOT EXISTS (
      SELECT 1 FROM observation p
      WHERE p.case_id = s.case_id AND p.speaker_id = s.speaker_id
        AND p.sequence <= :through_sequence
        AND (p.start_at_us, p.end_at_us, p.sequence) < (s.start_at_us, s.end_at_us, s.sequence)
        AND p.end_at_us >= s.start_at_us
  )
GROUP BY s.case_id HAVING count(DISTINCT s.sequence) >= :interruption_count
LIMIT 1
""",
                }
            ],
        },
        {
            "model_id": "high_intensity_address",
            "name": "High intensity address",
            "type": "undesired",
            "repairable": True,
            "parameters": {
                "volume_threshold_dbfs": -18,
                "rate_threshold_wpm": 180,
                "address_phrases": ["you're a", "you are a"],
                "vulgar_terms": [
                    "fuck",
                    "fucked",
                    "fucker",
                    "fucking",
                    "shit",
                    "damn",
                    "goddamn",
                    "dick",
                    "bitch",
                    "bastard",
                    "asshole",
                    "crap",
                    "piss",
                    "pissed",
                ],
            },
            "rules": [
                {
                    "rule_id": "loud_fast_speech",
                    "description": "A subject chunk is loud and fast",
                    "sql": """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND signal_level_avg > :volume_threshold_dbfs
  AND 60000000.0 * (length(normalize_text(transcript))
      - length(replace(normalize_text(transcript), ' ', '')) + 1)
      / (end_at_us - start_at_us) > :rate_threshold_wpm
LIMIT 1
""",
                },
                {
                    "rule_id": "insulting_address",
                    "description": "A subject chunk contains vulgarity or an address phrase",
                    "sql": """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND EXISTS (
      SELECT 1 FROM json_each(:address_phrases)
      WHERE instr(' ' || normalize_text(transcript) || ' ', ' ' || value || ' ') > 0
      UNION ALL
      SELECT 1 FROM json_each(:vulgar_terms)
      WHERE instr(' ' || normalize_text(transcript) || ' ', ' ' || value || ' ') > 0
  )
LIMIT 1
""",
                },
            ],
        },
        {
            "model_id": "extended_turn",
            "name": "Extended turn",
            "type": "undesired",
            "repairable": True,
            "parameters": {"duration_threshold_us": 30_000_000, "turn_gap_us": 1_000_000},
            "rules": [
                {
                    "rule_id": "long_turn",
                    "description": "A subject turn exceeds thirty seconds",
                    "sql": """
WITH chunks AS (
    SELECT *, max(end_at_us) OVER (
        ORDER BY start_at_us, end_at_us, sequence
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS previous_end
    FROM observation
    WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
      AND sequence <= :through_sequence
      AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
           > (:after_start_at_us, :after_end_at_us, :after_sequence))
), breaks AS (
    SELECT *, CASE WHEN previous_end IS NULL OR start_at_us - previous_end > :turn_gap_us
        OR EXISTS (
            SELECT 1 FROM observation o WHERE o.case_id = :case_id
            AND o.speaker_id != :subject_speaker_id AND o.sequence <= :through_sequence
            AND o.start_at_us BETWEEN chunks.previous_end AND chunks.start_at_us
        ) THEN 1 ELSE 0 END AS new_turn
    FROM chunks
), turns AS (
    SELECT *, sum(new_turn) OVER (ORDER BY start_at_us, end_at_us, sequence) AS turn_id
    FROM breaks
)
SELECT 1 FROM turns GROUP BY turn_id
HAVING max(end_at_us) - min(start_at_us) > :duration_threshold_us
LIMIT 1
""",
                }
            ],
        },
        {
            "model_id": "apology",
            "name": "Apology",
            "type": "repairs",
            "repairable": False,
            "parameters": {},
            "rules": [
                {
                    "rule_id": "apology_phrase",
                    "description": "The subject apologizes within the supplied repair window",
                    "sql": """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:observation_sequence IS NULL OR sequence = :observation_sequence)
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND (:deadline_at_us IS NULL OR received_at_us < :deadline_at_us)
  AND (instr(' ' || normalize_text(transcript) || ' ', ' i am sorry ') > 0
       OR instr(' ' || normalize_text(transcript) || ' ', ' i apologize ') > 0)
LIMIT 1
""",
                }
            ],
        },
    ]
    for model in models:
        op.get_bind().execute(
            text("""
            INSERT INTO normative_model_version
                (model_id, name, version, type, repairable, rules_json, parameters_json)
            VALUES (:model_id, :name, '1', :type, :repairable, :rules, :parameters)
        """),
            {
                **model,
                "rules": json.dumps(model["rules"]),
                "parameters": json.dumps(model["parameters"]),
            },
        )


def downgrade() -> None:
    # Foreign keys still prevent removing models referenced by assessments.
    op.execute("DROP TRIGGER model_no_delete")
    op.execute("""
        DELETE FROM normative_model_version WHERE version = '1'
        AND model_id IN (
            'repeated_interruption', 'high_intensity_address', 'extended_turn', 'apology'
        )
    """)
    op.execute("""
        CREATE TRIGGER model_no_delete BEFORE DELETE ON normative_model_version
        BEGIN SELECT RAISE(ABORT, 'model version is immutable'); END
    """)
    op.execute("ALTER TABLE normative_model_version DROP COLUMN repairable")
    op.execute("ALTER TABLE normative_model_version DROP COLUMN type")
