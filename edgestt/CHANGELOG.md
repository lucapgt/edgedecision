# Changelog

## 1.0.1

- Align the add-on version and Wyoming version announcement with EdgeDecision and its integration 1.0.1.
- Update the documented startup log to match. Recognition behavior and the model are unchanged.

## 1.0.0

First public release, published together with EdgeDecision.

- Streaming speech-to-text for Assist with NVIDIA Nemotron 3.5 ASR Streaming 0.6B (INT8, sherpa-onnx 1.13.8)
  over the Wyoming protocol (wyoming 1.10.2).
- Choice of 560 ms (default) or 1120 ms model; the official model is downloaded on first start and kept
  in the add-on data folder.
- Leading silence (300 ms) and a deterministic flush at the end of the audio, so that the first and the
  last word are not dropped.
- Language taken from the Assist pipeline; `language` option as fallback, including `auto`.
- Options `blank_penalty`, `save_audio` (off by default), `log_transcripts`, `model_dir`, `debug`.
- Per-utterance log with audio length, peak level, speech onset and finalization time.
- Wyoming discovery through the Supervisor.
- Log messages and documentation in English.
- Command-line defaults now match the add-on defaults (560 ms model, 300 ms minimum trailing silence).
  With a custom `model_dir` whose name does not contain the block size, the `chunk_ms` option is used.
