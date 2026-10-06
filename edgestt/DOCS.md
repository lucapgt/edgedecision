# EdgeSTT

Local, streaming speech-to-text for Home Assistant Assist.

EdgeSTT runs **NVIDIA Nemotron 3.5 ASR Streaming 0.6B** (INT8 ONNX export by
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)) on your Home Assistant machine and exposes it to
Assist through the **Wyoming** protocol. It was built for the Raspberry Pi 5 and is part of the chain
Voice PE → EdgeSTT → EdgeDecision → Piper, where everything runs locally.

- **Streaming:** the audio is recognized block by block *while you speak*. When you stop, only the
  last block or two remain to be processed.
- **Local:** no cloud service. The model is downloaded once, on first start.
- **Languages exposed to Home Assistant:** Italian, English, Spanish, French, German, Dutch, Portuguese,
  Polish, Swedish. NVIDIA classifies Polish and Swedish as "broad-coverage" languages, with lower
  accuracy than the others (see the [model card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)).
- **Robust start and end of speech:** the server adds silence before the audio and flushes the model
  at the end. This way the first and the last word are not dropped, and short answers are less likely
  to come back empty.

## Requirements

- A 64-bit system: `aarch64` (e.g. Raspberry Pi 5 with Home Assistant OS) or `amd64`.
- Internet access on first start only, to download the model from the sherpa-onnx releases on GitHub.
  The archive is about 475 MB; it is kept in the add-on data folder and reused after restarts and
  updates.
- Disk: about 680 MB for the extracted model, plus the add-on image. During the first extraction the
  archive and the extracted files exist at the same time.
- Memory: in our tests on an x86 machine the recognizer process used about 1 GB of RAM. Memory use on
  the Raspberry Pi has not been measured yet.

## Installation

1. In Home Assistant open **Settings → Add-ons → Add-on Store**, then menu **⋮ → Repositories**.
   Add `https://github.com/Lucapgt/edgedecision` and close the dialog.
2. Find **EdgeSTT** in the store, click **Install**, then **Start**. The first build takes a few minutes.
3. Open the **Log** tab. On first start you will see the model download. Wait for
   `Listening on tcp://0.0.0.0:10300`.
4. Go to **Settings → Devices & services**. Home Assistant normally discovers **Wyoming Protocol**
   automatically: click **Configure**. If it is not discovered, choose **Add integration → Wyoming
   Protocol**, with the host of your Home Assistant machine and port `10300`.
5. Go to **Settings → Voice assistants**, open your pipeline and choose **EdgeSTT** as the
   speech-to-text engine. Select the language you speak.

## Options

| Option | Default | Description |
|---|---|---|
| `chunk_ms` | `560` | Model variant: 560 ms or 1120 ms blocks. 1120 ms needs less CPU |
| `language` | `it` | Used **only** if Home Assistant does not send a language. Normally the pipeline language is used. `auto` = automatic language detection |
| `threads` | `4` | CPU threads used for recognition (1–4) |
| `lead_padding_ms` | `300` | Silence added before the audio |
| `tail_padding_ms` | `300` | Minimum silence added after the audio. The server adds more automatically until the last word has been processed |
| `model_dir` | empty | Path to another sherpa-onnx export of the same model (for example under `/share`). Leave empty to use the official model |
| `log_transcripts` | `true` | Write the recognized text to the log. When off, only its length is written |
| `save_audio` | `false` | Save every request as WAV + JSON in `/share/edgestt/recordings` |
| `blank_penalty` | `0` | Values around 0.5–2 make empty results for very short answers less likely, at the cost of occasional extra words |
| `debug` | `false` | Verbose log |

## Recommendations

- **Language:** set the language of the Assist pipeline to the language you actually speak. The model
  is told which language to expect. Speaking another language gives poor or even empty results: in our
  test, a French sentence sent with Italian selected came back empty. If you use more than one
  language, create one pipeline per language.
- **`chunk_ms`:** start with `560`. In our tests on synthetic Italian commands, 560 and 1120 ms gave
  similar accuracy. In our measurements 1120 ms needed roughly 40% less computation, which is useful if the CPU is busy with
  other add-ons.
- **`blank_penalty`:** leave it at `0`. If one-word answers ("yes", a room name) often come back empty,
  try `1`. In our tests on synthetic Italian commands this reduced empty results from 4.7% to 2.0% of
  utterances, while the word error rate rose slightly (from 30.9% to 32.5%; that test set is
  synthetic speech and not representative of real voices).
- **Wake sound on the Voice PE:** if the first words are lost when you start speaking right after the
  wake word, turn off the wake sound in the Voice PE settings. The sound overlaps the start of your
  speech.

## Log

At start-up:

```
EdgeSTT 1.0.1: model nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11 (0.56 s blocks), leading silence 300 ms / minimum trailing silence 300 ms, default language it, blank_penalty 0.0
Listening on tcp://0.0.0.0:10300
```

For every utterance (format; the values depend on your audio and hardware):

```
[it-IT] <seconds> s audio (peak <level> dBFS, speech from <N> ms), finalization <N> ms: 'Spegni la TV'
```

- **audio:** length of the audio received from Home Assistant.
- **peak:** loudest level. Below −30 dBFS the log suggests enabling auto gain on the satellite.
- **speech from N ms:** where speech starts in the received audio. If it is 0 and the audio is loud
  from the first instant, the log warns that the start was probably cut before reaching EdgeSTT, for
  example by the wake word or the wake sound.
- **finalization:** time from the end of the audio to the transcript, i.e. the speech-to-text delay
  you notice after you stop speaking. It depends on your hardware and on what else is running.

## Privacy

- Everything runs locally. After the one-time model download, EdgeSTT makes no network requests
  except to the Home Assistant Supervisor, for discovery.
- `save_audio` is **off** by default. When enabled, every request is stored as a WAV file with its
  transcript in `/share/edgestt/recordings`, which is readable by other add-ons with access to
  `/share`. Enable it only temporarily, for troubleshooting, and delete the recordings afterwards.
- With `log_transcripts` on, what you say appears in the add-on log. Turn it off if you do not want
  that.

## Known limitations

- **Very short answers** (one word, such as a room name in a follow-up question) sometimes come back
  empty. See `blank_penalty` above.
- **Numbers** may be written as digits or as words ("19 minutes" or "nineteen minutes"), and compound
  numbers are sometimes split. The text contains capital letters and punctuation. The conversation
  agent must accept all of these forms.
- **`auto` language detection** is less reliable than a fixed language, especially on very short
  utterances. The detected language is not reported back. Since Home Assistant normally sends the
  pipeline language, the `language` option rarely applies.
- **No custom vocabulary:** sherpa-onnx supports neither hotwords nor beam search for this model.
- **One request at a time:** a single model instance is shared, so when several satellites speak at
  once their requests are queued.
- **No fine-tuning yet:** this release uses the original NVIDIA model, not a version adapted to home-automation commands.

## Licenses

- EdgeSTT code: see the license of the repository.
- The model is **not** part of this repository. It is downloaded on first start from the sherpa-onnx
  releases and remains under its own license, **OpenMDW-1.1** (© NVIDIA). See `NOTICE` and
  `LICENSE-OpenMDW-1.1.txt`.
- Runtime: sherpa-onnx (Apache-2.0), wyoming (MIT), numpy (BSD-3-Clause).
