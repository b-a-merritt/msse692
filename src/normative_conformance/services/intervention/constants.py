# The first entry whose models were all detected supplies the messages, so
# Combinations come first. This is tech debt because it couples db and code.
# TODO: move these messages to the database and figure a way to COALESCE multiple matches
INTERVENTION_MESSAGES: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset({"high_intensity_address", "repeated_interruption"}),
        "You're talking over them with a raised voice. Pause and let them finish.",
    ),
    (
        frozenset({"harm_phrase"}),
        "You said something that could be heard as a threat. Take a moment before you continue.",
    ),
    (
        frozenset({"character_label"}),
        "You described the person, not the issue. Try naming what they did.",
    ),
    (
        frozenset({"high_intensity_address"}),
        "You're speaking loudly and quickly. Slow down and lower your voice.",
    ),
    (
        frozenset({"repeated_interruption"}),
        "You've interrupted several times. Let them finish before you respond.",
    ),
    (
        frozenset({"absolutist_phrase"}),
        'You said "always" or "never." Try describing this one situation.',
    ),
    (
        frozenset({"extended_turn"}),
        "You've been speaking for a while. Pause and ask for their view.",
    ),
)
