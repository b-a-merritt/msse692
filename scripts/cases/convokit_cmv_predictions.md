# ConvoKit CGA-CMV Predictions

Expected outcomes for 74 test threads (37 pairs) from ConvoKit's `conversations-gone-awry-cmv-corpus` (Chang and Danescu-Niculescu-Mizil, 2019, https://convokit.cornell.edu/documentation/awry_cmv.html; also used by Kim et al., 2026).

## Source data

Each thread in the corpus comes from Reddit's `r/changemyview` and stops right before a final comment. In `awry` threads (`has_removed_comment: true`), moderators removed that next comment for breaking Rule 2 (rude or hostile behavior). Each `awry` thread is paired with a `civil` thread (`has_removed_comment: false`) from the same post and of similar length.

These 37 pairs are all the pairs in the `test` split (out of 684) where both threads:

1. Have exactly two speakers.
2. Have no `[deleted]` or `[removed]` comments or usernames.
3. Are at least four turns long, so both people speak at least twice.

## Speakers and scoring

The system only decides whether to intervene when a batch includes new speech from `speaker-2` (the target). Because threads have between 4 and 13 turns, `speaker-2` is set to whoever speaks the last visible turn in the thread, and `speaker-1` is the other speaker. That way every case gets an action decision on its final turn.

`convokit_cmv_expected.json` predicts **Yes** for `awry` threads and **No** for `civil` threads. Because the corpus cuts each `awry` thread off *before* the rule-breaking comment (which `speaker-1` posts in reply to `speaker-2`'s last turn), an `awry` thread does not always contain an overt attack in the visible text. Scoring against `has_removed_comment` tests how often hostility is already clear before the removed reply.

## Predictions

| Case | ConvoKit `conversation_id` | Matched `pair_id` | `has_removed_comment` | Turns | `speaker-2` (turn $N$ target) | `speaker-1` (turn $N-1$ / $N+1$) | Final visible turn ($N$) quote | Intervene |
|---|---|---|---|---:|---|---|---|---|
| `cga-cmv-01-awry` | `cwgol80` | `cwgn3ng` | `True` | 4 | `WJKay` | `Myfootfeelsfunny` | "You are right. This could have been rectified in many other ways. I disagree that it…" | Yes |
| `cga-cmv-01-civil` | `cwgn3ng` | `cwgol80` | `False` | 4 | `WJKay` | `uncle2fire` | "I don't believe he was lifting her by the neck. His left arm is clearly exerting all…" | No |
| `cga-cmv-02-awry` | `cy1fo2m` | `cy1h2dl` | `True` | 11 | `Mavericgamer` | `draculabakula` | "So, basically a percentile chance in the ten thousandths of a percent range either w…" | Yes |
| `cga-cmv-02-civil` | `cy1h2dl` | `cy1fo2m` | `False` | 9 | `ryan_m` | `draculabakula` | "I mean, technically, it could, but it won't. &gt;By the way, I think you are wrong a…" | No |
| `cga-cmv-03-awry` | `cyt0bmb` | `cyt0r72` | `True` | 10 | `arostganomo` | `Yesofcoursenaturally` | "And I've said from the start that that 'evidence' of yours is questionable, and you'…" | Yes |
| `cga-cmv-03-civil` | `cyt0r72` | `cyt0bmb` | `False` | 6 | `KevCon` | `sydbobyd` | "Ethics is defined as "the best way to live", so possibly. If somebody derived pleasu…" | No |
| `cga-cmv-04-awry` | `d0hh23d` | `d0hfh23` | `True` | 7 | `forestfly1234` | `batmansdoctor` | "It is clear that you have no idea what you're talking about. I'm not understanding i…" | Yes |
| `cga-cmv-04-civil` | `d0hfh23` | `d0hh23d` | `False` | 8 | `batmansdoctor` | `Iregularlogic` | "So you're saying we don't know how ion channels open and generate action potentials?…" | No |
| `cga-cmv-05-awry` | `d1aaogd` | `d1abr2u` | `True` | 7 | `LtFred` | `Zmcknight170` | "Japanese immigrants? White South African immigrants? ALL immigrants, including Ameri…" | Yes |
| `cga-cmv-05-civil` | `d1abr2u` | `d1aaogd` | `False` | 6 | `Zmcknight170` | `22254534` | "first, we didnt enter ww2 willingly and two we entered this war like we did in vietn…" | No |
| `cga-cmv-06-awry` | `d2ub01v` | `d2u9rwd` | `True` | 4 | `Celda` | `PanopticPoetics` | "&gt;You are not very inclined to charitable interpretations, are you? I didn't inten…" | Yes |
| `cga-cmv-06-civil` | `d2u9rwd` | `d2ub01v` | `False` | 4 | `matchasmoothie` | `KuulGryphun` | "I mentioned this earlier, but I feel to deny the group official status is the same a…" | No |
| `cga-cmv-07-awry` | `d47ch0c` | `d47dik0` | `True` | 6 | `ProfessorHeartcraft` | `The_Real_Voldermort` | "Attempted, but may have failed. There's an awful lot of blood on your hands if you s…" | Yes |
| `cga-cmv-07-civil` | `d47dik0` | `d47ch0c` | `False` | 6 | `LtPowers` | `chrislstark` | "That's a nice fantasy, and I realize it fits well with gun owners' priorities, but t…" | No |
| `cga-cmv-08-awry` | `d4p8l0j` | `d4pcfoi` | `True` | 5 | `danceparty3000` | `magurney` | "&gt;I think you proved your point there... Am I supposed to know who the "basic Roma…" | Yes |
| `cga-cmv-08-civil` | `d4pcfoi` | `d4p8l0j` | `False` | 4 | `Chewyman11` | `studdbeefpile` | "Firstly, smash bros is an amazing game. You already earned my respect lol Women tryi…" | No |
| `cga-cmv-09-awry` | `d98ln25` | `d99970z` | `True` | 8 | `chiaconan` | `feabney` | "I advocate for any political talk, whether debate or not, whether lively or not... a…" | Yes |
| `cga-cmv-09-civil` | `d99970z` | `d98ln25` | `False` | 8 | `chiaconan` | `GenerationEgomania` | "&gt;there really is a lot more to life (and friendships) than politics alone. I posi…" | No |
| `cga-cmv-10-awry` | `d9pcxkv` | `d9p15w4` | `True` | 11 | `robert3131` | `cleofisrandolph1` | "Wow you really all over the place, once again, IT'S NOT FEAR MONGERING IF IT'S A CRE…" | Yes |
| `cga-cmv-10-civil` | `d9p15w4` | `d9pcxkv` | `False` | 7 | `thetasigma4` | `cleofisrandolph1` | "Yeah nuclear power has become increasingly unpopular since its early days so a lot o…" | No |
| `cga-cmv-11-awry` | `ddj8e6m` | `ddj4vfe` | `True` | 10 | `AloysiusC` | `reginaidiotarum` | "&gt;It sounds sexist. It's because it is. This isn't the narrative of Feminists. It…" | Yes |
| `cga-cmv-11-civil` | `ddj4vfe` | `ddj8e6m` | `False` | 10 | `Kleefish` | `Mitoza` | "Not at all but if youre going to dismantle roles and claim inequality then you have…" | No |
| `cga-cmv-12-awry` | `df7wmr8` | `df7wt3m` | `True` | 5 | `Sheexthro` | `myshieldsforargus` | "&gt;In countries like saudi arabia, there are no rapes, which proves this point. I d…" | Yes |
| `cga-cmv-12-civil` | `df7wt3m` | `df7wmr8` | `False` | 6 | `myshieldsforargus` | `iownakeytar` | "&gt; That wasn't a requirement. it was in the context of the discussion &gt;Yes. Bec…" | No |
| `cga-cmv-13-awry` | `diaoek8` | `dianmk3` | `True` | 8 | `atheist1009` | `azur08` | "&gt;You just have to believe in the "potential" for something to come afterward. I a…" | Yes |
| `cga-cmv-13-civil` | `dianmk3` | `diaoek8` | `False` | 9 | `fadedfigures` | `atheist1009` | "There are plenty of well-reasoned points here that challenge your arguments. You and…" | No |
| `cga-cmv-14-awry` | `dizl80n` | `dizdsk9` | `True` | 6 | `trace349` | `davidildo` | "&gt;I did not imply that jokes against men are offensive to me, I am rather egalitar…" | Yes |
| `cga-cmv-14-civil` | `dizdsk9` | `dizl80n` | `False` | 6 | `Senthe` | `Baby_Fart_McGeezax` | "I mean, "a feminist hurt me" is an explanation why somebody hates feminists. If they…" | No |
| `cga-cmv-15-awry` | `djz34na` | `djz3sl7` | `True` | 5 | `Thoth_the_5th_of_Tho` | `nobodystipe` | "How can you make such broad assements of half the human race when you have no person…" | Yes |
| `cga-cmv-15-civil` | `djz3sl7` | `djz34na` | `False` | 6 | `nobodystipe` | `PreacherJudge` | "&gt; Breast size, body/lip hair are things men less have to worry about. &gt;I am ju…" | No |
| `cga-cmv-16-awry` | `dkl09zr` | `dkla8fo` | `True` | 9 | `Ardonpitt` | `ShivasRightFoot` | "1. Ill take it you know nothing about the decay process of foods, or that landfills…" | Yes |
| `cga-cmv-16-civil` | `dkla8fo` | `dkl09zr` | `False` | 6 | `ShivasRightFoot` | `pillbinge` | "&gt;the world as it is now, just with higher tides and maybe a degree cooler [will]…" | No |
| `cga-cmv-17-awry` | `dkr7277` | `dkr19rw` | `True` | 7 | `_Project2501` | `DeltaT37` | "I understand those in the military are soldiers, while you still see them as employe…" | Yes |
| `cga-cmv-17-civil` | `dkr19rw` | `dkr7277` | `False` | 7 | `Damian4447` | `joalr0` | "Theres about 2000 active trans soldiers according to the article that broke the twit…" | No |
| `cga-cmv-18-awry` | `dnzplo8` | `dnyxen2` | `True` | 5 | `4_jacks` | `CheetosFritosDoritos` | "&gt;It being pointless does not mean it can't be universalized as praxis for conside…" | Yes |
| `cga-cmv-18-civil` | `dnyxen2` | `dnzplo8` | `False` | 4 | `CheetosFritosDoritos` | `cupcakesarethedevil` | "I'm not trying to accomplish anything. It's just a ethical position. It needn't requ…" | No |
| `cga-cmv-19-awry` | `dohntjb` | `dohmaxv` | `True` | 13 | `dickposner` | `FarkCookies` | "&gt;UN has a bias against Israel while nothing demonstrates that they have a bias ag…" | Yes |
| `cga-cmv-19-civil` | `dohmaxv` | `dohntjb` | `False` | 5 | `Valnar` | `x_cLOUDDEAD_x` | "I mean, you can see for yourself what some trump supporters think (I hope its not ag…" | No |
| `cga-cmv-20-awry` | `dqwsyaa` | `dqwtbuh` | `True` | 4 | `IJerkOffToSlutwalks` | `brock_lee` | "I do not see taxes and other laws as something that a business owner “agrees” to. I…" | Yes |
| `cga-cmv-20-civil` | `dqwtbuh` | `dqwsyaa` | `False` | 4 | `IJerkOffToSlutwalks` | `cupcakesarethedevil` | "I’ve explained how it’s slavery in my post. The business owner is being forced to pe…" | No |
| `cga-cmv-21-awry` | `drgo8ee` | `drg5cvn` | `True` | 4 | `thegoldengrekhanate` | `schudermcgavin` | "but I've seen white dudes let "nigga" slip and it usually doesn't end well for them.…" | Yes |
| `cga-cmv-21-civil` | `drg5cvn` | `drgo8ee` | `False` | 4 | `Lardarius115` | `PandaDerZwote` | "Well, for a moment give me the benefit of the doubt that I am, in fact, not looking…" | No |
| `cga-cmv-22-awry` | `dseeort` | `dseg096` | `True` | 6 | `Burflax` | `jbXarXmw` | "&gt;You should brush up on the things I’m telling you about instead of beating aroun…" | Yes |
| `cga-cmv-22-civil` | `dseg096` | `dseeort` | `False` | 7 | `Dinosaur_Boner` | `ericoahu` | "You are absolutely fixated on one poorly chosen example. You'd have a point if I tho…" | No |
| `cga-cmv-23-awry` | `duamit8` | `duab70d` | `True` | 6 | `kevlarballoons` | `billdietrich1` | "Well if you're going to straw man me I'm not going to respond. Have a nice day sir" | Yes |
| `cga-cmv-23-civil` | `duab70d` | `duamit8` | `False` | 6 | `maxout2142` | `Ansuz07` | "Pardon, I thought you were suggesting that the success of the NFA is an indicator th…" | No |
| `cga-cmv-24-awry` | `dusor10` | `duspdis` | `True` | 9 | `tryin2icesk8uphill` | `Exceon` | "Well for one you’re source is one man’s opinion on the situation. A man that was not…" | Yes |
| `cga-cmv-24-civil` | `duspdis` | `dusor10` | `False` | 7 | `jbXarXmw` | `Exceon` | "But then you’d have crossover events happening every two years. I think ultimate inn…" | No |
| `cga-cmv-25-awry` | `dvvjuj3` | `dvvistd` | `True` | 6 | `ChickenBoiOOF` | `Polychrist` | "It’s not that low it’s higher 93-95% because of animal behavior" | Yes |
| `cga-cmv-25-civil` | `dvvistd` | `dvvjuj3` | `False` | 5 | `epicazeroth` | `ChickenBoiOOF` | "Right, but they're using the term incorrectly. You're essentially just arguing that…" | No |
| `cga-cmv-26-awry` | `dydawov` | `dyd7cfv` | `True` | 5 | `PsecretPseudonym` | `JYPark_14` | "A bit, but that’s just not simple conceptually, never mind practically. Like a lot o…" | Yes |
| `cga-cmv-26-civil` | `dyd7cfv` | `dydawov` | `False` | 5 | `nutritionmaster69` | `rigam0rtus` | "I can sympathize with any victims of sexual harrasment and i wouldnt like it either…" | No |
| `cga-cmv-27-awry` | `dyeionp` | `dyegqah` | `True` | 6 | `demoncat1` | `theviqueen` | "Lol and how do I view poor people now do you think? Also I don't think me viewing th…" | Yes |
| `cga-cmv-27-civil` | `dyegqah` | `dyeionp` | `False` | 8 | `demoncat1` | `SurprisedPotato` | "No it does not undermine my point, because the area that is cleared of this crime is…" | No |
| `cga-cmv-28-awry` | `dzfan38` | `dzf9wsi` | `True` | 5 | `Priddee` | `draculabakula` | "&gt; Are you being willfully obtuse or can you really not ~~comprhend~~ comprehend t…" | Yes |
| `cga-cmv-28-civil` | `dzf9wsi` | `dzfan38` | `False` | 5 | `championofobscurity` | `draculabakula` | "Yeah because it's a pittance right now. Nobody would pay a 20 or 30 percent estate t…" | No |
| `cga-cmv-29-awry` | `dzn9q5k` | `dznaqx1` | `True` | 5 | `Thoth_the_5th_of_Tho` | `The_designer12` | "I don't have any sources to link to \(although I'm looking for one\), I was told thi…" | Yes |
| `cga-cmv-29-civil` | `dznaqx1` | `dzn9q5k` | `False` | 4 | `The_designer12` | `RoToR44` | "Actually I.Q would find them equal, because the quantitative reasoning portion is pr…" | No |
| `cga-cmv-30-awry` | `e20r4ir` | `e20mogq` | `True` | 11 | `NearEmu` | `Doctor_Worm` | "What you seem to call kicking and screaming is pretty obviously you not understandin…" | Yes |
| `cga-cmv-30-civil` | `e20mogq` | `e20r4ir` | `False` | 11 | `KaptinBluddflag` | `Doctor_Worm` | "&gt;Claiming asylum isn't a crime even if you don't do it at a point of entry. No it…" | No |
| `cga-cmv-31-awry` | `e2f0a1k` | `e2f6bp7` | `True` | 4 | `NearEmu` | `-Randy-Marsh-` | "Okay, but since we are talking about this so-called 'study'. Maybe you wanna discuss…" | Yes |
| `cga-cmv-31-civil` | `e2f6bp7` | `e2f0a1k` | `False` | 4 | `telemythides` | `MagicGnome97` | "You can easily just keep a sweater at work, I do it. I don't really have a strong op…" | No |
| `cga-cmv-32-awry` | `e2jvd6f` | `e2jv2dl` | `True` | 4 | `waistlinepants` | `DisappointingTaco` | "&gt; Which means nurture is a large factor contributing to intelligence in the early…" | Yes |
| `cga-cmv-32-civil` | `e2jv2dl` | `e2jvd6f` | `False` | 4 | `987654321234567` | `sillybonobo` | "Fair enough but it is an interesting correlation. Would be interesting to set contro…" | No |
| `cga-cmv-33-awry` | `e33fy1i` | `e32szej` | `True` | 4 | `--Aeo--` | `KettleLogic` | "&gt;Market socialism isn't pure socialism but is socialism with borrow elements of c…" | Yes |
| `cga-cmv-33-civil` | `e32szej` | `e33fy1i` | `False` | 4 | `Xais56` | `electronics12345` | "I'd make the argument that expecting an entity to pay 200% of an accrued sum isn't a…" | No |
| `cga-cmv-34-awry` | `e36kw3s` | `e36mc9a` | `True` | 7 | `EternalPropagation` | `IcarusOtaku` | "How does a criminal know they'll be subject to violence for their (mis)behavior?" | Yes |
| `cga-cmv-34-civil` | `e36mc9a` | `e36kw3s` | `False` | 4 | `IcarusOtaku` | `TRossW18` | "Sounds like that's how you were raised. Screaming and demanding is a very dictatorsh…" | No |
| `cga-cmv-35-awry` | `e66svbl` | `e66m3zw` | `True` | 4 | `bitt3n` | `buttface3001` | "'Disaster' and 'invasion' are also good examples. One can describe a sales pitch tha…" | Yes |
| `cga-cmv-35-civil` | `e66m3zw` | `e66svbl` | `False` | 4 | `JoeVacs` | `triples92` | "&gt; If Jews I'm Germany during the world way said mean things to Germans or afircan…" | No |
| `cga-cmv-36-awry` | `e6q8wco` | `e6qg704` | `True` | 4 | `Mariko2000` | `quantumNes` | "If an adult knows who they are and who they want to fuck, then they can consent to f…" | Yes |
| `cga-cmv-36-civil` | `e6qg704` | `e6q8wco` | `False` | 4 | `kju` | `hacksoncode` | "If one claims to have just been laying there you can bet both will claim they were j…" | No |
| `cga-cmv-37-awry` | `e7v7eal` | `e7vxoxz` | `True` | 8 | `barrycl` | `DBDude` | "I am not kidding - couldn't find anything. Please provide evidence to back up your c…" | Yes |
| `cga-cmv-37-civil` | `e7vxoxz` | `e7v7eal` | `False` | 4 | `barrycl` | `Toragi` | "Would you agree that there's a conflict of interest here? If lawyers have to recuse…" | No |

## Results

Three replays of each case with `jev-1.14.0`, prompt `conversation-3`, and no discovered model (`data/eval/convokit-cmv-2026-11-19`), scored by `scripts/evaluate.py`. The number after each behavior is how many of the three replays had a target turn at the 0.7 threshold. Interventions and first turn list the count and first intervention turn from each replay.

- Run 1 matched 46 of 74 (62.2%), Run 2 matched 46 of 74 (62.2%), and Run 3 matched 44 of 74 (59.5%) (136 of 222 runs total, 61.3%).
- Whether a case had an intervention was unchanged across all three runs in 69 of 74 cases (93.2%).
- On the 37 `awry` prefixes, the system intervened in 23, 23, and 22 cases (59.5%-62.2%) and stayed silent in the remaining 14-15 prefixes where the removed attack had not yet happened.
- On the 37 `civil` threads, the system stayed silent in 23, 23, and 22 cases (59.5%-62.2%) and intervened in 14-15 debates where sharp disagreement or sarcasm was flagged as criticism, contempt, or defensiveness despite not breaking Reddit's moderator rule.

| Case | Interventions | First turn | Predicted | Result | Behaviors |
|---|---|---|---|---|---|
| `cga-cmv-01-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | — |
| `cga-cmv-01-civil` | 0, 0, 0 | -, -, - | No | Match 3 | defensiveness 3 |
| `cga-cmv-02-awry` | 1, 0, 0 | 1, -, - | Yes | Match 1, Missed 2 | contempt 3, defensiveness 2 |
| `cga-cmv-02-civil` | 0, 0, 1 | -, -, 5 | No | Match 2, False positive 1 | swearing 3 |
| `cga-cmv-03-awry` | 2, 1, 2 | 8, 10, 8 | Yes | Match 3 | contempt 3 |
| `cga-cmv-03-civil` | 2, 2, 1 | 4, 4, 6 | No | False positive 3 | — |
| `cga-cmv-04-awry` | 3, 3, 3 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-04-civil` | 2, 2, 2 | 6, 6, 6 | No | False positive 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-05-awry` | 3, 3, 3 | 3, 3, 3 | Yes | Match 3 | contempt 3 |
| `cga-cmv-05-civil` | 3, 3, 2 | 2, 2, 4 | No | False positive 3 | defensiveness 3 |
| `cga-cmv-06-awry` | 1, 1, 1 | 4, 4, 4 | Yes | Match 3 | defensiveness 3 |
| `cga-cmv-06-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-07-awry` | 1, 1, 1 | 6, 6, 6 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-07-civil` | 0, 0, 0 | -, -, - | No | Match 3 | contempt 3, swearing 3 |
| `cga-cmv-08-awry` | 1, 1, 1 | 3, 3, 3 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-08-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-09-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | — |
| `cga-cmv-09-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-10-awry` | 1, 1, 1 | 11, 11, 11 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3, swearing 3 |
| `cga-cmv-10-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-11-awry` | 5, 5, 5 | 2, 2, 2 | Yes | Match 3 | contempt 3, criticism 1, defensiveness 3 |
| `cga-cmv-11-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-12-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 1 |
| `cga-cmv-12-civil` | 3, 3, 3 | 2, 2, 2 | No | False positive 3 | contempt 3, defensiveness 3 |
| `cga-cmv-13-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | — |
| `cga-cmv-13-civil` | 3, 3, 3 | 5, 5, 5 | No | False positive 3 | criticism 3, defensiveness 3 |
| `cga-cmv-14-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 3 |
| `cga-cmv-14-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-15-awry` | 1, 1, 1 | 5, 5, 5 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `cga-cmv-15-civil` | 2, 2, 3 | 4, 4, 2 | No | False positive 3 | — |
| `cga-cmv-16-awry` | 3, 2, 3 | 5, 7, 5 | Yes | Match 3 | contempt 3, criticism 3 |
| `cga-cmv-16-civil` | 1, 1, 1 | 6, 6, 6 | No | False positive 3 | contempt 3 |
| `cga-cmv-17-awry` | 4, 3, 4 | 1, 1, 1 | Yes | Match 3 | contempt 3, defensiveness 1, stonewalling 2 |
| `cga-cmv-17-civil` | 3, 3, 3 | 1, 1, 1 | No | False positive 3 | — |
| `cga-cmv-18-awry` | 0, 1, 0 | -, 3, - | Yes | Missed 2, Match 1 | contempt 3, defensiveness 2, swearing 3 |
| `cga-cmv-18-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-19-awry` | 4, 5, 4 | 5, 5, 5 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-19-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-20-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 3, swearing 3 |
| `cga-cmv-20-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-21-awry` | 2, 2, 2 | 2, 2, 2 | Yes | Match 3 | defensiveness 3, swearing 3 |
| `cga-cmv-21-civil` | 0, 0, 0 | -, -, - | No | Match 3 | swearing 1 |
| `cga-cmv-22-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | — |
| `cga-cmv-22-civil` | 3, 3, 2 | 3, 3, 5 | No | False positive 3 | — |
| `cga-cmv-23-awry` | 2, 2, 2 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 3, stonewalling 3, swearing 1 |
| `cga-cmv-23-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-24-awry` | 1, 1, 0 | 7, 7, - | Yes | Match 2, Missed 1 | contempt 3, swearing 3 |
| `cga-cmv-24-civil` | 0, 0, 0 | -, -, - | No | Match 3 | contempt 3 |
| `cga-cmv-25-awry` | 1, 1, 1 | 6, 6, 6 | Yes | Match 3 | — |
| `cga-cmv-25-civil` | 0, 0, 0 | -, -, - | No | Match 3 | contempt 3, defensiveness 2 |
| `cga-cmv-26-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | swearing 3 |
| `cga-cmv-26-civil` | 1, 1, 2 | 3, 3, 3 | No | False positive 3 | defensiveness 3, swearing 3 |
| `cga-cmv-27-awry` | 2, 2, 2 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `cga-cmv-27-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-28-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 3, criticism 2 |
| `cga-cmv-28-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-29-awry` | 1, 2, 1 | 5, 3, 3 | Yes | Match 3 | contempt 3, defensiveness 3 |
| `cga-cmv-29-civil` | 1, 1, 1 | 2, 2, 2 | No | False positive 3 | contempt 3, swearing 3 |
| `cga-cmv-30-awry` | 6, 6, 6 | 1, 1, 1 | Yes | Match 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-30-civil` | 2, 2, 2 | 9, 9, 9 | No | False positive 3 | contempt 3 |
| `cga-cmv-31-awry` | 0, 0, 1 | -, -, 4 | Yes | Missed 2, Match 1 | defensiveness 3 |
| `cga-cmv-31-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-32-awry` | 1, 2, 2 | 2, 2, 2 | Yes | Match 3 | contempt 3 |
| `cga-cmv-32-civil` | 2, 2, 2 | 2, 2, 2 | No | False positive 3 | contempt 3, swearing 3 |
| `cga-cmv-33-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | — |
| `cga-cmv-33-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-34-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 3 |
| `cga-cmv-34-civil` | 1, 1, 1 | 4, 4, 4 | No | False positive 3 | contempt 3, criticism 3, defensiveness 3 |
| `cga-cmv-35-awry` | 1, 1, 1 | 4, 4, 4 | Yes | Match 3 | contempt 3, defensiveness 1 |
| `cga-cmv-35-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
| `cga-cmv-36-awry` | 2, 2, 2 | 2, 2, 2 | Yes | Match 3 | contempt 3, defensiveness 1, swearing 3 |
| `cga-cmv-36-civil` | 0, 0, 0 | -, -, - | No | Match 3 | contempt 3, defensiveness 2 |
| `cga-cmv-37-awry` | 0, 0, 0 | -, -, - | Yes | Missed 3 | contempt 3 |
| `cga-cmv-37-civil` | 0, 0, 0 | -, -, - | No | Match 3 | — |
