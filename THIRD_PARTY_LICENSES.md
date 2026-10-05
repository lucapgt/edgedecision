# Third-party components and licences

EdgeDecision ships one neural model (`bundles/6L/model.int8.onnx`, variant `e5s-6L`). Its weights are **derived from
multilingual-e5-small**; everything else listed below was used only on the training PC and is **not distributed**.

## 1. Distributed with EdgeDecision

### multilingual-e5-small (base of the EdgeDecision model)

- Source: https://huggingface.co/intfloat/multilingual-e5-small (Wang et al., "Multilingual E5 Text Embeddings", 2024)
- Licence: **MIT**
- What we did: kept 6 of its 12 transformer layers, reduced the vocabulary from 250 002 to 33 060 pieces,
  added decision heads (candidate score, request type, word tags, 256-d retrieval vector), trained it by
  distillation on synthetic home-automation data, exported it to ONNX and quantised it to INT8.
  The MIT licence permits modification and redistribution; the notice below must accompany every copy.

```
MIT License

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Runtime libraries (installed by pip in the add-on image, not bundled in this repository)

onnxruntime (MIT), tokenizers (Apache-2.0), numpy (BSD-3-Clause), requests (Apache-2.0),
websocket-client (Apache-2.0), PyYAML (MIT), num2words (LGPL-2.1, used unmodified as a library).

## 2. Used only for training (not distributed)

| Component | Role | Licence |
|---|---|---|
| BAAI/bge-reranker-v2-m3 | teacher model: its scores are the distillation targets; fine-tuned on our data, never shipped | Apache-2.0 |
| Qwen2.5-14B-Instruct (via Ollama) | paraphrases and out-of-domain sentences of the synthetic training set | Apache-2.0 (no restriction on outputs) |
| Whisper *small* (faster-whisper) | transcribes synthetic speech to reproduce speech-recognition errors | MIT |
| Piper TTS | reads training sentences aloud before transcription | MIT (engine); voices: see below |

### Piper voices used for the speech round trip

The audio was generated on the training PC, used only to obtain transcriptions (text) and then discarded. No audio and
no voice model is part of EdgeDecision, and the model itself reads text and outputs decisions: it never produces speech.
EdgeDecision is distributed for non-commercial use only. Information below as stated on each voice's MODEL_CARD
(huggingface.co/rhasspy/piper-voices) and on the linked dataset pages, checked on 2026-09-29 and 2026-10-03:

| Language | Voice | Dataset and licence | Base |
|---|---|---|---|
| it | it_IT paola (medium) | paolapersico1/Voice-Dataset-Italian, CC0 | fine-tuned from en_US lessac |
| it | it_IT riccardo (x_low) | M-AILABS speech dataset, M-AILABS licence (BSD-3-Clause style) | trained from scratch |
| en | en_US lessac (medium) | Lessac Technologies data for Blizzard 2013, research purposes only, no commercial use | trained from scratch |
| en | en_GB alan (medium) | Alan Pope recordings (Mimic 3 voice apope), no licence stated | fine-tuned from en_US lessac |
| es | es_ES davefx (medium) | CC0 | fine-tuned from en_US lessac |
| es | es_ES sharvard (medium) | University of Edinburgh, CC BY 3.0 | fine-tuned from en_US lessac |
| fr | fr_FR siwis (medium) | SIWIS database, CC BY 4.0 | fine-tuned from en_US lessac |
| fr | fr_FR tom (medium) | AGPL-3.0 (only its outputs were used) | see MODEL_CARD |
| de | de_DE thorsten (medium) | Thorsten-Voice, CC0 | fine-tuned from en_US lessac |
| de | de_DE mls (medium) | Multilingual LibriSpeech (openslr.org/94), CC BY 4.0 | see MODEL_CARD |
| nl | nl_NL pim (medium) | CC0 | fine-tuned from en_US lessac |
| nl | nl_BE nathalie (medium) | CC0 | fine-tuned from en_US lessac |
| pt | pt_BR faber (medium) | CC0 | fine-tuned from en_US lessac |
| pt | pt_PT tugão (medium) | CC0 | fine-tuned from en_US lessac |
| pl | pl_PL darkman (medium) | CC0 | fine-tuned from en_US lessac |
| pl | pl_PL gosia (medium) | CC0 | fine-tuned from en_US lessac |
| sv | sv_SE nst (medium) | NST Swedish database (Språkbanken), CC0 | trained from scratch (KBLab) |
| sv | sv_SE lisa (medium) | no MODEL_CARD and no licence stated in the repository; published there for use | unknown |

Note on Lessac: the Blizzard 2013 licence allows use "exclusively for Research Purposes" and excludes any commercial
use, including voice synthesis or speech recognition products; it also forbids passing the data itself to third
parties. Voices fine-tuned from lessac may inherit these terms. EdgeDecision uses them only indirectly (synthetic audio
-> transcription -> text), distributes none of them and forbids commercial use.

This file is a record of what was used, not legal advice.
