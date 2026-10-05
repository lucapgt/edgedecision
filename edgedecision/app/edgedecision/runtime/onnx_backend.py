"""Torch-free runtime backend: ONNX Runtime + HF `tokenizers` + numpy.

Runs on x86, ARM64 (Raspberry Pi 4/5, Jetson CPU) and any ONNX Runtime execution provider.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class OnnxBackend:
    def __init__(self, bundle_dir: str, model_file: str = "model.int8.onnx", threads: int | None = None,
                 providers: list[str] | None = None):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = Path(bundle_dir)
        self.meta = json.loads((d / "edge_runtime.json").read_text(encoding="utf-8"))
        if not (d / model_file).exists():
            model_file = "model.onnx"
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads:
            so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(str(d / model_file), so, providers=providers or ["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.max_len = int(self.meta["max_len"])
        self.q_max_len = int(self.meta.get("q_max_len", 48))
        self.tok.no_padding()
        self.tok.no_truncation()
        self.pad_id = int(self.meta["pad_id"])
        self.model_file = model_file
        self.has_tags = "tags" in {o.name for o in self.sess.get_outputs()} and bool(self.meta.get("word_tags"))

    def _batch(self, encs, max_len):
        n = len(encs)
        L = min(max_len, max(len(e.ids) for e in encs))
        ids = np.full((n, L), self.pad_id, dtype=np.int64)
        mask = np.zeros((n, L), dtype=np.int64)
        tt = np.zeros((n, L), dtype=np.int64)
        for i, e in enumerate(encs):
            k = min(L, len(e.ids))
            ids[i, :k] = e.ids[:k]
            mask[i, :k] = 1
            tt[i, :k] = e.type_ids[:k]
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = tt
        return feed

    def _encode(self, a, b=None, max_len=None):
        max_len = max_len or self.max_len
        self.tok.enable_truncation(max_length=max_len)
        if b is None:
            return self.tok.encode_batch(list(a))
        return self.tok.encode_batch(list(zip(a, b)))

    def embed(self, texts, batch: int = 64) -> np.ndarray:
        outs = []
        for i in range(0, len(texts), batch):
            encs = self._encode(texts[i:i + batch], max_len=self.q_max_len * 2)
            _, _, emb = self.sess.run(["score", "types", "embedding"], self._batch(encs, self.q_max_len * 2))
            outs.append(emb)
        return np.concatenate(outs).astype(np.float32) if outs else np.zeros((0, self.meta["emb_dim"]), np.float32)

    def score(self, query: str, cand_texts, batch: int = 32):
        s, t = [], []
        for i in range(0, len(cand_texts), batch):
            c = list(cand_texts[i:i + batch])
            encs = self._encode([query] * len(c), c)
            sc, ty = self.sess.run(["score", "types"], self._batch(encs, self.max_len))
            s.append(sc)
            t.append(ty)
        return np.concatenate(s), np.concatenate(t)

    def tag(self, text: str):
        """[(word, tag)] for the words of `text` (split on spaces), or None if the model has no tagging head."""
        words = text.split()
        if not self.has_tags or not words:
            return None
        self.tok.enable_truncation(max_length=self.max_len)
        enc = self.tok.encode(words, is_pretokenized=True)
        (tags,) = self.sess.run(["tags"], self._batch([enc], self.max_len))
        names = self.meta["word_tags"]
        out = [None] * len(words)
        for i, w in enumerate(enc.word_ids):
            if w is not None and i < tags.shape[1] and out[w] is None:
                out[w] = names[int(tags[0, i].argmax())]
        return [(w, t or "O") for w, t in zip(words, out)]
