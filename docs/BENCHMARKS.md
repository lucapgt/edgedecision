# Benchmarks

EdgeDecision 1.0 (model 7c, add-on 0.8.3 software) compared with the **default conversation agent of Home
Assistant**, on the same homes and the same sentences, with the same scoring.

## How it was measured

- **Sentences**: 846 hand-written sentences in 9 languages, never used for training (three sets: *gold*, 227
  sentences in Italian / English / Spanish; *homes*, a test home translated into 7 languages, 404 sentences; *r7*,
  questions on rooms and the whole house, timers, new devices, 215 sentences). About a quarter of them ask for
  something that must **not** be executed (out of domain, unsupported, unclear, high risk).
- **Home Assistant**: the templates of the official `home-assistant-intents` project (2026.9.30), recognised by
  `hassil` 3.12, filled with the names of the devices, rooms and floors of the same homes; a recognised intent is
  resolved to a target as Home Assistant does (a device name → that device; a room and a kind → the devices of that
  kind in the room; a kind alone → the room of the microphone, else the whole house). Delayed commands ("turn off the
  light in ten minutes") count as correct, because Home Assistant runs them with a timer.
- **Scoring**: a command is correct when the right action runs on the right device; a sentence that must not run is
  correct when nothing runs. A *wrong execution* is an action run on the wrong device or the wrong action.

## Results

| set | Home Assistant default agent | EdgeDecision |
|---|---|---|
| gold (227) | 98 correct (43%) | **214 correct (94%)** |
| homes, 9 languages (404) | 188 correct (47%) | **385 correct (95%)** |
| r7 (215) | 84 correct (39%) | **206 correct (96%)** |
| commands run right | 198 / 659 (30%) | **622 / 659 (94%)** |
| wrong executions | 0 | **0** |
| high-risk actions (unlock, open the garage) run without asking | 15 | **0** (always confirmed) |

Only the sentences written in the same language as the names of the home (Home Assistant matches names and rooms
exactly as they are written, so a sentence in another language is at a disadvantage):

| set | Home Assistant | EdgeDecision |
|---|---|---|
| gold | 58 / 106 | 102 / 106 |
| homes | 178 / 364 | 355 / 364 |
| r7 | 73 / 196 | 187 / 196 |

Where the templates stop: a small change in wording ("spegni l'abat-jour **di** Paolo" for a device called
"Abat-jour Paolo", "abbassa **un po'** la luce", "prossima canzone", "è buio qui", "could you turn the living room
lamp on please") matches no template. Home Assistant never runs the wrong device: when it does not understand, it does
nothing.

## Speed

| | Home Assistant default agent | EdgeDecision |
|---|---|---|
| decision time, desktop CPU (2 threads) | 2–12 ms when a template matches | ~120 ms |

### The whole chain on a Raspberry Pi 5

Measured on the author's Raspberry Pi 5 (16 GB) running Home Assistant OS, with a Voice PE satellite, EdgeSTT 0.2.2
(Nemotron 3.5 ASR Streaming 0.6B, 560 ms blocks, 4 threads) and EdgeDecision 0.8.3 (model 7c, 4 threads) both
active: one session of 50 spoken Italian commands, 4 October 2026.

| step | median | 90% of commands under |
|---|---|---|
| EdgeSTT: end of speech → text (finalisation) | 276 ms | 519 ms |
| EdgeDecision: text → decision | 203 ms | 510 ms |
| **end of speech → decision** (sum of the medians) | **≈ 0.48 s** | — |

The finalisation of EdgeSTT has two values, about 250 ms or about 510 ms, depending on whether one or two 560 ms
blocks remain when you stop talking: the rest of the sentence was already transcribed while you were speaking.

| resources on the Pi 5 | EdgeSTT | EdgeDecision |
|---|---|---|
| memory | 1.40 GB | 0.32 GB |
| average CPU between two readings 12 minutes apart (second half of the session and after it) | 0.22 of 4 cores | 0.06 of 4 cores |

In the same session 5 of the 50 recordings came out of the speech recogniser empty (nothing was executed), and
several contained recognition errors ("Spende la luce" for "spegni la luce", "Impas on tainer di due minuti" for
"imposta un timer di due minuti"). Of the 49 decisions, 32 were executions, 13 questions back to the user, 3
replies without an action ("Grazie", "what did I just ask?") and 1 request passed on to the other agent.

## Not reproduced

- the "fuzzy matching" fallback of recent Home Assistant releases, custom sentences and LLM agents;
- a local LLM on the Raspberry Pi 5 (planned for a later release).

The test sentences are not published; the counts above and the method are, so that the comparison can be repeated
on any set of sentences.
