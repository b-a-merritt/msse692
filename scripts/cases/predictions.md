# Case Predictions

Expected outcomes for the target (`speaker-2`) in each case, stated as what should happen rather than what any detector would catch. All 12 cases are scored.

## What counts as undesirable

Intervene when the target's speech is directed at the listener, would harm them, and has not been repaired:

- **Criticism:** attacks the person rather than a specific act.
- **Contempt:** mockery, scorn, or superiority.
- **Cruelty:** a wish or threat to hurt, intimidate, or humiliate.
- **Defensiveness:** counterattack or blame that blocks repair.
- **Stonewalling:** explicit refusal to engage.
- **Interruption:** repeatedly cutting the other speaker off.

Loudness, emotion, long turns, profanity used for emphasis rather than at the listener, complaints about a specific act, and setting a boundary are not undesirable by themselves.

| Query-based rule | Treatment |
|---|---|
| Loud and fast, shouting | Not a behavior; signal levels inform hostility intensity only |
| Extended turn | Not a behavior |
| Absolutist phrase ("you always") | Criticism only when it generalizes about the person |
| Vulgar language | Swearing; intervene only when aimed at the listener |
| Character label ("crazy") | Criticism or contempt |
| Repeated interruption | Interruption |

## Predictions

| Case | Inappropriate speech | Expected behaviors | Intervene |
|---|---|---|---|
| 1 | "anyone else in their right mind", "goddamn punishment", "I swear to God—" | criticism, contempt, cruelty, swearing | Yes |
| 2 | "You're all the bad things", "It's pathetic", "I hope you're dead… and die" | criticism, contempt, cruelty, defensiveness, swearing | Yes, several; none after "I'm sorry" |
| 3 | "you used to sleep with the door guy"; after apologizing, "Because you go to BU" | contempt | Yes; the second remark is unrepaired |
| 4 | "you're fucking nuts", "put up with your shit", "your fucking French ass… blew that guy" | criticism, contempt, defensiveness, swearing | Yes |
| 5 | "Book dropper! Child mentioner!", the "Get the Guests" story, "Beg, baby", "She'll get over it" | cruelty, contempt | Yes |
| 6 | None. A complaint about infidelity, loud and emotional ("You always… you take") | None | No |
| 7 | "Who walked out of the house 15 months ago?", "What makes you so sure he wants you?" | defensiveness, criticism | Either |
| 8 | "You clearly don't know who you're talking to", "I am the danger", "I am the one who knocks" | contempt, cruelty | Yes |
| 9 | "admiring my own gallantry", "a special agent sent here to ruin my evening", "Show me your gun", "fuck off to back where you came from" | contempt, cruelty, swearing | Yes |
| 10 | "Who cares?", "you're acting crazy again", "All you do is nag me!", "I just want to be left the hell alone" | criticism, contempt, defensiveness, stonewalling, swearing | Yes |
| 11 | None. A confrontational but caring monologue ("cocky, scared shitless kid") | swearing | No |
| 12 | None. An apology and an introduction | None | No |

## Scoring

- **Intervention:** a case matches when it has at least one intervention and the prediction is Yes, none and the prediction is No, or either and the prediction is Either.
- **Behaviors:** an expected behavior is found when any target turn scores it at the 0.7 threshold. Report found, missed, and unexpected behaviors per case.
- Cases 6 and 11 test context: they contain the shouting or swearing a phrase list matches, but call for no intervention.

## Query-based baseline

The query-based results from the post-fix rerun in `docs/quality_assurance_report.md`, scored against these predictions. Cases 1 and 2 tuned those rules and have no recorded results, so they are not in the baseline; results on them would favor the rules.

| Case | Interventions | Predicted | Result |
|---|---|---|---|
| 3 | None | Yes | Missed |
| 4 | Vulgar language, character label, extended turn | Yes | Match |
| 5 | Loud and fast, repeated interruption | Yes | Match |
| 6 | Extended turn, absolutist phrase | No | False positive |
| 7 | Loud and fast | Either | Match |
| 8 | None | Yes | Missed |
| 9 | Vulgar language, repeated interruption | Yes | Match |
| 10 | Vulgar language, character label, repeated interruption | Yes | Match |
| 11 | Vulgar language | No | False positive |
| 12 | None | No | Match |

6 of 10 matched: two false positives (cases 6 and 11) and two misses (cases 3 and 8). Cases 5 and 7 matched on rules this file does not treat as undesirable (loud and fast), so their matches do not show the rules found the right speech.

## Decision-model results

One replay of each case with `jev-1.14.0`, prompt `conversation-3`, and no discovered model, scored by the rules above. Cases 5 and 12, the only ones with batches over three turns, were replayed after batches were limited to three turns (ADR 017).

| Case | Interventions | Predicted | Result | Query-based | Found | Missed | Unexpected |
|---|---|---|---|---|---|---|---|
| 1 | 4 | Yes | Match | — | contempt, cruelty, swearing | criticism | — |
| 2 | 9 | Yes | Match | — | contempt, criticism, cruelty, defensiveness, swearing | — | — |
| 3 | 8 | Yes | Match | Missed | contempt | — | defensiveness |
| 4 | 1 | Yes | Match | Match | contempt, criticism, defensiveness, swearing | — | — |
| 5 | 24 | Yes | Match | Match | contempt | cruelty | criticism, defensiveness |
| 6 | 2 | No | False positive | False positive | — | — | defensiveness |
| 7 | 6 | Either | Match | Match | defensiveness | criticism | contempt |
| 8 | 2 | Yes | Match | Missed | contempt | cruelty | defensiveness |
| 9 | 10 | Yes | Match | Match | contempt, swearing | cruelty | criticism, defensiveness |
| 10 | 16 | Yes | Match | Match | contempt, criticism, defensiveness, swearing | stonewalling | — |
| 11 | 4 | No | False positive | False positive | swearing | — | contempt, criticism, cruelty, defensiveness |
| 12 | 0 | No | Match | Match | — | — | — |

8 of 10 matched on cases 3–12, against 6 of 10 for the query-based rules, and cases 1 and 2 matched. The rules' two misses now match: case 3's "door guy" remark scored as contempt, and case 8's threats as contempt.

The two false positives remain for different reasons. In case 6, both interventions follow "Troy, you're hurting me! … Let go!" with no target behavior at the threshold: the model responded to harm against the target, which the definition above does not cover. In case 11, the monologue scored contempt (0.90–0.92) and criticism; the model reads it as an attack, not as care.

Cruelty was missed in cases 5, 8, and 9, including case 8's threats, despite the prompt asking about threats and intimidation. Stonewalling was missed in case 10, and defensiveness was often unexpected.

## Control dialogue

`cases/control/` is AI-written dialogue between one couple, used to test whether discovery finds a known pattern and whether its evidence improves decisions. The target is `speaker-2` (Alex); `speaker-1` is Sam.

**Planted pattern.** Sam's mother, then money from the couple's savings, is followed by Alex's contempt and criticism. Either topic alone stays calm. Because the pattern was written into the data, these cases show whether the mechanism can find a pattern, not that real couples have one.

| Training | Content | Undesired target behavior |
|---|---|---|
| `control-train-01`–`06` | Other topics, then the pattern, then conflict | contempt, criticism; stonewalling in 06 |
| `control-train-07` | Budget review only | None |
| `control-train-08` | Mother's visit only | None |

Discovery should require both `extended_family` (the mother) and `budgeting` (the savings) before `undesired_behavior`, in either order; neither topic alone gives evidence.

| Held out | Content | Without evidence | With evidence |
|---|---|---|---|
| `control-test-01` | Pattern; tense but civil replies; then contempt and criticism | Intervene at the attack | Intervene, possibly during the tense replies |
| `control-test-02` | Same, ending in stonewalling | Intervene at the attack | Intervene, possibly during the tense replies |
| `control-test-03` | Pattern; Alex responds constructively | No | No |
| `control-test-04` | Pattern; Alex sounds annoyed, then apologizes and agrees | No | No |
| `control-test-05` | Unrelated topic, calm | No | No |
| `control-test-06` | Unrelated topic, criticism and stonewalling | Intervene | Intervene, unchanged |

Evidence helps if the first intervention in 01 and 02 comes earlier, 03–06 are unchanged, and behavior scores do not differ between the two runs. Run each held-out case at least three times per condition; answers vary between runs.
