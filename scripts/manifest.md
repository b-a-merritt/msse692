# Case Manifest

| Case file | Film | Scene | YouTube title | Source URL |
|---|---|---|---|---|
| `cases/case-1.jsonl` | Revolutionary Road (2008) | "I Love My Children, Frank" (clip 4/8) | Revolutionary Road (4/8) Movie CLIP - I Love My Children, Frank (2008) HD | https://www.youtube.com/watch?v=m_7Bm1gyq2c |
| `cases/case-2.jsonl` | Marriage Story (2019) | Argument between Nicole (Scarlett Johansson) and Charlie (Adam Driver) | Scarlett Johansson and Adam Driver in Marriage Story l Netflix | https://www.youtube.com/watch?v=FDFdroN7d0w&t=2s |
| `cases/case-3.jsonl` | The Social Network (2010) | Opening bar breakup between Erica (Rooney Mara, `speaker-1`) and Mark (Jesse Eisenberg, `speaker-2`) | The Social Network (2010) - You're Breaking Up With Me? Scene (1/10) \| Movieclips | https://www.youtube.com/watch?v=VlSkPA60ujQ |
| `cases/case-4.jsonl` | Before Midnight (2013) | Hotel-room fight between Celine (Julie Delpy, `speaker-1`) and Jesse (Ethan Hawke, `speaker-2`) | Before Midnight 2013 Celine Argument Scene | https://www.youtube.com/watch?v=aaqDa2UJ_kM |
| `cases/case-5.jsonl` | Who's Afraid of Virginia Woolf? (1966) | George plays "Get the Guests" with Martha (Elizabeth Taylor, `speaker-1`), George (Richard Burton, `speaker-2`), Nick (George Segal, `speaker-3`) and Honey (Sandy Dennis, `speaker-4`) | Who's Afraid of Virginia Woolf  George plays "get the guests" | https://www.youtube.com/watch?v=p59MMlPae3U |
| `cases/case-6.jsonl` | Fences (2016) | Rose's "same spot" speech between Troy (Denzel Washington, `speaker-1`) and Rose (Viola Davis, `speaker-2`) | Fences (2016) - The Same Spot As You Scene (5/10) \| Movieclips | https://www.youtube.com/watch?v=2hs-yt-Pmk0 |
| `cases/case-7.jsonl` | Kramer vs. Kramer (1979) | Restaurant custody scene between Joanna (Meryl Streep, `speaker-1`) and Ted (Dustin Hoffman, `speaker-2`) | Kramer vs. Kramer (4/8) Movie CLIP - I Want My Son (1979) HD | https://www.youtube.com/watch?v=M_ejjr2-4WE |
| `cases/case-8.jsonl` | Breaking Bad (S4E6) | "I am the one who knocks" between Skyler (Anna Gunn, `speaker-1`) and Walt (Bryan Cranston, `speaker-2`) | Breaking Bad - I Am the One Who Knocks Scene (S4E6) \| Rotten Tomatoes TV | https://www.youtube.com/watch?v=Ca3kPemW2CE |
| `cases/case-9.jsonl` | Phantom Thread (2017) | Asparagus dinner between Alma (Vicky Krieps, `speaker-1`) and Reynolds (Daniel Day-Lewis, `speaker-2`) | The Asparagus Fight \| Phantom Thread | https://www.youtube.com/watch?v=Q3KBAOoLh0k |
| `cases/case-10.jsonl` | The Break-Up (2006) | Dishes argument between Brooke (Jennifer Aniston, `speaker-1`) and Gary (Vince Vaughn, `speaker-2`) | I Want You to WANT to do the Dishes - The Break-Up \| RomComs | https://www.youtube.com/watch?v=xj7sYdMEKec |
| `cases/case-11.jsonl` | Good Will Hunting (1997) | Park bench scene between Will (Matt Damon, `speaker-1`) and Sean (Robin Williams, `speaker-2`) | [Great Movie Scenes] Good Will Hunting - Park Scene | https://www.youtube.com/watch?v=qM-gZintWDc |
| `cases/case-12.jsonl` | Forrest Gump (1994) | Forrest (Tom Hanks, `speaker-1`) meets his son at Jenny's (Robin Wright, `speaker-2`) apartment, with little Forrest (Haley Joel Osment, `speaker-3`) and Jenny's coworker (`speaker-4`) | Forrest Gump: Named after his dad (HD CLIP) | https://www.youtube.com/watch?v=ITGEGE9v0d0 |

## Expected outcomes

The assessed speaker is `speaker-2`.

- **case-3:** There should be no interventions for mark because he says "I'm sorry." He seems incapable of realizing how he offended her, but realizes he said something he shouldn't have.
- **case-4:** Jesse uses some high intensity and bad language. I expect at least one or two interventions.
- **case-5:** If there are any interventions, it should only be for high intensity (loud) argumentation.
- **case-6:** Rose uses quite a few uncondintional phrases ("You always") as well as some shouting. There will likely be 2 interventions.
- **case-7:** They speak over one another, but not for long. I don't think there are any interventions because the one violent act is nonverbal.
- **case-8:** I expect no interventions for Walt. His threat uses no listed phrase or work and he never raises his voice. This is likely a false negative.
- **case-9:** There is a lot of crude langauge as well as a lot of interruption. I expect a least two interventions.
- **case-10:** I expect Gary to get interventions for interrupting and calling Brooke "Crazy." Her "You're a prick" would be recognized if she was the subject. (There should be no intervention or assessment of her).
- **case-11:** Sean likely gets an intervention for swearing, but should not be getting one for saying "You're a tough kid."
- **case-12:** This is a normal conversation. There should be no interventions for either.

## Stress case

`cases/stress.jsonl` is synthetic. It interleaves 330 scripted sessions (`stress-p<phase>-<nnn>`,
`speaker-1` and subject `speaker-2`) so that replaying recorded gaps steps the load up. A 30 s
quiet gap after each phase lets the backlog drain, so each step can be measured on its own. _It was AI-generated._


| Phase | Sessions | Rows | Offered rate |
|---|---|---|---|
| p1 | 10 | 302 | 3.7 obs/s |
| p2 | 20 | 604 | 7.2 obs/s |
| p3 | 30 | 906 | 10.6 obs/s |
| p4 | 60 | 1812 | 20.9 obs/s |
| p5 | 90 | 2718 | 31.6 obs/s |
| p6 | 120 | 3624 | 40.9 obs/s |

The whole run takes ~11.5 minutes. `send_observations.py` sleeps for the full gap and then
waits for the response, so the achieved rate falls short of the offered rate at high load. Measure
the achieved rate from `observation.committed` timestamps.

Sessions cycle through ten scenarios by session number, so every phase includes each one. Phase 1
was checked against the server and matched every row below. If a higher phase differs, the
deviation comes from load.

| Session `nnn` ends in | Scenario | Expected outcome |
|---|---|---|
| 1 | Calm conversation | No assessments |
| 2 | Character label, apology about 6 s later | Repaired, no intervention |
| 3 | Vulgar term, no repair | Expires, one intervention |
| 4 | Absolutist phrase, agreement about 12 s later | Repaired, no intervention |
| 5 | Harm phrase | One intervention, immediately |
| 6 | Loud, fast chunk | Expires, one intervention |
| 7 | Two interruptions | Expires, one intervention |
| 8 | Monologue longer than 30 s | Expires, one intervention |
| 9 | `speaker-1` uses absolutist, label, vulgar, and harm phrases | No assessments |
| 0 | Absolutist phrase repaired by an intent disclaimer, then a label with an apology about 24 s later | First repaired, second expires, one intervention |

Each phase should create 6 interventions per 10 sessions, or 198 in total.
