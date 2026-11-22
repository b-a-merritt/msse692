# PersonaConflicts Predictions

Expected outcomes for the 120 human-rated dialogues (60 conflict and non-conflict pairs) from Shen et al. (2025), *Words Like Knives: Backstory-Personalized Modeling and Detection of Violent Communication* (EMNLP 2025, https://github.com/mitmedialab/persona-conflicts-corpus-emnlp-2025).

## Source data

`mturk_aggregate.csv` has 240 rows: 120 conversations rated twice each by Amazon Mechanical Turk workers, once with a positive backstory for the main character (`mturk_positive_backstory.csv`) and once with a negative backstory (`mturk_negative_backstory.csv`), with two raters per condition (four total). All 120 conversations are included here:

- `pc-01` to `pc-50` (`main`): 50 conflict cases (`id` 0-49) paired with 50 non-conflict cases (`id` 125-174) from `dataset_final.csv`.
- `pc-51` to `pc-60` (`pilot`): the other 20 rated conversations in `mturk_aggregate.csv` (`id` 0-9 for conflict, `id` 10-19 for non-conflict).

The character whose backstory was varied (`chosen_character`) is `speaker-2` (the target), and the other speaker is `speaker-1`. Turn times are spaced 0.2 s apart with neutral signal levels (-50 / -25 / -10 dBFS) so an entire 15- or 16-turn conversation fits inside the 30 s context window.

Three source-data anomalies appear in `transformed_conversation`:

- `pc-01-conflict` (`id` 0) and `pc-32-conflict` (`id` 31) have 16 turns (`turn` 1-16); `mturk_aggregate.csv` truncates `turn_problematic_avg` and `turn_vc_union` to 15 elements, whereas the raw MTurk CSVs include `turn_16`.
- `pc-09-conflict` (`id` 8) has 12 turns because turn numbers `[3, 9, 14]` are skipped in `transformed_conversation`, and `pc-36-nonconflict` (`id` 160) has 14 turns because turn number `[10]` is skipped.
- `pc-06-conflict` (`id` 5) turn 3 has a stage direction (`(Isabelle sits quietly while Jasmine starts making seemingly unnecessary noise: bouncing a yoga ball, clanging pots and pans in the kitchen, humming loudly.)`) split across the `speaker` and `text` fields and is attributed to `speaker-2` (Jasmine).

## Labels and ratings

`persona_conflicts_expected.json` uses the scenario label (`convo_type`): **Yes** for `conflict` and **No** for `nonconflict`.

Conversation-level ratings (`chosen_ss` and `other_ss`) come from the four-rater averages in `mturk_aggregate.csv` (`neg_row` and `pos_row` averaged together), while turn-level ratings (`tp_max` and `Target VC tags`) are joined directly from `mturk_positive_backstory.csv` and `mturk_negative_backstory.csv` across the four worker rows using each turn's explicit `turn` number (`1-16`):

- `chosen_ss` and `other_ss`: average answer (1-4) to whether `speaker-2` or `speaker-1` said anything they should not have said.
- `tp_max`: highest four-rater average turn-level problematic rating (1-4, `Answer.is_problematic_turn_<1..16>.*`) among `speaker-2`'s turns.
- `Target VC tags`: Nonviolent Communication violations marked by raters on `speaker-2`'s turns (`Comparison`, `Demand`, `Denial of Responsibility`, `Deserve Thinking`, `Moralistic Judgment`).

## Where the raters and scenario label disagree

In 110 of the 120 cases, the `convo_type` label matches whether `chosen_ss` is at least 2.50 (the midpoint of the 1-4 scale). The 10 cases where they differ are listed below:

| Case | `convo_type` | `speaker-2` (`chosen`) | `chosen_ss` | `other_ss` | `tp_max_chosen` | Why they differ |
|---|---|---|---:|---:|---:|---|
| `pc-02-conflict` | `conflict` | Leo | 2.00 | 2.25 | 2.75 | `speaker-1` (Naomi, 2.25) escalated more than `speaker-2` (Leo) |
| `pc-05-conflict` | `conflict` | Gwen | 2.25 | 2.75 | 2.00 | `speaker-1` (Isabelle, 2.75) escalated more than `speaker-2` (Gwen) |
| `pc-15-nonconflict` | `nonconflict` | Ethan | 2.75 | 2.25 | 2.75 | Raters scored `Ethan` at 2.75 in a non-conflict scenario |
| `pc-19-conflict` | `conflict` | Noah | 1.75 | 3.00 | 2.00 | `speaker-1` (Finnegan, 3.00) escalated more than `speaker-2` (Noah) |
| `pc-24-conflict` | `conflict` | Calista | 1.75 | 3.25 | 3.25 | `speaker-1` (Isabelle, 3.25) escalated more than `speaker-2` (Calista) |
| `pc-30-conflict` | `conflict` | Hendrick | 2.00 | 3.25 | 3.25 | `speaker-1` (Ethan, 3.25) escalated more than `speaker-2` (Hendrick) |
| `pc-35-conflict` | `conflict` | Imelda | 2.25 | 3.00 | 3.50 | `speaker-1` (Ethan, 3.00) escalated more than `speaker-2` (Imelda) |
| `pc-44-nonconflict` | `nonconflict` | Imelda | 2.50 | 1.25 | 2.50 | Raters scored `Imelda` at 2.50 in a non-conflict scenario |
| `pc-45-nonconflict` | `nonconflict` | Imelda | 2.50 | 1.75 | 2.25 | Raters scored `Imelda` at 2.50 in a non-conflict scenario |
| `pc-47-nonconflict` | `nonconflict` | Isabelle | 2.50 | 1.75 | 2.00 | Raters scored `Isabelle` at 2.50 in a non-conflict scenario |

## Predictions

| Case | Batch | `id` | `neg_row` | `pos_row` | `df_row` | `speaker-2` | `speaker-1` | `chosen_ss` | `other_ss` | `tp_max` | Target VC tags (`turn_vc_union`) | Peak target turn quote | Intervene |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|
| `pc-01-conflict` | main | 0 | 55 | 229 | 0 | Benjamin | Gwen | 2.50 | 3.00 | 3.25 | Demand, Moralistic Judgment | "That's where you're wrong. Things need order. You can't just live life randomly." | Yes |
| `pc-01-nonconflict` | main | 125 | 49 | 195 | 125 | Benjamin | Gwen | 1.75 | 1.50 | 1.75 | Comparison, Demand, Moralistic Judgment | "Hey, I'm going to tidy up a bit. Do you mind if I move some of your stuff around?" | No |
| `pc-02-conflict` | main | 1 | 115 | 121 | 1 | Leo | Naomi | 2.00 | 2.25 | 2.75 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "No, I just... I feel like you're choosing work over our relationship." | Yes |
| `pc-02-nonconflict` | main | 126 | 58 | 224 | 126 | Leo | Naomi | 2.00 | 1.50 | 2.25 | Comparison, Denial of Responsibility, Deserve Thinking | "I know, I should have told you sooner. But I didn't know how." | No |
| `pc-03-conflict` | main | 2 | 86 | 205 | 2 | Baxter | Isabelle | 3.50 | 3.25 | 3.75 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Well, then find a better way to do your \"hobby.\" I never left messes around when I…" | Yes |
| `pc-03-nonconflict` | main | 127 | 57 | 145 | 127 | Baxter | Isabelle | 2.00 | 2.00 | 2.50 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Really? And leave me to my rare plants?" | No |
| `pc-04-conflict` | main | 3 | 37 | 163 | 3 | Finnegan | Esmeralda | 3.50 | 2.50 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Maybe if you weren't so emotionally distant, Esme, you would know the answer by now.…" | Yes |
| `pc-04-nonconflict` | main | 128 | 67 | 150 | 128 | Esmeralda | Finnegan | 1.50 | 1.25 | 2.00 | Comparison, Denial of Responsibility, Moralistic Judgment | "Well, at least you've got your paintings to keep you company." | No |
| `pc-05-conflict` | main | 4 | 80 | 236 | 4 | Gwen | Isabelle | 2.25 | 2.75 | 2.00 | Demand, Deserve Thinking, Moralistic Judgment | "That's really harsh, Belle. I thought..." | Yes |
| `pc-05-nonconflict` | main | 129 | 90 | 211 | 129 | Gwen | Isabelle | 2.00 | 1.50 | 2.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I Well... like, physically? Maybe a hug every now and then..." | No |
| `pc-06-conflict` | main | 5 | 117 | 223 | 5 | Jasmine | Isabelle | 2.50 | 2.25 | 3.50 | Comparison, Denial of Responsibility, Moralistic Judgment | "Oh, what? Like you always consider my needs before practicing your 'magic tricks' in…" | Yes |
| `pc-06-nonconflict` | main | 130 | 14 | 214 | 130 | Jasmine | Isabelle | 2.25 | 1.25 | 3.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Alright, just checking. You've been acting a little... different lately." | No |
| `pc-07-conflict` | main | 6 | 81 | 208 | 6 | Benjamin | Gwen | 3.25 | 2.50 | 3.50 | Comparison, Denial of Responsibility, Moralistic Judgment | "Maybe you should try to take care of yourself more, you know? You're always out help…" | Yes |
| `pc-07-nonconflict` | main | 131 | 73 | 134 | 131 | Gwen | Benjamin | 1.00 | 1.25 | 1.75 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I get that. But remember this: Holding space for others doesn’t mean losing yourself." | No |
| `pc-08-conflict` | main | 7 | 102 | 204 | 7 | Imelda | Gwen | 3.50 | 3.25 | 3.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "You might think it's trivial, but it's taking up physical and mental space." | Yes |
| `pc-08-nonconflict` | main | 132 | 40 | 191 | 132 | Imelda | Gwen | 2.00 | 1.75 | 2.50 | Deserve Thinking, Moralistic Judgment | "Still, I don't like the idea of you thinking you have to do it all by yourself." | No |
| `pc-09-conflict` | main | 8 | 38 | 131 | 8 | Gwen | Isabelle | 3.25 | 2.75 | 3.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Isabelle, we need to talk about your future." | Yes |
| `pc-09-nonconflict` | main | 133 | 78 | 124 | 133 | Gwen | Isabelle | 1.25 | 1.50 | 1.75 | Deserve Thinking | "I hope so. I'm nervous but excited." | No |
| `pc-10-conflict` | main | 9 | 103 | 228 | 9 | Imelda | Ethan | 3.50 | 3.00 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Well, at least I am using my head, Ethan." | Yes |
| `pc-10-nonconflict` | main | 134 | 46 | 188 | 134 | Imelda | Ethan | 1.50 | 1.25 | 1.50 | Moralistic Judgment | "Keep honing your skills, Ethan. You never know when a career change might come in ha…" | No |
| `pc-11-conflict` | main | 10 | 9 | 199 | 10 | Naomi | Leo | 3.00 | 2.00 | 4.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Hm. Well, is there anything else you wanna complain about?" | Yes |
| `pc-11-nonconflict` | main | 135 | 15 | 221 | 135 | Leo | Naomi | 1.00 | 1.00 | 1.25 | — | "And you chose...?" | No |
| `pc-12-conflict` | main | 11 | 68 | 222 | 11 | Oliver | Gwen | 3.50 | 2.75 | 3.75 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "It's not about the coat, Gwen. You always seem to leave stuff everywhere. It's chaos." | Yes |
| `pc-12-nonconflict` | main | 136 | 64 | 178 | 136 | Oliver | Gwen | 1.50 | 1.75 | 1.25 | — | "Dull or not, they match really well with the rug's color, don't you think?" | No |
| `pc-13-conflict` | main | 12 | 41 | 227 | 12 | Leo | Naomi | 3.25 | 3.25 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Right! Blame it on my choice of career or my so-called 'insensitivity.' Always a def…" | Yes |
| `pc-13-nonconflict` | main | 137 | 19 | 135 | 137 | Leo | Naomi | 1.25 | 1.25 | 1.50 | Moralistic Judgment | "Yeah, it's still a bit unsettling. But we'll manage, we always did." | No |
| `pc-14-conflict` | main | 13 | 76 | 151 | 13 | Calista | Amara | 2.75 | 2.50 | 3.25 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I don't see why you should have all the say about it. We both live here." | Yes |
| `pc-14-nonconflict` | main | 138 | 84 | 164 | 138 | Calista | Amara | 1.50 | 1.00 | 2.25 | Demand, Denial of Responsibility, Moralistic Judgment | "Yeah, that one. I just... I don't know. I'm not sure it's the right message." | No |
| `pc-15-conflict` | main | 14 | 2 | 185 | 14 | Imelda | Ethan | 3.25 | 2.25 | 3.25 | Comparison, Denial of Responsibility, Moralistic Judgment | "Neutrinos can't be seen, true, but they have real-world implications, Ethan. They're…" | Yes |
| `pc-15-nonconflict` | main | 139 | 91 | 186 | 139 | Ethan | Imelda | 2.75 | 2.25 | 2.75 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Yeah, some change. Who knows?" | No |
| `pc-16-conflict` | main | 15 | 28 | 162 | 15 | Oliver | Gwen | 3.50 | 2.25 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Suffocating? Is that how you see it? Even my affection bothers you now!" | Yes |
| `pc-16-nonconflict` | main | 140 | 10 | 175 | 140 | Oliver | Gwen | 2.25 | 1.50 | 2.25 | Demand, Denial of Responsibility, Moralistic Judgment | "Lately, well...I feel like maybe we could be closer. You know, physically." | No |
| `pc-17-conflict` | main | 16 | 88 | 235 | 16 | Finnegan | Ava | 3.00 | 3.25 | 3.00 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "To obvious eyes...perhaps." | Yes |
| `pc-17-nonconflict` | main | 141 | 100 | 127 | 141 | Finnegan | Ava | 1.25 | 1.00 | 1.75 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "I might not have your artistic eye, but the way the light dances on the water... it'…" | No |
| `pc-18-conflict` | main | 17 | 23 | 192 | 17 | Gwen | Isabelle | 2.75 | 3.00 | 2.25 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "Isabelle, is everything okay? You seem a bit...distant." | Yes |
| `pc-18-nonconflict` | main | 142 | 21 | 233 | 142 | Gwen | Isabelle | 1.25 | 1.50 | 1.00 | — | "Well, honey, it's entirely up to you." | No |
| `pc-19-conflict` | main | 18 | 116 | 202 | 18 | Noah | Finnegan | 1.75 | 3.00 | 2.00 | Denial of Responsibility | "Well, it's just... I've noticed that you always seem to devalue your paintings, man.…" | Yes |
| `pc-19-nonconflict` | main | 143 | 62 | 220 | 143 | Finnegan | Noah | 2.00 | 1.25 | 2.25 | Comparison, Moralistic Judgment | "Stand-up comedy? You?" | No |
| `pc-20-conflict` | main | 19 | 114 | 166 | 19 | Noah | Finnegan | 2.75 | 2.25 | 3.50 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Right, 'soul-searching'. All those late-night gatherings and weird sorcerer stuff." | Yes |
| `pc-20-nonconflict` | main | 144 | 56 | 226 | 144 | Finnegan | Noah | 2.00 | 1.00 | 1.50 | Comparison, Denial of Responsibility, Deserve Thinking | "Comedy, huh? That's a surprise." | No |
| `pc-21-conflict` | main | 20 | 33 | 193 | 20 | Gwen | Benjamin | 2.75 | 1.75 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Oh come on, Benjamin. Don't be ridiculous. It’s just a little cat food." | Yes |
| `pc-21-nonconflict` | main | 145 | 70 | 141 | 145 | Benjamin | Gwen | 1.25 | 1.00 | 1.50 | Comparison | "Yeah. No impact is too small, right?" | No |
| `pc-22-conflict` | main | 21 | 54 | 157 | 21 | Oliver | Liam | 3.75 | 2.50 | 4.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I don't recall you having such severe allergies. Maybe it’s just all in your head." | Yes |
| `pc-22-nonconflict` | main | 146 | 94 | 206 | 146 | Oliver | Liam | 1.75 | 1.25 | 2.00 | Denial of Responsibility, Deserve Thinking | "Was sorta surprisin' you with it." | No |
| `pc-23-conflict` | main | 22 | 118 | 183 | 22 | Benjamin | Gwen | 3.25 | 1.25 | 3.75 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "And I thought you knew better than to play victim all the time. Can't you just leave…" | Yes |
| `pc-23-nonconflict` | main | 147 | 101 | 239 | 147 | Benjamin | Gwen | 1.50 | 1.25 | 2.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I can see that. It's always hard when people around you are in conflict." | No |
| `pc-24-conflict` | main | 23 | 43 | 168 | 23 | Calista | Isabelle | 1.75 | 3.25 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I can't read your mind, Izzy. You need to... forget it." | Yes |
| `pc-24-nonconflict` | main | 148 | 83 | 126 | 148 | Calista | Isabelle | 1.25 | 1.25 | 1.75 | — | "Hmm, it’s not like I haven’t seen your place messy before." | No |
| `pc-25-conflict` | main | 24 | 112 | 176 | 24 | Jaxon | Calista | 3.25 | 2.00 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "So, it's a problem now? All I did was help you, and you twist it into an argument." | Yes |
| `pc-25-nonconflict` | main | 149 | 44 | 129 | 149 | Jaxon | Calista | 1.75 | 2.25 | 1.75 | Denial of Responsibility | "Maybe, maybe not." | No |
| `pc-26-conflict` | main | 25 | 65 | 215 | 25 | Isabella | Sophia | 3.25 | 2.25 | 3.50 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Well, considering how you could barely keep your job at the bar..." | Yes |
| `pc-26-nonconflict` | main | 150 | 31 | 213 | 150 | Sophia | Isabella | 2.25 | 2.00 | 2.50 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Maybe not 'okay'. But I'm willing to compromise." | No |
| `pc-27-conflict` | main | 26 | 11 | 149 | 26 | Isabelle | Jasmine | 4.00 | 1.50 | 3.25 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "Yeah, heard that one before, haven't we?" | Yes |
| `pc-27-nonconflict` | main | 151 | 8 | 165 | 151 | Jasmine | Isabelle | 1.00 | 1.00 | 1.75 | Deserve Thinking | "I just want you to know, I might not fully understand it, but... I'm trying." | No |
| `pc-28-conflict` | main | 27 | 53 | 147 | 27 | Baxter | Isabelle | 3.75 | 2.75 | 4.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Isabelle, get out. Now. Just take your books and study your fancy magic somewhere el…" | Yes |
| `pc-28-nonconflict` | main | 152 | 3 | 225 | 152 | Baxter | Isabelle | 1.50 | 1.00 | 2.00 | Comparison, Moralistic Judgment | "Magic, huh. I never took you for an illusionist fan." | No |
| `pc-29-conflict` | main | 28 | 85 | 187 | 28 | Mia | Oliver | 2.75 | 2.00 | 3.25 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I get it, Oliver, I do. But clinging onto the pain won't change anything." | Yes |
| `pc-29-nonconflict` | main | 153 | 16 | 212 | 153 | Oliver | Mia | 1.00 | 1.25 | 1.50 | Denial of Responsibility | "Indeed. The laughter, the innocent banter. Wish I could go back in time." | No |
| `pc-30-conflict` | main | 29 | 39 | 169 | 29 | Hendrick | Ethan | 2.00 | 3.25 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I clean up after you almost every day, Ethan. Do you really think that's fair?" | Yes |
| `pc-30-nonconflict` | main | 154 | 29 | 171 | 154 | Hendrick | Ethan | 2.00 | 1.25 | 2.00 | Demand, Denial of Responsibility | "Can you lend me a hand here, dear? This mess won't sort itself out." | No |
| `pc-31-conflict` | main | 30 | 113 | 217 | 30 | Oliver | Mia | 3.75 | 1.25 | 4.00 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "Maybe if you weren't hiding your talent like it was some sort of crime, I wouldn't h…" | Yes |
| `pc-31-nonconflict` | main | 155 | 75 | 207 | 155 | Oliver | Mia | 2.25 | 2.00 | 2.75 | Demand, Deserve Thinking, Moralistic Judgment | "I found your painting supplies tucked away. Mia, why would you hide something like t…" | No |
| `pc-32-conflict` | main | 31 | 97 | 144 | 31 | Jaxon | Emily | 2.75 | 3.00 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "That was...I didn't mean it. I wasn't thinking straight." | Yes |
| `pc-32-nonconflict` | main | 156 | 52 | 122 | 156 | Jaxon | Emily | 1.25 | 1.50 | 1.25 | — | "But isn't that... subjective? Interfering with objectivity?" | No |
| `pc-33-conflict` | main | 32 | 45 | 181 | 32 | Benjamin | Gwen | 3.25 | 3.25 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Perspective? You leave your clutter all around and then you blame me for wanting ord…" | Yes |
| `pc-33-nonconflict` | main | 157 | 74 | 143 | 157 | Benjamin | Gwen | 1.50 | 1.25 | 1.25 | — | "Oh, hey Gwen, don't you think the place is a bit messy?" | No |
| `pc-34-conflict` | main | 33 | 18 | 219 | 33 | Hendrick | Ethan | 3.25 | 2.50 | 3.25 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Ethan, those dishes need cleaning. You've left them piled up again!" | Yes |
| `pc-34-nonconflict` | main | 158 | 119 | 167 | 158 | Hendrick | Ethan | 1.00 | 1.25 | 2.25 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Indeed. But their bickering is disrupting our quiet evenings. What's your take?" | No |
| `pc-35-conflict` | main | 34 | 6 | 190 | 34 | Imelda | Ethan | 2.25 | 3.00 | 3.50 | Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Alright, have it your way. Don't complain when things mess up." | Yes |
| `pc-35-nonconflict` | main | 159 | 61 | 172 | 159 | Imelda | Ethan | 1.50 | 1.50 | 3.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Well, that’s part of leadership, Ethan. Tough choices, unpopular decisions. Not alwa…" | No |
| `pc-36-conflict` | main | 35 | 30 | 137 | 35 | Amara | Gwen | 3.25 | 2.50 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Honestly, it's your wishy-washy approach to everything that just... I mean, it frust…" | Yes |
| `pc-36-nonconflict` | main | 160 | 26 | 230 | 160 | Amara | Gwen | 1.00 | 1.00 | 1.50 | Demand, Denial of Responsibility, Moralistic Judgment | "Oh, Gwen, I had no idea..." | No |
| `pc-37-conflict` | main | 36 | 72 | 177 | 36 | Calista | Isabelle | 3.25 | 2.50 | 4.00 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I see. So this is what it's really about, huh? About being in control." | Yes |
| `pc-37-nonconflict` | main | 161 | 93 | 123 | 161 | Calista | Isabelle | 1.25 | 1.00 | 2.25 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "Why scary?" | No |
| `pc-38-conflict` | main | 37 | 0 | 130 | 37 | Jaxon | Emily | 3.50 | 2.75 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "It's not tearing apart, it's constructive criticism! Maybe if you actually paid atte…" | Yes |
| `pc-38-nonconflict` | main | 162 | 69 | 238 | 162 | Emily | Jaxon | 2.00 | 2.25 | 2.75 | Comparison, Denial of Responsibility, Moralistic Judgment | "What? But why would you risk your integrity, Jax?" | No |
| `pc-39-conflict` | main | 38 | 17 | 200 | 38 | Gwen | Isabelle | 2.50 | 3.00 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "But magic, sweetie? Really? It’s... it's not like science, you know. It doesn't pay…" | Yes |
| `pc-39-nonconflict` | main | 163 | 92 | 189 | 163 | Gwen | Isabelle | 1.50 | 1.75 | 2.25 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "No. It's been hard for me." | No |
| `pc-40-conflict` | main | 39 | 48 | 152 | 39 | Imelda | Gwen | 3.00 | 2.50 | 3.75 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "It's... Honestly, it looks sloppy. The stitches aren't even consistent." | Yes |
| `pc-40-nonconflict` | main | 164 | 24 | 156 | 164 | Imelda | Gwen | 1.50 | 1.50 | 2.00 | Comparison, Deserve Thinking, Moralistic Judgment | "Perfection is an impossible goal, Gwen. Just remember that what you're doing is inhe…" | No |
| `pc-41-conflict` | main | 40 | 79 | 234 | 40 | Oliver | Liam | 3.50 | 2.00 | 4.00 | Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "And I don't need you pulling this martyr routine! Always playing the victim..." | Yes |
| `pc-41-nonconflict` | main | 165 | 35 | 125 | 165 | Oliver | Liam | 1.50 | 1.50 | 1.50 | Comparison, Demand, Moralistic Judgment | "Where is this coming from?" | No |
| `pc-42-conflict` | main | 41 | 5 | 173 | 41 | Oliver | Liam | 3.25 | 2.75 | 3.75 | Comparison, Denial of Responsibility, Moralistic Judgment | "Well, sorry for not being at your beck and call." | Yes |
| `pc-42-nonconflict` | main | 166 | 36 | 196 | 166 | Oliver | Liam | 1.00 | 1.00 | 1.50 | Denial of Responsibility | "Frankly, it was just what anyone else would do." | No |
| `pc-43-conflict` | main | 42 | 87 | 154 | 42 | Gwen | Benjamin | 2.75 | 2.50 | 3.75 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Well, you should have told me in the first place that you would get this upset about…" | Yes |
| `pc-43-nonconflict` | main | 167 | 95 | 203 | 167 | Benjamin | Gwen | 1.75 | 2.50 | 1.50 | — | "Ouch. Well played, sis. But yes, I suppose in a way. I still respect you and your wo…" | No |
| `pc-44-conflict` | main | 43 | 22 | 142 | 43 | Imelda | Gwen | 3.75 | 2.75 | 3.50 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "It's just that I cleaned up before you started and it feels like you don't even see…" | Yes |
| `pc-44-nonconflict` | main | 168 | 60 | 184 | 168 | Imelda | Gwen | 2.50 | 1.25 | 2.50 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "You know, Gwen, I've been doing some thinking." | No |
| `pc-45-conflict` | main | 44 | 110 | 231 | 44 | Imelda | Gwen | 4.00 | 2.50 | 3.75 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I see how it is... You just throw that at my face every time you can. No discussion…" | Yes |
| `pc-45-nonconflict` | main | 169 | 1 | 140 | 169 | Imelda | Gwen | 2.50 | 1.75 | 2.25 | Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Oh. That came out of left field. What exactly do you mean?" | No |
| `pc-46-conflict` | main | 45 | 104 | 132 | 45 | Calista | Isabelle | 3.25 | 3.25 | 2.50 | Denial of Responsibility | "I don’t… What? That’s unfair, Izzy." | Yes |
| `pc-46-nonconflict` | main | 170 | 66 | 201 | 170 | Isabelle | Calista | 1.50 | 1.50 | 2.00 | Comparison | "And?" | No |
| `pc-47-conflict` | main | 46 | 20 | 161 | 46 | Isabelle | Gwen | 4.00 | 1.50 | 3.50 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Yeah, I get it. But isn't that something anyone could do?" | Yes |
| `pc-47-nonconflict` | main | 171 | 12 | 182 | 171 | Isabelle | Gwen | 2.50 | 1.75 | 2.00 | Comparison, Deserve Thinking, Moralistic Judgment | "They're not two sides of a coin, Gwen. Maybe more like threads in a fabric." | No |
| `pc-48-conflict` | main | 47 | 108 | 232 | 47 | Isabella | Sophia | 3.25 | 2.00 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "You mean climbing up a dirty hill with a sweaty back? Doesn't seem like a big purpos…" | Yes |
| `pc-48-nonconflict` | main | 172 | 59 | 210 | 172 | Sophia | Isabella | 1.00 | 1.00 | 1.00 | — | "You ever just sit and wonder what really matters to you?" | No |
| `pc-49-conflict` | main | 48 | 77 | 174 | 48 | Isabelle | Jasmine | 2.75 | 1.50 | 3.25 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Oh, the water... I drank it all. It was so hot, I just couldn't help myself." | Yes |
| `pc-49-nonconflict` | main | 173 | 34 | 153 | 173 | Jasmine | Isabelle | 1.50 | 1.50 | 2.50 | Moralistic Judgment | "I could say the same about you." | No |
| `pc-50-conflict` | main | 49 | 111 | 216 | 49 | Benjamin | Gwen | 3.00 | 1.25 | 3.75 | Comparison, Denial of Responsibility, Moralistic Judgment | "Maybe if you were realistic about your capabilities, I wouldn't have to!" | Yes |
| `pc-50-nonconflict` | main | 174 | 82 | 133 | 174 | Gwen | Benjamin | 1.25 | 1.25 | 2.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Don't worry about me, Benjamin. I've been balancing all my life." | No |
| `pc-51-conflict` | pilot | 0 | 32 | 179 | pilot | Ethan | Hendrick | 2.75 | 2.75 | 2.75 | Demand, Denial of Responsibility, Moralistic Judgment | "I understand that, Hendrick, but you need to start thinking about moving on…" | Yes |
| `pc-51-nonconflict` | pilot | 10 | 107 | 197 | pilot | Hendrick | Ethan | 2.00 | 1.25 | 3.00 | Comparison, Denial of Responsibility, Moralistic Judgment | "That's easy for you to say..." | No |
| `pc-52-conflict` | pilot | 1 | 42 | 180 | pilot | Jaxon | Calista | 3.75 | 1.75 | 4.00 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Right, always the innocent, aren't you?" | Yes |
| `pc-52-nonconflict` | pilot | 11 | 27 | 148 | pilot | Calista | Jaxon | 2.00 | 1.50 | 1.75 | Comparison, Demand, Denial of Responsibility | "And nothing. Enjoy the silence. Breathe. You don't need to have something planned ev…" | No |
| `pc-53-conflict` | pilot | 2 | 71 | 159 | pilot | Calista | Amara | 3.50 | 1.75 | 3.50 | Comparison, Demand, Denial of Responsibility, Moralistic Judgment | "Ah, the \"higher purpose.\" I get it. Yet, those sacrifices for creatures who might…" | Yes |
| `pc-53-nonconflict` | pilot | 12 | 89 | 160 | pilot | Amara | Calista | 1.75 | 1.50 | 2.00 | Comparison, Moralistic Judgment | "Ok. What is it this time?" | No |
| `pc-54-conflict` | pilot | 3 | 105 | 218 | pilot | Noah | Finnegan | 3.25 | 2.25 | 3.25 | Comparison, Denial of Responsibility, Moralistic Judgment | "Oh not that again, Finnegan. I understand he was your friend, but he's gone. You nee…" | Yes |
| `pc-54-nonconflict` | pilot | 13 | 50 | 170 | pilot | Noah | Finnegan | 1.25 | 1.00 | 1.25 | — | "Was it about that group you were a part of? The cult?" | No |
| `pc-55-conflict` | pilot | 4 | 96 | 146 | pilot | Isabelle | Gwen | 2.75 | 2.00 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "It's just...it's always about you and what you're doing. What about me? I'm exactly…" | Yes |
| `pc-55-nonconflict` | pilot | 14 | 51 | 209 | pilot | Gwen | Isabelle | 1.25 | 1.00 | 2.00 | Comparison, Denial of Responsibility, Moralistic Judgment | "About how my life turned out. Where I've ended up." | No |
| `pc-56-conflict` | pilot | 5 | 63 | 120 | pilot | Baxter | Isabelle | 3.50 | 1.75 | 3.25 | Comparison, Denial of Responsibility, Moralistic Judgment | "My shop may be messy but at least I'm not serving people subpar coffee and calling i…" | Yes |
| `pc-56-nonconflict` | pilot | 15 | 47 | 237 | pilot | Baxter | Isabelle | 2.00 | 1.00 | 1.75 | Comparison, Deserve Thinking, Moralistic Judgment | "What's gnawing at you, Isabelle?" | No |
| `pc-57-conflict` | pilot | 6 | 99 | 128 | pilot | Gwen | Isabelle | 3.00 | 2.50 | 3.00 | Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Again, Isabelle? Your stuff is scattered all over the house. It could be anywhere." | Yes |
| `pc-57-nonconflict` | pilot | 16 | 109 | 139 | pilot | Gwen | Isabelle | 1.50 | 1.25 | 1.75 | Comparison, Demand, Moralistic Judgment | "Oh, sweetie... I had no idea. You know, you can always move back home, right?" | No |
| `pc-58-conflict` | pilot | 7 | 4 | 155 | pilot | Oliver | Gwen | 2.75 | 3.25 | 2.50 | Comparison, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "Likewise, Gwen." | Yes |
| `pc-58-nonconflict` | pilot | 17 | 98 | 136 | pilot | Oliver | Gwen | 1.50 | 1.00 | 1.25 | — | "You sound surprised!" | No |
| `pc-59-conflict` | pilot | 8 | 25 | 138 | pilot | Oliver | Liam | 3.50 | 1.75 | 3.50 | Comparison, Demand, Denial of Responsibility, Deserve Thinking, Moralistic Judgment | "I guess that makes you the expert, huh, since you've had your fair share of glaring…" | Yes |
| `pc-59-nonconflict` | pilot | 18 | 13 | 158 | pilot | Liam | Oliver | 1.25 | 1.00 | 1.25 | — | "Mm? For what?" | No |
| `pc-60-conflict` | pilot | 9 | 7 | 194 | pilot | Oliver | Mia | 2.75 | 2.75 | 3.25 | Denial of Responsibility, Moralistic Judgment | "You've been sneaking around, huh?" | Yes |
| `pc-60-nonconflict` | pilot | 19 | 106 | 198 | pilot | Oliver | Mia | 1.50 | 1.00 | 1.50 | Moralistic Judgment | "Yeah, that one. You revealed my secret, eh?" | No |

## Results

Three replays of each case with `jev-1.14.0`, prompt `conversation-3`, and no discovered model (`data/eval/persona-conflicts-2026-11-19`), scored by `scripts/evaluate.py`. The number after each behavior is how many of the three replays had a target turn at the 0.7 threshold. Interventions and first turn list the count and first intervention turn from each replay.

- Run 1 matched 117 of 120 (97.5%), Run 2 matched 116 of 120 (96.7%), and Run 3 matched 118 of 120 (98.3%) (351 of 360 runs total, 97.5%).
- Whether a case had an intervention was unchanged across all three runs in 116 of 120 cases (96.7%).
- On the 60 `conflict` cases, 59 matched in every run, and the only case missed in runs 1 and 2 (`pc-19-conflict`, matched in run 3) is one of the discrepancy cases above where the four human raters scored `speaker-2` (Noah) at 1.75 because `speaker-1` (Finnegan, 3.00) escalated instead.
- On the 60 `nonconflict` cases, 56 had no interventions in any run (173 of 180 runs matched, 96.1%). Only `pc-03-nonconflict` had an intervention in all three runs, while `pc-22-nonconflict`, `pc-31-nonconflict`, and `pc-57-nonconflict` had an intervention in one or two runs.
- Scored against the four-rater threshold (`chosen_ss >= 2.50`) instead of `convo_type`, Run 1 matched 109 of 120 (90.8%), Run 2 matched 108 of 120 (90.0%), and Run 3 matched 108 of 120 (90.0%) (325 of 360 runs total, 90.3%). On the 110 cases where the four raters and `convo_type` agree, 323 of 330 runs matched (97.9%).

| Case | Interventions | First turn | Predicted | Result | Behaviors |
|---|---|---|---|---|---|
| `pc-01-conflict` | 3, 3, 3 | 5, 7, 7 | Yes | Match 3 | contempt 2, criticism 3, defensiveness 3 |
| `pc-01-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-02-conflict` | 2, 2, 2 | 5, 5, 5 | Yes | Match 3 | — |
| `pc-02-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-03-conflict` | 6, 6, 7 | 5, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-03-nonconflict` | 1, 1, 1 | 6, 6, 6 | No | False positive 3 | contempt 3, defensiveness 3, stonewalling 3 |
| `pc-04-conflict` | 6, 5, 6 | 5, 5, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-04-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-05-conflict` | 1, 1, 1 | 7, 7, 7 | Yes | Match 3 | — |
| `pc-05-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-06-conflict` | 5, 5, 4 | 3, 3, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-06-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-07-conflict` | 6, 6, 6 | 4, 4, 4 | Yes | Match 3 | defensiveness 3 |
| `pc-07-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-08-conflict` | 5, 4, 5 | 3, 5, 3 | Yes | Match 3 | — |
| `pc-08-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-09-conflict` | 4, 4, 4 | 4, 4, 4 | Yes | Match 3 | — |
| `pc-09-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-10-conflict` | 5, 5, 5 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-10-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-11-conflict` | 5, 5, 5 | 2, 2, 2 | Yes | Match 3 | contempt 3, criticism 1, defensiveness 3 |
| `pc-11-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-12-conflict` | 5, 5, 5 | 5, 5, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, stonewalling 3 |
| `pc-12-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-13-conflict` | 5, 5, 5 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, stonewalling 3 |
| `pc-13-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-14-conflict` | 4, 4, 4 | 3, 3, 3 | Yes | Match 3 | defensiveness 3 |
| `pc-14-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-15-conflict` | 3, 3, 4 | 4, 4, 2 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, stonewalling 3 |
| `pc-15-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-16-conflict` | 6, 6, 6 | 3, 3, 3 | Yes | Match 3 | defensiveness 3 |
| `pc-16-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-17-conflict` | 4, 4, 4 | 5, 5, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-17-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-18-conflict` | 2, 2, 2 | 11, 11, 11 | Yes | Match 3 | — |
| `pc-18-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-19-conflict` | 0, 0, 1 | -, -, 9 | Yes | Missed 2, Match 1 | stonewalling 3 |
| `pc-19-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-20-conflict` | 3, 3, 3 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 1, stonewalling 3 |
| `pc-20-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-21-conflict` | 5, 5, 5 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-21-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-22-conflict` | 6, 6, 6 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-22-nonconflict` | 1, 0, 0 | 9, -, - | No | False positive 1, Match 2 | — |
| `pc-23-conflict` | 5, 5, 5 | 6, 6, 6 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, stonewalling 3 |
| `pc-23-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-24-conflict` | 3, 2, 2 | 7, 13, 13 | Yes | Match 3 | defensiveness 3 |
| `pc-24-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-25-conflict` | 6, 6, 6 | 3, 3, 3 | Yes | Match 3 | defensiveness 3 |
| `pc-25-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-26-conflict` | 6, 6, 6 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-26-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-27-conflict` | 6, 6, 6 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-27-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-28-conflict` | 7, 7, 7 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, stonewalling 3 |
| `pc-28-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-29-conflict` | 5, 5, 5 | 4, 4, 4 | Yes | Match 3 | — |
| `pc-29-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-30-conflict` | 5, 5, 5 | 5, 5, 5 | Yes | Match 3 | defensiveness 3 |
| `pc-30-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-31-conflict` | 6, 6, 6 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-31-nonconflict` | 0, 1, 1 | -, 9, 9 | No | Match 1, False positive 2 | — |
| `pc-32-conflict` | 2, 1, 1 | 11, 13, 13 | Yes | Match 3 | defensiveness 3 |
| `pc-32-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-33-conflict` | 5, 5, 4 | 3, 3, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-33-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-34-conflict` | 7, 7, 7 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, swearing 3 |
| `pc-34-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-35-conflict` | 3, 4, 5 | 9, 9, 7 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `pc-35-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-36-conflict` | 6, 6, 6 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, cruelty 3, defensiveness 3, stonewalling 3 |
| `pc-36-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-37-conflict` | 5, 5, 5 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-37-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-38-conflict` | 5, 4, 5 | 3, 5, 3 | Yes | Match 3 | contempt 3, criticism 1, defensiveness 3, swearing 3 |
| `pc-38-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-39-conflict` | 2, 3, 3 | 5, 5, 5 | Yes | Match 3 | contempt 3 |
| `pc-39-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-40-conflict` | 6, 6, 6 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-40-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-41-conflict` | 5, 5, 6 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-41-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-42-conflict` | 4, 4, 5 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-42-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-43-conflict` | 5, 5, 4 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `pc-43-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-44-conflict` | 2, 3, 4 | 5, 5, 3 | Yes | Match 3 | defensiveness 3 |
| `pc-44-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-45-conflict` | 5, 5, 6 | 2, 2, 2 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-45-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-46-conflict` | 3, 4, 4 | 9, 7, 5 | Yes | Match 3 | defensiveness 3 |
| `pc-46-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-47-conflict` | 3, 4, 4 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `pc-47-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-48-conflict` | 6, 6, 6 | 2, 2, 2 | Yes | Match 3 | contempt 3, criticism 1, defensiveness 3 |
| `pc-48-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-49-conflict` | 5, 5, 5 | 3, 3, 3 | Yes | Match 3 | defensiveness 3 |
| `pc-49-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-50-conflict` | 4, 4, 4 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, cruelty 3, defensiveness 3 |
| `pc-50-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-51-conflict` | 4, 4, 4 | 8, 8, 8 | Yes | Match 3 | — |
| `pc-51-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-52-conflict` | 6, 5, 6 | 4, 4, 4 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-52-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-53-conflict` | 4, 3, 4 | 3, 3, 3 | Yes | Match 3 | contempt 3 |
| `pc-53-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-54-conflict` | 5, 6, 5 | 2, 2, 2 | Yes | Match 3 | contempt 3 |
| `pc-54-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-55-conflict` | 5, 4, 5 | 2, 2, 2 | Yes | Match 3 | contempt 3, defensiveness 3, stonewalling 3 |
| `pc-55-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-56-conflict` | 5, 5, 5 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-56-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | swearing 3 |
| `pc-57-conflict` | 6, 6, 6 | 2, 2, 2 | Yes | Match 3 | contempt 1, criticism 3, defensiveness 3 |
| `pc-57-nonconflict` | 0, 1, 0 | -, 5, - | No | Match 2, False positive 1 | — |
| `pc-58-conflict` | 2, 2, 2 | 11, 11, 11 | Yes | Match 3 | criticism 3, defensiveness 3 |
| `pc-58-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-59-conflict` | 7, 7, 7 | 2, 2, 2 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `pc-59-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `pc-60-conflict` | 4, 4, 4 | 5, 5, 5 | Yes | Match 3 | defensiveness 3 |
| `pc-60-nonconflict` | 0, 0, 0 | -, -, - | No | Match 3 | — |
