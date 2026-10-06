"""EdgeSTT - Wyoming speech-to-text server for NVIDIA Nemotron 3.5 ASR Streaming (sherpa-onnx).

  - streaming: audio is decoded block by block while the user speaks
  - leading silence at audio-start and a deterministic flush at audio-stop, so that the first
    and the last word are not lost and short answers do not come back empty
  - 560 ms or 1120 ms model (or a custom export of the same model) chosen in the options
  - the official model is downloaded on first start
  - per-utterance log: audio length, level, speech onset, finalization time, transcript

Command line (outside Home Assistant):
  python edgestt_server.py --model-dir /path/to/model --uri tcp://0.0.0.0:10300
Inside the add-on the options are read from /data/options.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import tarfile
import time
import urllib.request
import wave
from datetime import datetime
from functools import partial
from pathlib import Path

import numpy as np
import sherpa_onnx
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer

VERSION = "1.0.1"
SAMPLE_RATE = 16000
RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
OFFICIAL = {
    560: "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11",
    1120: "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-1120ms-int8-2026-06-11",
}
LANGUAGES = ["it", "en", "es", "fr", "de", "nl", "pt", "pl", "sv"]
LOCALE = {
    "it": "it-IT", "en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
    "nl": "nl-NL", "pt": "pt-PT", "pl": "pl-PL", "sv": "sv-SE",
}

# Defaults: identical to the add-on options in config.yaml
DEFAULT_CHUNK_MS = 560
DEFAULT_THREADS = 4
DEFAULT_LEAD_MS = 300
DEFAULT_TAIL_MS = 300
DEFAULT_LANGUAGE = "it"

_LOGGER = logging.getLogger("edgestt")
FLUSH_MARGIN_S = 0.3  # speech to cover beyond the end of the received audio
WINDOW_EXTRA_S = 0.1  # right context: a block is ready after block length + ~90 ms of audio


# -------------------------------------------------------------------- model
def ensure_model(chunk_ms: int, models_root: Path) -> Path:
    """Download and extract the official model if it is not there yet."""
    name = OFFICIAL[chunk_ms]
    target = models_root / name
    if (target / "tokens.txt").exists():
        return target
    models_root.mkdir(parents=True, exist_ok=True)
    archive = models_root / f"{name}.tar.bz2"
    _LOGGER.info("Downloading %s (about 450 MB, first start only)...", name)
    tmp = archive.with_suffix(".part")
    urllib.request.urlretrieve(RELEASE + name + ".tar.bz2", tmp)
    tmp.rename(archive)
    _LOGGER.info("Extracting...")
    with tarfile.open(archive, "r:bz2") as t:
        t.extractall(models_root)
    archive.unlink()
    return target


def find_files(model_dir: Path) -> dict[str, str]:
    def pick(prefix: str) -> str:
        cands = sorted(model_dir.glob(f"{prefix}*.onnx"))
        if not cands:
            raise FileNotFoundError(f"{prefix}*.onnx not found in {model_dir}")
        int8 = [c for c in cands if "int8" in c.name]
        return str((int8 or cands)[0])
    return {"encoder": pick("encoder"), "decoder": pick("decoder"), "joiner": pick("joiner"),
            "tokens": str(model_dir / "tokens.txt")}


def load_recognizer(model_dir: Path, threads: int, blank_penalty: float = 0.0) -> sherpa_onnx.OnlineRecognizer:
    f = find_files(model_dir)
    _LOGGER.info("Loading %s (%d threads)", model_dir.name, threads)
    t0 = time.perf_counter()
    rec = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=f["tokens"], encoder=f["encoder"], decoder=f["decoder"], joiner=f["joiner"],
        num_threads=threads, sample_rate=SAMPLE_RATE, feature_dim=128,
        decoding_method="greedy_search", provider="cpu", blank_penalty=blank_penalty,
    )
    _LOGGER.info("Model ready in %.1f s", time.perf_counter() - t0)
    return rec


def model_language(language: str | None, default: str) -> str:
    lang = (language or default or DEFAULT_LANGUAGE).strip()
    if lang.lower() == "auto":
        return "auto"
    base = lang.split("-")[0].split("_")[0].lower()
    if "-" in lang or "_" in lang:
        region = lang.replace("_", "-").split("-")[1].upper()
        return f"{base}-{region}"
    return LOCALE.get(base, base)


# ------------------------------------------------------------------- server
class Settings:
    def __init__(self, recognizer, lead_s: float, tail_s: float, default_lang: str,
                 log_transcripts: bool, model_name: str, save_dir: Path | None = None,
                 chunk_s: float = DEFAULT_CHUNK_MS / 1000):
        self.recognizer = recognizer
        self.lead = np.zeros(int(round(lead_s * SAMPLE_RATE)), np.float32)
        self.tail = np.zeros(int(round(tail_s * SAMPLE_RATE)), np.float32)
        self.default_lang = default_lang
        self.log_transcripts = log_transcripts
        self.model_name = model_name
        self.save_dir = save_dir
        # sherpa-onnx only processes complete encoder blocks: audio after the last complete
        # block is dropped at input_finished(). The flush needs the block length.
        self.chunk_s = chunk_s
        self.lead_s = lead_s
        # one shared model: decodes are serialized
        self.lock = asyncio.Lock()


def make_info(model_name: str) -> Info:
    return Info(asr=[AsrProgram(
        name="edgestt",
        description="EdgeSTT - Nemotron 3.5 ASR Streaming",
        attribution=Attribution(name="NVIDIA / k2-fsa sherpa-onnx", url="https://github.com/k2-fsa/sherpa-onnx"),
        installed=True,
        version=VERSION,
        models=[AsrModel(
            name=model_name,
            description="Nemotron 3.5 ASR Streaming 0.6B INT8",
            attribution=Attribution(name="NVIDIA", url="https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b"),
            installed=True,
            version=VERSION,
            languages=LANGUAGES,
        )],
    )])


def audio_stats(pcm: np.ndarray) -> dict:
    """Level and speech onset: helps to tell whether the audio arrived already cut."""
    if len(pcm) == 0:
        return {"peak_dbfs": -120.0, "onset_ms": None, "rms_first_100ms_dbfs": -120.0}
    x = pcm.astype(np.float32) / 32768.0
    peak = float(np.abs(x).max())
    frame = SAMPLE_RATE // 100  # 10 ms
    n = len(x) // frame
    rms = np.sqrt((x[: n * frame].reshape(n, frame) ** 2).mean(axis=1) + 1e-12) if n else np.array([1e-6])
    noise = float(np.percentile(rms, 10))
    thr = max(noise * 4, 10 ** (-45 / 20))
    above = np.nonzero(rms > thr)[0]
    first = x[: SAMPLE_RATE // 10]
    return {
        "peak_dbfs": 20 * np.log10(max(peak, 1e-6)),
        "onset_ms": int(above[0] * 10) if len(above) else None,
        "rms_first_100ms_dbfs": 20 * np.log10(float(np.sqrt((first ** 2).mean() + 1e-12))),
    }


def save_recording(save_dir: Path, pcm: np.ndarray, text: str, language: str, extra: dict) -> str:
    save_dir.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    with wave.open(str(save_dir / f"{stem}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.astype("<i2").tobytes())
    (save_dir / f"{stem}.json").write_text(json.dumps(
        {"text": text, "language": language, **extra}, ensure_ascii=False, indent=1), encoding="utf-8")
    return stem


class Handler(AsyncEventHandler):
    def __init__(self, settings: Settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.s = settings
        self.info_event = make_info(settings.model_name).event()
        self.language = model_language(None, settings.default_lang)
        self.stream = None
        self.samples = 0
        self.t_start = 0.0
        self.pcm: list[np.ndarray] = []
        self.chunks = 0
        self.fed = 0

    def _decode(self) -> None:
        rec = self.s.recognizer
        while rec.is_ready(self.stream):
            rec.decode_stream(self.stream)
            self.chunks += 1

    def _feed(self, audio: np.ndarray) -> None:
        self.stream.accept_waveform(SAMPLE_RATE, audio)
        self.fed += len(audio)
        self._decode()

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.info_event)
            return True

        if Transcribe.is_type(event.type):
            req = Transcribe.from_event(event)
            self.language = model_language(req.language, self.s.default_lang)
            return True

        if AudioStart.is_type(event.type):
            start = AudioStart.from_event(event)
            if start.rate != SAMPLE_RATE or start.width != 2 or start.channels != 1:
                _LOGGER.error("Unsupported audio format: %s Hz, %s bytes, %s channels",
                              start.rate, start.width, start.channels)
                await self.write_event(Transcript(text="").event())
                return False
            self.stream = self.s.recognizer.create_stream()
            try:
                self.stream.set_option("language", self.language)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Language %s not accepted, using auto", self.language)
                self.stream.set_option("language", "auto")
            self.samples = 0
            self.chunks = 0
            self.fed = 0
            self.pcm = []
            self.t_start = time.perf_counter()
            if len(self.s.lead):
                async with self.s.lock:
                    await asyncio.to_thread(self._feed, self.s.lead)
            return True

        if AudioChunk.is_type(event.type):
            if self.stream is None:
                return True
            chunk = AudioChunk.from_event(event)
            raw = np.frombuffer(chunk.audio, dtype="<i2")
            self.pcm.append(raw.copy())
            audio = raw.astype(np.float32) / 32768.0
            self.samples += len(audio)
            async with self.s.lock:
                await asyncio.to_thread(self._feed, audio)
            return True

        if AudioStop.is_type(event.type):
            if self.stream is None:
                await self.write_event(Transcript(text="").event())
                return False
            t0 = time.perf_counter()

            def finish() -> str:
                if len(self.s.tail):
                    self._feed(self.s.tail)
                # Flush: add silence until the processed blocks cover all the speech plus a
                # margin. Without it the last word can be lost, depending on where the end of
                # the utterance falls relative to the encoder blocks.
                end_s = self.s.lead_s + self.samples / SAMPLE_RATE
                need = math.ceil((end_s + FLUSH_MARGIN_S) / self.s.chunk_s)
                for _ in range(4):
                    if self.chunks >= need:
                        break
                    missing = int((need * self.s.chunk_s + WINDOW_EXTRA_S) * SAMPLE_RATE) - self.fed
                    self._feed(np.zeros(max(missing, SAMPLE_RATE // 20), np.float32))
                self.stream.input_finished()
                self._decode()
                return self.s.recognizer.get_result(self.stream).strip()

            async with self.s.lock:
                text = await asyncio.to_thread(finish)
            fin_ms = (time.perf_counter() - t0) * 1000
            dur = self.samples / SAMPLE_RATE
            pcm = np.concatenate(self.pcm) if self.pcm else np.zeros(0, np.int16)
            st = audio_stats(pcm)
            onset = f"{st['onset_ms']} ms" if st["onset_ms"] is not None else "none"
            diag = f"peak {st['peak_dbfs']:.0f} dBFS, speech from {onset}"
            if self.s.log_transcripts:
                _LOGGER.info("[%s] %.2f s audio (%s), finalization %.0f ms: %r",
                             self.language, dur, diag, fin_ms, text)
            else:
                _LOGGER.info("[%s] %.2f s audio (%s), finalization %.0f ms, %d characters",
                             self.language, dur, diag, fin_ms, len(text))
            if st["onset_ms"] == 0 and st["rms_first_100ms_dbfs"] > -25:
                _LOGGER.info("  loud audio from the very first instant: the start may have been cut before reaching the server")
            if st["peak_dbfs"] < -30:
                _LOGGER.info("  very low audio (peak %.0f dBFS): consider auto gain on the satellite", st["peak_dbfs"])
            if self.s.save_dir is not None:
                try:
                    stem = save_recording(self.s.save_dir, pcm, text, self.language,
                                          {"duration_s": dur, "finalize_ms": fin_ms, **st})
                    _LOGGER.info("  audio saved: %s.wav", stem)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Could not save audio")
            await self.write_event(Transcript(text=text, language=self.language.split("-")[0]).event())
            self.stream = None
            return False

        return True


# ------------------------------------------------------------ configuration
def read_options() -> dict:
    p = Path("/data/options.json")
    return json.loads(p.read_text()) if p.exists() else {}


def announce_to_home_assistant(port: int) -> None:
    """Register the Wyoming service with the Supervisor (inside the add-on only)."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    try:
        req = urllib.request.Request("http://supervisor/addons/self/info",
                                     headers={"Authorization": f"Bearer {token}"})
        info = json.loads(urllib.request.urlopen(req, timeout=10).read())["data"]
        host = info.get("hostname") or info.get("ip_address")
        body = json.dumps({"service": "wyoming", "config": {"uri": f"tcp://{host}:{port}"}}).encode()
        req = urllib.request.Request("http://supervisor/discovery", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        _LOGGER.info("Announced to Home Assistant as tcp://%s:%d", host, port)
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Wyoming discovery failed (%s): add the Wyoming integration manually", e)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="tcp://0.0.0.0:10300")
    ap.add_argument("--chunk-ms", type=int, choices=[560, 1120])
    ap.add_argument("--model-dir", help="model folder (overrides --chunk-ms)")
    ap.add_argument("--models-root", default="/data/models")
    ap.add_argument("--threads", type=int)
    ap.add_argument("--lead-ms", type=int)
    ap.add_argument("--tail-ms", type=int)
    ap.add_argument("--language")
    ap.add_argument("--log-transcripts", action="store_true", default=None)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    opts = read_options()
    logging.basicConfig(level=logging.DEBUG if args.debug or opts.get("debug") else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    chunk = args.chunk_ms or int(opts.get("chunk_ms", DEFAULT_CHUNK_MS))
    threads = args.threads or int(opts.get("threads", DEFAULT_THREADS))
    lead_ms = args.lead_ms if args.lead_ms is not None else int(opts.get("lead_padding_ms", DEFAULT_LEAD_MS))
    tail_ms = args.tail_ms if args.tail_ms is not None else int(opts.get("tail_padding_ms", DEFAULT_TAIL_MS))
    language = args.language or opts.get("language", DEFAULT_LANGUAGE)
    log_tx = args.log_transcripts if args.log_transcripts is not None else bool(opts.get("log_transcripts", True))
    custom = args.model_dir or (opts.get("model_dir") or "").strip()
    blank_penalty = float(opts.get("blank_penalty", 0.0))
    save_audio = bool(opts.get("save_audio", False))
    save_dir = Path(opts.get("save_audio_dir") or "/share/edgestt/recordings") if save_audio else None

    if custom:
        model_dir = Path(custom)
    else:
        model_dir = ensure_model(chunk, Path(args.models_root))
    recognizer = load_recognizer(model_dir, threads, blank_penalty)
    model_name = model_dir.name.replace("sherpa-onnx-", "")
    m = re.search(r"(\d+)ms", str(model_dir))
    chunk_s = int(m.group(1)) / 1000 if m else chunk / 1000
    settings = Settings(recognizer, lead_ms / 1000, tail_ms / 1000, language, log_tx, model_name, save_dir, chunk_s)
    _LOGGER.info("EdgeSTT %s: model %s (%.2f s blocks), leading silence %d ms / minimum trailing silence %d ms, "
                 "default language %s, blank_penalty %.1f",
                 VERSION, model_name, chunk_s, lead_ms, tail_ms, language, blank_penalty)
    if save_dir:
        _LOGGER.info("Audio saving enabled in %s", save_dir)

    server = AsyncServer.from_uri(args.uri)
    port = int(args.uri.rsplit(":", 1)[1])
    announce_to_home_assistant(port)
    _LOGGER.info("Listening on %s", args.uri)
    await server.run(partial(Handler, settings))


if __name__ == "__main__":
    asyncio.run(main())
