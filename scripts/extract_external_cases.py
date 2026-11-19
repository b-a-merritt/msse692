#!/usr/bin/env python3
"""Extract external evaluation cases from PersonaConflicts and ConvoKit CGA-CMV."""

import argparse
import ast
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from conversation_monitor.schemas.observation import ObservationInput

DEFAULT_PC_DIR = Path("/tmp/persona-conflicts-corpus-emnlp-2025")
DEFAULT_CGA_DIR = Path("/tmp/cga-cmv/conversations-gone-awry-cmv-corpus")
DEFAULT_CASES_DIR = Path(__file__).resolve().parent / "cases"
DEFAULT_EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "eval"
DEFAULT_PC_SCORE = DEFAULT_EVAL_DIR / "persona-conflicts-2026-11-19" / "score.out"
DEFAULT_CGA_SCORE = DEFAULT_EVAL_DIR / "convokit-cmv-2026-11-19" / "score.out"

BASE_TIME = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)
TURN_DURATION = timedelta(milliseconds=150)
TURN_GAP = timedelta(milliseconds=50)
SIGNAL_MIN = -50.0
SIGNAL_AVG = -25.0
SIGNAL_MAX = -10.0

CANONICAL_VC_TAGS = frozenset(
    {
        "Comparison",
        "Demand",
        "Denial of Responsibility",
        "Deserve Thinking",
        "Moralistic Judgment",
    }
)


@dataclass(frozen=True)
class _PersonaConflictCase:
    case_id: str
    pair_number: int
    batch: str
    source_id: int
    neg_row: int
    pos_row: int
    dataset_final_row: int | None
    convo_type: str
    relationship_type: str
    category: str
    chosen_character: str
    other_character: str
    chosen_ss: float
    other_ss: float
    tp_max_chosen: float
    vc_tags: tuple[str, ...]
    other_vc_notes: tuple[str, ...]
    turns: tuple[tuple[str, str], ...]
    peak_quote: str


@dataclass(frozen=True)
class _ConvokitCase:
    case_id: str
    pair_number: int
    conversation_id: str
    pair_id: str
    has_removed_comment: bool
    speaker_2_name: str
    speaker_1_name: str
    turns: tuple[tuple[str, str], ...]
    final_turn_quote: str


@dataclass(frozen=True)
class _ScoreRow:
    case_id: str
    interventions: str
    first_turn: str
    predicted: str
    result: str
    behaviors: str


def _load_score_rows(score_path: Path) -> list[_ScoreRow]:
    if not score_path.is_file():
        return []
    rows: list[_ScoreRow] = []
    for raw_line in score_path.read_text(encoding="utf-8").splitlines()[1:]:
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 6:
            continue
        predicted_clean = parts[3].capitalize()
        behaviors_clean = "—" if parts[5] == "-" else parts[5]
        rows.append(
            _ScoreRow(
                case_id=parts[0],
                interventions=parts[1],
                first_turn=parts[2],
                predicted=predicted_clean,
                result=parts[4],
                behaviors=behaviors_clean,
            )
        )
    return rows


def _format_results_table(rows: list[_ScoreRow]) -> list[str]:
    lines = [
        "| Case | Interventions | First turn | Predicted | Result | Behaviors |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.case_id}` | {row.interventions} | {row.first_turn}"
            f" | {row.predicted} | {row.result} | {row.behaviors} |"
        )
    return lines


def _format_timestamp(value: datetime) -> str:
    utc = value.astimezone(UTC)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0") + "Z"
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_quote(text: str, limit: int = 85) -> str:
    single_line = " ".join(text.replace("|", "/").split())
    if len(single_line) <= limit:
        return single_line
    return single_line[: limit - 1].rstrip() + "…"


def _resolve_pc_turn(
    turn_dict: dict[str, object],
    agent_1_name: str,
    agent_2_name: str,
    chosen_character: str,
) -> tuple[str, str]:
    raw_speaker = str(turn_dict["speaker"])
    raw_text = str(turn_dict["text"]).strip()
    cleaned = raw_speaker.strip("() ")
    if cleaned in (agent_1_name, agent_2_name):
        return cleaned, raw_text
    if ":" in raw_speaker:
        prefix, remainder = raw_speaker.split(":", 1)
        prefix_clean = prefix.strip("() ")
        if prefix_clean in (agent_1_name, agent_2_name):
            return prefix_clean, f"{remainder.strip()}: {raw_text}"
    # Stage-direction turn without a speaker prefix (e.g., id=5 turn 3 noisy action by Jasmine).
    return chosen_character, f"{raw_speaker}: {raw_text}"


def _build_pc_case(
    case_id: str,
    pair_number: int,
    batch: str,
    record: tuple[int, int, int | None, dict[str, str], dict[str, str]],
) -> _PersonaConflictCase:
    neg_row, pos_row, df_row, neg_r, pos_r = record
    chosen = neg_r["chosen_character"]
    a1 = neg_r["agent_1_name"]
    a2 = neg_r["agent_2_name"]
    is_a1 = chosen == a1
    other = a2 if is_a1 else a1

    ss_chosen_col = (
        "q_shouldnt_say_agent_1_name_avg" if is_a1 else "q_shouldnt_say_agent_2_name_avg"
    )
    ss_other_col = "q_shouldnt_say_agent_2_name_avg" if is_a1 else "q_shouldnt_say_agent_1_name_avg"
    chosen_ss = (float(neg_r[ss_chosen_col]) + float(pos_r[ss_chosen_col])) / 2.0
    other_ss = (float(neg_r[ss_other_col]) + float(pos_r[ss_other_col])) / 2.0

    raw_turns = json.loads(neg_r["transformed_conversation"])
    neg_tp = ast.literal_eval(neg_r["turn_problematic_avg"])
    pos_tp = ast.literal_eval(pos_r["turn_problematic_avg"])
    neg_vc = ast.literal_eval(neg_r["turn_vc_union"])
    pos_vc = ast.literal_eval(pos_r["turn_vc_union"])

    turns: list[tuple[str, str]] = []
    chosen_turn_scores: list[tuple[float, str]] = []
    canonical_tags: set[str] = set()
    other_notes: set[str] = set()

    for idx, turn_dict in enumerate(raw_turns):
        character, text = _resolve_pc_turn(turn_dict, a1, a2, chosen)
        speaker_id = "speaker-2" if character == chosen else "speaker-1"
        turns.append((speaker_id, text))
        if character == chosen:
            pooled_tp = (float(neg_tp[idx]) + float(pos_tp[idx])) / 2.0
            chosen_turn_scores.append((pooled_tp, text))
            for tag in neg_vc[idx] + pos_vc[idx]:
                if not tag or tag == "None of the above":
                    continue
                if tag in CANONICAL_VC_TAGS:
                    canonical_tags.add(tag)
                else:
                    other_notes.add(tag)

    tp_max_chosen, peak_text = max(chosen_turn_scores, key=lambda item: item[0])
    return _PersonaConflictCase(
        case_id=case_id,
        pair_number=pair_number,
        batch=batch,
        source_id=int(neg_r["id"]),
        neg_row=neg_row,
        pos_row=pos_row,
        dataset_final_row=df_row,
        convo_type=neg_r["convo_type"],
        relationship_type=neg_r["relationship_type"],
        category=neg_r["High Level Category"],
        chosen_character=chosen,
        other_character=other,
        chosen_ss=chosen_ss,
        other_ss=other_ss,
        tp_max_chosen=tp_max_chosen,
        vc_tags=tuple(sorted(canonical_tags)),
        other_vc_notes=tuple(sorted(other_notes)),
        turns=tuple(turns),
        peak_quote=_clean_quote(peak_text),
    )


def _load_persona_conflicts(pc_dir: Path) -> list[_PersonaConflictCase]:
    with (pc_dir / "mturk_aggregate.csv").open(encoding="utf-8") as handle:
        mturk_rows = list(csv.DictReader(handle))
    with (pc_dir / "dataset_final.csv").open(encoding="utf-8") as handle:
        df_rows = list(csv.DictReader(handle))

    df_by_conv = {row["transformed_conversation"]: idx for idx, row in enumerate(df_rows)}
    by_conv: dict[str, dict[str, tuple[int, dict[str, str]]]] = defaultdict(dict)
    for idx, row in enumerate(mturk_rows):
        by_conv[row["transformed_conversation"]][row["condition"]] = (idx, row)

    main_convs: dict[int, tuple[int, int, int | None, dict[str, str], dict[str, str]]] = {}
    pilot_convs: dict[int, tuple[int, int, int | None, dict[str, str], dict[str, str]]] = {}
    for conv, conds in by_conv.items():
        neg_idx, neg_r = conds["negative"]
        pos_idx, pos_r = conds["positive"]
        source_id = int(neg_r["id"])
        if conv in df_by_conv:
            main_convs[source_id] = (neg_idx, pos_idx, df_by_conv[conv], neg_r, pos_r)
        else:
            pilot_convs[source_id] = (neg_idx, pos_idx, None, neg_r, pos_r)

    cases: list[_PersonaConflictCase] = []
    for pair_num in range(1, 51):
        offset = pair_num - 1
        cases.append(
            _build_pc_case(f"pc-{pair_num:02d}-conflict", pair_num, "main", main_convs[offset])
        )
        cases.append(
            _build_pc_case(
                f"pc-{pair_num:02d}-nonconflict", pair_num, "main", main_convs[offset + 125]
            )
        )
    for pair_num in range(51, 61):
        offset = pair_num - 51
        cases.append(
            _build_pc_case(f"pc-{pair_num:02d}-conflict", pair_num, "pilot", pilot_convs[offset])
        )
        cases.append(
            _build_pc_case(
                f"pc-{pair_num:02d}-nonconflict", pair_num, "pilot", pilot_convs[offset + 10]
            )
        )
    return cases


def _is_clean_two_speaker_ge4(utterances: list[dict[str, object]]) -> bool:
    if len(utterances) < 4:
        return False
    speakers = {str(u["speaker"]) for u in utterances}
    if len(speakers) != 2 or "[deleted]" in speakers or "[removed]" in speakers:
        return False
    for utterance in utterances:
        text = str(utterance["text"]).strip()
        if not text or text in ("[deleted]", "[removed]"):
            return False
    return True


def _load_convokit_cmv(cga_dir: Path) -> list[_ConvokitCase]:
    with (cga_dir / "conversations.json").open(encoding="utf-8") as handle:
        convs = json.load(handle)

    test_cids = {cid for cid, meta in convs.items() if meta["meta"]["split"] == "test"}
    utts_by_conv: dict[str, list[dict[str, object]]] = defaultdict(list)
    with (cga_dir / "utterances.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            utterance = json.loads(line)
            cid = str(utterance["conversation_id"])
            if cid in test_cids:
                utts_by_conv[cid].append(utterance)

    pairs: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for cid in test_cids:
        meta = convs[cid]["meta"]
        pair_key = tuple(sorted((cid, str(meta["pair_id"]))))
        role = "awry" if meta["has_removed_comment"] else "civil"
        pairs[pair_key][role] = cid

    clean_pairs: list[tuple[str, str]] = []
    for _, paired in sorted(pairs.items()):
        if "awry" in paired and "civil" in paired:
            awry_cid = paired["awry"]
            civil_cid = paired["civil"]
            if _is_clean_two_speaker_ge4(utts_by_conv[awry_cid]) and _is_clean_two_speaker_ge4(
                utts_by_conv[civil_cid]
            ):
                clean_pairs.append((awry_cid, civil_cid))

    cases: list[_ConvokitCase] = []
    for pair_number, (awry_cid, civil_cid) in enumerate(clean_pairs, start=1):
        for suffix, cid, partner_cid, has_removed in (
            ("awry", awry_cid, civil_cid, True),
            ("civil", civil_cid, awry_cid, False),
        ):
            utts = utts_by_conv[cid]
            target_speaker = str(utts[-1]["speaker"])
            other_speakers = {str(u["speaker"]) for u in utts} - {target_speaker}
            other_speaker = next(iter(other_speakers))
            turns = tuple(
                (
                    "speaker-2" if str(u["speaker"]) == target_speaker else "speaker-1",
                    str(u["text"]).strip(),
                )
                for u in utts
            )
            cases.append(
                _ConvokitCase(
                    case_id=f"cga-cmv-{pair_number:02d}-{suffix}",
                    pair_number=pair_number,
                    conversation_id=cid,
                    pair_id=partner_cid,
                    has_removed_comment=has_removed,
                    speaker_2_name=target_speaker,
                    speaker_1_name=other_speaker,
                    turns=turns,
                    final_turn_quote=_clean_quote(str(utts[-1]["text"])),
                )
            )
    return cases


def _turns_to_jsonl_lines(case_id: str, turns: tuple[tuple[str, str], ...]) -> list[str]:
    lines: list[str] = []
    step = TURN_DURATION + TURN_GAP
    for index, (speaker_id, transcript) in enumerate(turns, start=1):
        start_at = BASE_TIME + (index - 1) * step
        end_at = start_at + TURN_DURATION
        payload = {
            "case_id": case_id,
            "observation_id": f"{case_id}-{index:03d}",
            "speaker_id": speaker_id,
            "start_at": _format_timestamp(start_at),
            "end_at": _format_timestamp(end_at),
            "transcript": transcript,
            "signal_level_min": SIGNAL_MIN,
            "signal_level_avg": SIGNAL_AVG,
            "signal_level_max": SIGNAL_MAX,
        }
        ObservationInput.model_validate(payload)
        lines.append(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return lines


def _write_persona_conflicts_outputs(
    cases: list[_PersonaConflictCase],
    cases_dir: Path,
    score_path: Path = DEFAULT_PC_SCORE,
) -> None:
    for filename, suffix in (
        ("persona_conflicts_conflict.jsonl", "conflict"),
        ("persona_conflicts_nonconflict.jsonl", "nonconflict"),
    ):
        jsonl_lines = [
            line
            for case in cases
            if case.convo_type == suffix
            for line in _turns_to_jsonl_lines(case.case_id, case.turns)
        ]
        (cases_dir / filename).write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")
    combined_path = cases_dir / "persona_conflicts.jsonl"
    if combined_path.exists():
        combined_path.unlink()

    expected = {
        case.case_id: {"intervene": "yes" if case.convo_type == "conflict" else "no"}
        for case in cases
    }
    (cases_dir / "persona_conflicts_expected.json").write_text(
        json.dumps(expected, indent=2) + "\n", encoding="utf-8"
    )

    discrepancies = [
        case
        for case in cases
        if (case.convo_type == "conflict" and case.chosen_ss < 2.50)
        or (case.convo_type == "nonconflict" and case.chosen_ss >= 2.50)
    ]

    md_lines = [
        "# PersonaConflicts Predictions",
        "",
        "Expected outcomes for the 120 human-rated dialogues (60 conflict and non-conflict"
        " pairs) from Shen et al. (2025), *Words Like Knives: Backstory-Personalized"
        " Modeling and Detection of Violent Communication* (EMNLP 2025,"
        " https://github.com/mitmedialab/persona-conflicts-corpus-emnlp-2025).",
        "",
        "## Source data",
        "",
        "`mturk_aggregate.csv` has 240 rows: 120 conversations rated twice each by Amazon"
        " Mechanical Turk workers, once with a positive backstory for the main character and"
        " once with a negative backstory (two raters per condition, four total). All 120"
        " conversations are included here:",
        "",
        "- `pc-01` to `pc-50` (`main`): 50 conflict cases (`id` 0-49) paired with 50"
        " non-conflict cases (`id` 125-174) from `dataset_final.csv`.",
        "- `pc-51` to `pc-60` (`pilot`): the other 20 rated conversations in"
        " `mturk_aggregate.csv` (`id` 0-9 for conflict, `id` 10-19 for non-conflict).",
        "",
        "The character whose backstory was varied (`chosen_character`) is `speaker-2` (the"
        " target), and the other speaker is `speaker-1`. Turn times are spaced 0.2 s apart"
        " with neutral signal levels (-50 / -25 / -10 dBFS) so an entire 15-turn conversation"
        " fits inside the 30 s context window.",
        "",
        "## Labels and ratings",
        "",
        "`persona_conflicts_expected.json` uses the scenario label (`convo_type`):"
        " **Yes** for `conflict` and **No** for `nonconflict`.",
        "",
        "The table also lists the four-rater averages from `mturk_aggregate.csv`"
        " (`neg_row` and `pos_row` averaged together):",
        "",
        "- `chosen_ss` and `other_ss`: average answer (1-4) to whether `speaker-2` or"
        " `speaker-1` said anything they should not have said.",
        "- `tp_max`: highest turn-level problematic rating (1-4) among `speaker-2`'s turns.",
        "- `Target VC tags`: Nonviolent Communication violations marked by raters on"
        " `speaker-2`'s turns (`Comparison`, `Demand`, `Denial of Responsibility`,"
        " `Deserve Thinking`, `Moralistic Judgment`).",
        "",
        "## Where the raters and scenario label disagree",
        "",
        "In 110 of the 120 cases, the `convo_type` label matches whether `chosen_ss` is at"
        " least 2.50 (the midpoint of the 1-4 scale). The 10 cases where they differ are"
        " listed below:",
        "",
        "| Case | `convo_type` | `speaker-2` (`chosen`) | `chosen_ss` | `other_ss` |"
        " `tp_max_chosen` | Why they differ |",
        "|---|---|---|---:|---:|---:|---|",
    ]

    for case in discrepancies:
        if case.convo_type == "conflict":
            cause = (
                f"`speaker-1` ({case.other_character}, {case.other_ss:.2f}) escalated"
                f" more than `speaker-2` ({case.chosen_character})"
            )
        else:
            cause = (
                f"Raters scored `{case.chosen_character}` at {case.chosen_ss:.2f}"
                " in a non-conflict scenario"
            )
        md_lines.append(
            f"| `{case.case_id}` | `{case.convo_type}` | {case.chosen_character}"
            f" | {case.chosen_ss:.2f} | {case.other_ss:.2f} | {case.tp_max_chosen:.2f}"
            f" | {cause} |"
        )

    md_lines.extend(
        [
            "",
            "## Predictions",
            "",
            "| Case | Batch | `id` | `neg_row` | `pos_row` | `df_row` | `speaker-2` |"
            " `speaker-1` | `chosen_ss` | `other_ss` | `tp_max` | Target VC tags"
            " (`turn_vc_union`) | Peak target turn quote | Intervene |",
            "|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|",
        ]
    )

    for case in cases:
        df_cell = str(case.dataset_final_row) if case.dataset_final_row is not None else "pilot"
        vc_cell = ", ".join(case.vc_tags) if case.vc_tags else "—"
        intervene_cell = "Yes" if case.convo_type == "conflict" else "No"
        md_lines.append(
            f"| `{case.case_id}` | {case.batch} | {case.source_id} | {case.neg_row}"
            f" | {case.pos_row} | {df_cell} | {case.chosen_character}"
            f" | {case.other_character} | {case.chosen_ss:.2f} | {case.other_ss:.2f}"
            f' | {case.tp_max_chosen:.2f} | {vc_cell} | "{case.peak_quote}"'
            f" | {intervene_cell} |"
        )

    score_rows = _load_score_rows(score_path)
    if score_rows:
        md_lines.extend(
            [
                "",
                "## Results",
                "",
                "Three replays of each case with `jev-1.14.0`, prompt `conversation-3`,"
                " and no discovered model (`data/eval/persona-conflicts-2026-11-19`),"
                " scored by `scripts/evaluate.py`. The number after each behavior is"
                " how many of the three replays had a target turn at the 0.7 threshold."
                " Interventions and first turn list the count and first intervention"
                " turn from each replay.",
                "",
                "- Run 1 matched 117 of 120 (97.5%), Run 2 matched 116 of 120 (96.7%),"
                " and Run 3 matched 118 of 120 (98.3%) (351 of 360 runs total, 97.5%).",
                "- Whether a case had an intervention was unchanged across all three"
                " runs in 116 of 120 cases (96.7%).",
                "- On the 60 `conflict` cases, 59 matched in every run, and the only"
                " case missed in runs 1 and 2 (`pc-19-conflict`, matched in run 3) is"
                " one of the discrepancy cases above where the four human raters scored"
                " `speaker-2` (Noah) at 1.75 because `speaker-1` (Finnegan, 3.00)"
                " escalated instead.",
                "- On the 60 `nonconflict` cases, 56 had no interventions in any run"
                " (173 of 180 runs matched, 96.1%). Only `pc-03-nonconflict` had an"
                " intervention in all three runs, while `pc-22-nonconflict`,"
                " `pc-31-nonconflict`, and `pc-57-nonconflict` had an intervention in"
                " one or two runs.",
                "- Scored against the four-rater threshold (`chosen_ss >= 2.50`)"
                " instead of `convo_type`, Run 1 matched 109 of 120 (90.8%), Run 2"
                " matched 108 of 120 (90.0%), and Run 3 matched 108 of 120 (90.0%)"
                " (325 of 360 runs total, 90.3%). On the 110 cases where the four"
                " raters and `convo_type` agree, 323 of 330 runs matched (97.9%).",
                "",
                *_format_results_table(score_rows),
            ]
        )

    (cases_dir / "persona_conflicts_predictions.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8"
    )


def _write_convokit_outputs(
    cases: list[_ConvokitCase],
    cases_dir: Path,
    score_path: Path = DEFAULT_CGA_SCORE,
) -> None:
    jsonl_lines = [
        line for case in cases for line in _turns_to_jsonl_lines(case.case_id, case.turns)
    ]
    (cases_dir / "convokit_cmv.jsonl").write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")

    expected = {
        case.case_id: {"intervene": "yes" if case.has_removed_comment else "no"} for case in cases
    }
    (cases_dir / "convokit_cmv_expected.json").write_text(
        json.dumps(expected, indent=2) + "\n", encoding="utf-8"
    )

    md_lines = [
        "# ConvoKit CGA-CMV Predictions",
        "",
        "Expected outcomes for 74 test threads (37 pairs) from ConvoKit's"
        " `conversations-gone-awry-cmv-corpus` (Chang and Danescu-Niculescu-Mizil, 2019,"
        " https://convokit.cornell.edu/documentation/awry_cmv.html; also used by Kim et al.,"
        " 2026).",
        "",
        "## Source data",
        "",
        "Each thread in the corpus comes from Reddit's `r/changemyview` and stops right"
        " before a final comment. In `awry` threads (`has_removed_comment: true`), moderators"
        " removed that next comment for breaking Rule 2 (rude or hostile behavior). Each"
        " `awry` thread is paired with a `civil` thread (`has_removed_comment: false`) from"
        " the same post and of similar length.",
        "",
        "These 37 pairs are all the pairs in the `test` split (out of 684) where both threads:",
        "",
        "1. Have exactly two speakers.",
        "2. Have no `[deleted]` or `[removed]` comments or usernames.",
        "3. Are at least four turns long, so both people speak at least twice.",
        "",
        "## Speakers and scoring",
        "",
        "The system only decides whether to intervene when a batch includes new speech from"
        " `speaker-2` (the target). Because threads have between 4 and 13 turns, `speaker-2`"
        " is set to whoever speaks the last visible turn in the thread, and `speaker-1` is"
        " the other speaker. That way every case gets an action decision on its final turn.",
        "",
        "`convokit_cmv_expected.json` predicts **Yes** for `awry` threads and **No** for"
        " `civil` threads. Because the corpus cuts each `awry` thread off *before* the"
        " rule-breaking comment (which `speaker-1` posts in reply to `speaker-2`'s last"
        " turn), an `awry` thread does not always contain an overt attack in the visible"
        " text. Scoring against `has_removed_comment` tests how often hostility is already"
        " clear before the removed reply.",
        "",
        "## Predictions",
        "",
        "| Case | ConvoKit `conversation_id` | Matched `pair_id` | `has_removed_comment` |"
        " Turns | `speaker-2` (turn $N$ target) | `speaker-1` (turn $N-1$ / $N+1$) |"
        " Final visible turn ($N$) quote | Intervene |",
        "|---|---|---|---|---:|---|---|---|---|",
    ]

    for case in cases:
        intervene_cell = "Yes" if case.has_removed_comment else "No"
        md_lines.append(
            f"| `{case.case_id}` | `{case.conversation_id}` | `{case.pair_id}`"
            f" | `{case.has_removed_comment}` | {len(case.turns)}"
            f" | `{case.speaker_2_name}` | `{case.speaker_1_name}`"
            f' | "{case.final_turn_quote}" | {intervene_cell} |'
        )

    score_rows = _load_score_rows(score_path)
    if score_rows:
        md_lines.extend(
            [
                "",
                "## Results",
                "",
                "Three replays of each case with `jev-1.14.0`, prompt `conversation-3`,"
                " and no discovered model (`data/eval/convokit-cmv-2026-11-19`), scored"
                " by `scripts/evaluate.py`. The number after each behavior is how many"
                " of the three replays had a target turn at the 0.7 threshold."
                " Interventions and first turn list the count and first intervention"
                " turn from each replay.",
                "",
                "- Run 1 matched 46 of 74 (62.2%), Run 2 matched 46 of 74 (62.2%), and"
                " Run 3 matched 44 of 74 (59.5%) (136 of 222 runs total, 61.3%).",
                "- Whether a case had an intervention was unchanged across all three"
                " runs in 69 of 74 cases (93.2%).",
                "- On the 37 `awry` prefixes, the system intervened in 23, 23, and 22"
                " cases (59.5%-62.2%) and stayed silent in the remaining 14-15 prefixes"
                " where the removed attack had not yet happened.",
                "- On the 37 `civil` threads, the system stayed silent in 23, 23, and"
                " 22 cases (59.5%-62.2%) and intervened in 14-15 debates where sharp"
                " disagreement or sarcasm was flagged as criticism, contempt, or"
                " defensiveness despite not breaking Reddit's moderator rule.",
                "",
                *_format_results_table(score_rows),
            ]
        )

    (cases_dir / "convokit_cmv_predictions.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pc-dir",
        type=Path,
        default=DEFAULT_PC_DIR,
        help="Path to PersonaConflicts repository directory",
    )
    parser.add_argument(
        "--cga-dir",
        type=Path,
        default=DEFAULT_CGA_DIR,
        help="Path to ConvoKit conversations-gone-awry-cmv-corpus directory",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=DEFAULT_CASES_DIR,
        help="Output directory for generated case JSONL, expected JSON, and predictions markdown",
    )
    args = parser.parse_args()
    args.cases_dir.mkdir(parents=True, exist_ok=True)

    pc_cases = _load_persona_conflicts(args.pc_dir)
    _write_persona_conflicts_outputs(pc_cases, args.cases_dir)

    cga_cases = _load_convokit_cmv(args.cga_dir)
    _write_convokit_outputs(cga_cases, args.cases_dir)

    print(
        f"Extracted {len(pc_cases)} PersonaConflicts cases and"
        f" {len(cga_cases)} ConvoKit CGA-CMV cases into {args.cases_dir}"
    )


if __name__ == "__main__":
    main()
