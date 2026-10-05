# EdgeDecision

Local decision engine for Assist: it receives a sentence ("abbassa un po' la luce"), compares it with the actions of
your home and decides whether to execute, ask, refuse, or pass the request to another agent. 9 languages, one model,
fast enough for a Raspberry Pi 5.

## Setup

1. Start the add-on once in `demo` mode if you want to try it safely (a built-in test home with 41 devices; nothing
   in your house is controlled).
2. Set **mode** to `homeassistant` and restart: the add-on reads the entities exposed to Assist, their rooms, floors
   and aliases. New, renamed or moved devices are picked up within a minute.
3. Install the **EdgeDecision integration** (HACS, same repository) and choose *EdgeDecision* as the conversation agent
   of your Assist pipeline. Pick a fallback agent in the integration options (e.g. *Home Assistant*): it receives the
   requests EdgeDecision passes on (chit-chat, complex conditions, questions about the world).

## Options

| option | meaning |
|---|---|
| `mode` | `demo` (built-in test home) or `homeassistant` (your entities) |
| `model` | the model to load |
| `threads` | CPU threads for the model (Raspberry Pi 5: 4) |
| `lang` | default language of the replies (Assist sends the language of each pipeline) |
| `expose_all` | also use entities not exposed to Assist |
| `allow_off_all` | let "turn everything off" really switch off the house (off by default: a misheard sentence must not darken it) |
| `save_history` | write every decision to `/share/edgedecision/history.jsonl` (off by default: these are sentences said at home) |

## Languages

Italian, English, Spanish, French, German, Dutch, Portuguese, Polish, Swedish. Create one Assist pipeline per
language (speech-to-text, EdgeDecision, text-to-speech in that language); the add-on is the same for all of them.
Device names can stay in your language: "turn on the cucina light" and "turn on the kitchen light" both work.

## Music

Music by name ("metti radio deejay", "play some jazz in the kitchen") needs Music Assistant players exposed to Assist.
Music goes to the player of the satellite that heard the sentence: the ESPHome player of a Voice PE and its Music
Assistant twin are recognised as the same speaker.

## Timers and alarms

Timers, alarms ("wake me up at 7") and announcements run on the voice satellite that heard the sentence, through the
integration.

## API (port 8765)

- `POST /decide` `{"text": "accendi la tv", "context_area": "salone", "session": "satellite1", "execute": false}`
- `GET /health`, `GET /info`, `GET /history` (last 50 decisions), `GET /states`, `POST /reload`

The port is **not published** by default: the integration talks to the add-on inside Home Assistant's network. If you
publish it (Network section of the add-on) to test from another computer, remember that with `"execute": true`
anyone on your network who reaches it can control the exposed devices.

## Licence

Code: PolyForm Noncommercial 1.0.0. Model and documentation: CC BY-NC 4.0. Non-commercial use only. The model is
derived from intfloat/multilingual-e5-small (MIT). Details: `LICENSE`, `LICENSE-MODEL`, `THIRD_PARTY_LICENSES.md` in
the repository.
