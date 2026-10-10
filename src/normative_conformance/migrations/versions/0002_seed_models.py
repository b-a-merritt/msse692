import json

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: str | None = "0001"

REPEATED_INTERRUPTION_PARAMETERS = {"overlap_min_us": 150_000, "interruption_count": 2}
HIGH_INTENSITY_ADDRESS_PARAMETERS = {
    "volume_threshold_dbfs": -17,
    "rate_threshold_wpm": 180,
    "duration_min_us": 1_500_000,
}
EXTENDED_TURN_PARAMETERS = {"duration_threshold_us": 30_000_000, "turn_gap_us": 1_000_000}
HARM_PHRASE_PARAMETERS = {
    "phrases": [
        "hope you die",
        "hope you're dead",
        "wish you were dead",
        "kill you",
        "i swear to god",
    ],
}
DESCRIPTOR_TERMS = ["selfish", "selfishness", "pathetic", "insane", "melodramatic", "slob"]
# Insult terms match only when addressed to the listener, so "that's a stupid idea" does not match
INSULT_TERMS = [
    "liar",
    "idiot",
    "loser",
    "coward",
    "joke",
    "jerk",
    "moron",
    "fool",
    "imbecile",
    "prick",
    "psycho",
    "freak",
    "hypocrite",
    "narcissist",
    "bully",
    "brat",
    "pig",
    "failure",
    "disappointment",
    "embarrassment",
    "crazy",
    "nuts",
    "stupid",
    "dumb",
    "lazy",
    "useless",
    "worthless",
    "childish",
    "immature",
    "ridiculous",
    "ignorant",
    "incompetent",
    "disgusting",
    "paranoid",
    "delusional",
    "spineless",
    "heartless",
    "unbearable",
]
VULGAR_TERMS = [
    "fuck(ed|er|ers|ing)?",
    "shit(ty)?",
    "(god)?damn(ed|it)?",
    "dick(head)?",
    "bitch(es|y)?",
    "bastards?",
    "assholes?",
    "crap(py)?",
    "piss(ed)?",
]
LABEL_TERMS = "|".join(DESCRIPTOR_TERMS + INSULT_TERMS + VULGAR_TERMS)
# Only listed intensifiers may separate a bare label, so "you're not crazy" does not match
BARE_LABEL_INTENSIFIERS = (
    "being|acting|so|such|really|just|totally|completely|absolutely|fucking|too"
)
CHARACTER_LABEL_PARAMETERS = {
    "descriptor_terms": DESCRIPTOR_TERMS,
    # An address must reach a label term, so "you're a great dad" does not match
    "address_patterns": [
        r"\byou('re| are) (an?|such an?|just an?|being|acting|so)( \w+)? (" + LABEL_TERMS + r")\b",
        # Vulgar terms are excluded here, so "you're damn right" does not match
        r"\byou('re| are)( ("
        + BARE_LABEL_INTENSIFIERS
        + r"))* ("
        + "|".join(DESCRIPTOR_TERMS + INSULT_TERMS)
        + r")\b",
        r"\b(you('re| are)|you sound|you act)( just| exactly)? like your (mother|father|mom|dad)\b",
    ],
}
VULGAR_LANGUAGE_PARAMETERS = {"patterns": [r"\b(" + term + r")\b" for term in VULGAR_TERMS]}
ABSOLUTIST_PHRASE_PARAMETERS = {
    "phrases": ["you always", "you never", "you'll never", "you will never", "every time you"],
}
APOLOGY_PARAMETERS = {"phrases": ["i am sorry", "i'm sorry", "i apologize"]}
AGREEMENT_PHRASE_PARAMETERS = {"phrases": ["you're right", "you are right"]}
INTENT_DISCLAIMER_PARAMETERS = {"phrases": ["i didn't mean", "i did not mean"]}

DISTINCT_INTERRUPTIONS_SQL = """
WITH prefix AS (
    SELECT speaker_id, sequence, start_at_us, end_at_us,
        max(end_at_us) FILTER (WHERE speaker_id != :subject_speaker_id) OVER (
            ORDER BY start_at_us RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS other_end,
        max(end_at_us) FILTER (WHERE speaker_id = :subject_speaker_id) OVER (
            ORDER BY start_at_us, end_at_us, sequence
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS own_end
    FROM observation
    WHERE case_id = :case_id AND sequence <= :through_sequence
)
SELECT 1 FROM (
    SELECT count(DISTINCT sequence) AS interruptions FROM prefix
    WHERE speaker_id = :subject_speaker_id
      AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
           > (:after_start_at_us, :after_end_at_us, :after_sequence))
      AND other_end > start_at_us
      AND min(end_at_us, other_end) - start_at_us >= :overlap_min_us
      AND (own_end IS NULL OR own_end < start_at_us)
)
WHERE interruptions >= :interruption_count
"""

LOUD_FAST_SPEECH_SQL = """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND signal_level_avg > :volume_threshold_dbfs
  AND end_at_us - start_at_us >= :duration_min_us
  AND 60000000.0 * (length(normalize_text(transcript))
      - length(replace(normalize_text(transcript), ' ', '')) + 1)
      / (end_at_us - start_at_us) > :rate_threshold_wpm
LIMIT 1
"""

LONG_TURN_SQL = """
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
"""

SUBJECT_PHRASE_SQL = """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND EXISTS (
      SELECT 1 FROM json_each(:phrases)
      WHERE instr(' ' || normalize_text(transcript) || ' ', ' ' || value || ' ') > 0
  )
LIMIT 1
"""

CHARACTER_LABEL_SQL = """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND (
      EXISTS (
          SELECT 1 FROM json_each(:descriptor_terms)
          WHERE instr(' ' || normalize_text(transcript) || ' ', ' ' || value || ' ') > 0
      )
      OR EXISTS (
          SELECT 1 FROM json_each(:address_patterns)
          WHERE normalize_text(transcript) REGEXP value
      )
  )
LIMIT 1
"""

SUBJECT_PATTERN_SQL = """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND EXISTS (
      SELECT 1 FROM json_each(:patterns) WHERE normalize_text(transcript) REGEXP value
  )
LIMIT 1
"""

REPAIR_PHRASE_SQL = """
SELECT 1 FROM observation
WHERE case_id = :case_id AND speaker_id = :subject_speaker_id
  AND sequence <= :through_sequence
  AND (:observation_sequence IS NULL OR sequence = :observation_sequence)
  AND (:after_sequence IS NULL OR (start_at_us, end_at_us, sequence)
       > (:after_start_at_us, :after_end_at_us, :after_sequence))
  AND (:deadline_at_us IS NULL OR received_at_us < :deadline_at_us)
  AND EXISTS (
      SELECT 1 FROM json_each(:phrases)
      WHERE instr(' ' || normalize_text(transcript) || ' ', ' ' || value || ' ') > 0
  )
LIMIT 1
"""


def upgrade() -> None:
    models: list[dict[str, object]] = [
        {
            "model_id": "repeated_interruption",
            "name": "Repeated interruption",
            "type": "undesired",
            "repair_allowance_us": 10_000_000,
            "parameters": REPEATED_INTERRUPTION_PARAMETERS,
            "rules": [
                {
                    "rule_id": "distinct_interruptions",
                    "description": "The subject makes at least two distinct interruptions",
                    "sql": DISTINCT_INTERRUPTIONS_SQL,
                }
            ],
        },
        {
            "model_id": "high_intensity_address",
            "name": "High intensity address",
            "type": "undesired",
            "repair_allowance_us": 10_000_000,
            "parameters": HIGH_INTENSITY_ADDRESS_PARAMETERS,
            "rules": [
                {
                    "rule_id": "loud_fast_speech",
                    "description": "A subject chunk of at least duration_min_us is loud and fast",
                    "sql": LOUD_FAST_SPEECH_SQL,
                },
            ],
        },
        {
            "model_id": "extended_turn",
            "name": "Extended turn",
            "type": "undesired",
            "repair_allowance_us": 10_000_000,
            "parameters": EXTENDED_TURN_PARAMETERS,
            "rules": [
                {
                    "rule_id": "long_turn",
                    "description": "A subject turn exceeds thirty seconds",
                    "sql": LONG_TURN_SQL,
                }
            ],
        },
        {
            "model_id": "harm_phrase",
            "name": "Harm phrase",
            "type": "undesired",
            "repair_allowance_us": None,
            "parameters": HARM_PHRASE_PARAMETERS,
            "rules": [
                {
                    "rule_id": "harm_phrase",
                    "description": "A subject chunk contains a harm or threat phrase",
                    "sql": SUBJECT_PHRASE_SQL,
                }
            ],
        },
        {
            "model_id": "character_label",
            "name": "Character label",
            "type": "undesired",
            "repair_allowance_us": 10_000_000,
            "parameters": CHARACTER_LABEL_PARAMETERS,
            "rules": [
                {
                    "rule_id": "character_label",
                    "description": "A subject chunk contains a descriptor or addresses "
                    "the listener with a label",
                    "sql": CHARACTER_LABEL_SQL,
                }
            ],
        },
        {
            "model_id": "vulgar_language",
            "name": "Vulgar language",
            "type": "undesired",
            "repair_allowance_us": 10_000_000,
            "parameters": VULGAR_LANGUAGE_PARAMETERS,
            "rules": [
                {
                    "rule_id": "vulgar_term",
                    "description": "A subject chunk contains a vulgar term",
                    "sql": SUBJECT_PATTERN_SQL,
                }
            ],
        },
        {
            "model_id": "absolutist_phrase",
            "name": "Absolutist phrase",
            "type": "undesired",
            "repair_allowance_us": 20_000_000,
            "parameters": ABSOLUTIST_PHRASE_PARAMETERS,
            "rules": [
                {
                    "rule_id": "absolutist_phrase",
                    "description": "A subject chunk contains an always or never phrase",
                    "sql": SUBJECT_PHRASE_SQL,
                }
            ],
        },
        {
            "model_id": "apology",
            "name": "Apology",
            "type": "repairs",
            "repair_allowance_us": None,
            "parameters": APOLOGY_PARAMETERS,
            "rules": [
                {
                    "rule_id": "apology_phrase",
                    "description": "The subject apologizes within the supplied repair window",
                    "sql": REPAIR_PHRASE_SQL,
                }
            ],
        },
        {
            "model_id": "agreement_phrase",
            "name": "Agreement phrase",
            "type": "repairs",
            "repair_allowance_us": None,
            "parameters": AGREEMENT_PHRASE_PARAMETERS,
            "rules": [
                {
                    "rule_id": "agreement_phrase",
                    "description": "The subject agrees within the supplied repair window",
                    "sql": REPAIR_PHRASE_SQL,
                }
            ],
        },
        {
            "model_id": "intent_disclaimer",
            "name": "Intent disclaimer",
            "type": "repairs",
            "repair_allowance_us": None,
            "parameters": INTENT_DISCLAIMER_PARAMETERS,
            "rules": [
                {
                    "rule_id": "intent_disclaimer_phrase",
                    "description": "The subject disclaims intent within the supplied repair window",
                    "sql": REPAIR_PHRASE_SQL,
                }
            ],
        },
    ]
    for model in models:
        op.get_bind().execute(
            text("""
            INSERT INTO normative_model_version
                (model_id, name, version, type, repair_allowance_us, rules_json, parameters_json)
            VALUES (:model_id, :name, '1', :type, :repair_allowance_us, :rules, :parameters)
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
            'repeated_interruption', 'high_intensity_address', 'extended_turn', 'harm_phrase',
            'character_label', 'vulgar_language', 'absolutist_phrase', 'apology',
            'agreement_phrase', 'intent_disclaimer'
        )
    """)
    op.execute("""
        CREATE TRIGGER model_no_delete BEFORE DELETE ON normative_model_version
        BEGIN SELECT RAISE(ABORT, 'model version is immutable'); END
    """)
