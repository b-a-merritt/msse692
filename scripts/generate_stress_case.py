#!/usr/bin/env python3
import argparse
import json
import random
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Literal

Kind = Literal["loud", "interrupt", "monologue"] | None
Line = tuple[str, str | None, Kind]

SUBJECT = "speaker-2"
OTHER = "speaker-1"
SEED = 692
START_AT = datetime(2026, 10, 3, tzinfo=timezone.utc)
SESSIONS_PER_PHASE = [10, 20, 30, 60, 90, 120]
UTTERANCES = 30
PHASE_SEC = 90  # Nominal session length at about 3 s per utterance
DRAIN_SEC = 30  # Quiet gap so each phase's backlog drains before the next

NEUTRAL = [
    "Can we talk about the weekend plans?",
    "I picked up groceries on the way home.",
    "The car needs an oil change soon.",
    "What time does your sister arrive?",
    "I thought we agreed on Thursday.",
    "Let me check the calendar first.",
    "That works for me, I think.",
    "We should call the landlord tomorrow.",
    "Did you see the electric bill?",
    "I can drop the kids off in the morning.",
    "Maybe we can split it this month.",
    "I need a minute to think about it.",
    "Okay, what do you want to do then?",
    "I'm not sure that's what happened.",
    "Can you explain what you meant?",
    "Let's figure out a budget together.",
    "I was at work until seven.",
    "We could ask your parents for help.",
    "Fine, let's look at the numbers.",
    "I hear what you're saying.",
    "That's fair, but it costs more.",
    "I'll handle the dishes tonight.",
    "When is the appointment again?",
    "We can revisit this next week.",
    "I just want us to be on the same page.",
    "Tell me what would help.",
    "It has been a long week for both of us.",
    "I'll text you when I leave.",
]

MONOLOGUE = [
    "So let me walk you through what happened today.",
    "First I dropped the car off at the shop.",
    "Then they told me it would take two more days.",
    "So I called work and moved my meetings around.",
    "After that I walked over to the pharmacy.",
    "They did not have the prescription ready.",
    "I waited about twenty minutes for it.",
    "Then I went to pick up the kids from school.",
    "Traffic was backed up the whole way there.",
    "We got home and nobody had started dinner.",
    "So I made something quick for everyone.",
    "And now we are finally sitting down to talk.",
]

# Scripted lines by utterance index; scripts/manifest.md lists the expected outcomes
SCENARIOS: list[dict[int, Line]] = [
    # Calm conversation
    {},
    # Character label, then an apology within the repair allowance
    {
        8: (SUBJECT, "You're being so selfish about this.", None),
        10: (SUBJECT, "I'm sorry, that was unfair of me.", None),
    },
    # Vulgar term, no repair
    {8: (SUBJECT, "This whole thing is a damn mess.", None)},
    # Absolutist phrase, then agreement within the repair allowance
    {
        8: (SUBJECT, "You never listen to a word I say.", None),
        12: (SUBJECT, "Okay, you're right about that part.", None),
    },
    # Harm phrase
    {10: (SUBJECT, "I swear to god I am done with this.", None)},
    # Loud, fast chunk
    {8: (SUBJECT, "Stop changing the subject every single time we talk about money", "loud")},
    # Two interruptions
    {
        8: (SUBJECT, "Wait, hold on, that is not true.", "interrupt"),
        14: (SUBJECT, "No, let me finish my point.", "interrupt"),
    },
    # Monologue longer than 30 s
    {10 + i: (SUBJECT, line, "monologue") for i, line in enumerate(MONOLOGUE)},
    # Triggers from the non-subject speaker only
    {
        8: (OTHER, "You never listen, you're such an idiot, damn it.", None),
        14: (OTHER, "I swear to god I hope you die.", None),
    },
    # Absolutist phrase repaired, then a label with an apology after the allowance
    {
        6: (SUBJECT, "You always do this when we have guests.", None),
        9: (SUBJECT, "I didn't mean it like that.", None),
        18: (SUBJECT, "You're being a coward about this.", None),
        26: (SUBJECT, "I'm sorry, I shouldn't have said that.", None),
    },
]


def _format_timestamp(*, value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _signal_levels(*, rng: random.Random, loud: bool) -> dict[str, float]:
    if loud:
        avg = round(rng.uniform(-13, -10), 2)
        return {
            "signal_level_min": round(avg - 30, 2),
            "signal_level_avg": avg,
            "signal_level_max": round(rng.uniform(-4, -1), 2),
        }
    avg = round(rng.uniform(-32, -22), 2)
    return {
        "signal_level_min": round(rng.uniform(-65, -45), 2),
        "signal_level_avg": avg,
        "signal_level_max": round(rng.uniform(-12, -6), 2),
    }


def _observation(
    *,
    rng: random.Random,
    case_id: str,
    index: int,
    speaker_id: str,
    transcript: str,
    start_at: datetime,
    end_at: datetime,
    loud: bool,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "observation_id": f"{case_id}-{index + 1:03d}",
        "speaker_id": speaker_id,
        "start_at": _format_timestamp(value=start_at),
        "end_at": _format_timestamp(value=end_at),
        "transcript": transcript,
        **_signal_levels(rng=rng, loud=loud),
    }


def _session(
    *,
    rng: random.Random,
    case_id: str,
    script: dict[int, Line],
    start_at: datetime,
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    cursor = start_at
    previous: tuple[str, datetime, datetime] | None = None

    for index in range(UTTERANCES):
        default_speaker = OTHER if index % 2 == 0 else SUBJECT
        speaker_id, transcript, kind = script.get(index, (default_speaker, None, None))
        if transcript is None:
            transcript = rng.choice(NEUTRAL)

        if kind == "monologue":
            begin = cursor + timedelta(seconds=0.3)
            duration = 2.5
        elif kind == "interrupt" and previous is not None:
            if previous[0] == speaker_id:
                # Give the other speaker a turn to interrupt
                other_start = cursor + timedelta(seconds=0.5)
                other_end = other_start + timedelta(seconds=2.4)
                observations.append(
                    _observation(
                        rng=rng,
                        case_id=case_id,
                        index=len(observations),
                        speaker_id=OTHER,
                        transcript=rng.choice(NEUTRAL),
                        start_at=other_start,
                        end_at=other_end,
                        loud=False,
                    )
                )
                previous = (OTHER, other_start, other_end)
                cursor = other_end
            begin = previous[2] - timedelta(seconds=0.6)
            duration = 2.0
        else:
            begin = cursor + timedelta(seconds=rng.uniform(0.4, 1.0))
            duration = rng.uniform(1.6, 2.4)

        loud = kind == "loud"
        if loud:
            duration = 2.2  # 11 words in 2.2 s is 300 words per minute
        end = begin + timedelta(seconds=duration)
        observations.append(
            _observation(
                rng=rng,
                case_id=case_id,
                index=len(observations),
                speaker_id=speaker_id,
                transcript=transcript,
                start_at=begin,
                end_at=end,
                loud=loud,
            )
        )
        previous = (speaker_id, begin, end)
        cursor = max(cursor, end)

    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic stress case")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "cases" / "stress.jsonl",
        help="JSONL file to write",
    )
    args = parser.parse_args()

    rng = random.Random(SEED)
    observations: list[dict[str, object]] = []
    phase_start = START_AT

    for phase, sessions in enumerate(SESSIONS_PER_PHASE, start=1):
        for number in range(sessions):
            offset = timedelta(seconds=rng.uniform(0, 3))
            observations.extend(
                _session(
                    rng=rng,
                    case_id=f"stress-p{phase}-{number + 1:03d}",
                    script=SCENARIOS[number % len(SCENARIOS)],
                    start_at=phase_start + offset,
                )
            )
        phase_start += timedelta(seconds=PHASE_SEC + DRAIN_SEC)

    # Replay order; send_observations.py derives delays from end_at
    observations.sort(key=lambda observation: (observation["end_at"], observation["case_id"]))
    with args.output.open("w", encoding="utf-8") as output:
        for observation in observations:
            output.write(json.dumps(observation, separators=(",", ":"), ensure_ascii=False) + "\n")

    print(f"Wrote {len(observations)} observations to {args.output}", flush=True)


if __name__ == "__main__":
    main()
