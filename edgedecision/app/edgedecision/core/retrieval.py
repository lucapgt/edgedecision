"""Hybrid candidate retrieval: char n-gram TF-IDF (typo robust) + dense embeddings.

Reduces a large runtime catalog to a few candidates before cross scoring.
Capability embeddings are computed once per catalog (they do not contain
state), so query-time cost is one encoder pass + a matrix product.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Callable, Optional

import numpy as np

from .text import normalize


def char_ngrams(s: str, n_values=(3, 4)) -> Counter:
    out: Counter = Counter()
    for w in normalize(s).replace("'", " ").split():
        w = f" {w} "
        for n in n_values:
            if len(w) < n:
                continue
            for i in range(len(w) - n + 1):
                out[w[i:i + n]] += 1
    return out


class LexicalIndex:
    """TF-IDF over char n-grams with an inverted index (compact and fast)."""

    def __init__(self, docs: list[str]):
        self.n = len(docs)
        vecs = [char_ngrams(d) for d in docs]
        df: Counter = Counter()
        for v in vecs:
            df.update(v.keys())
        n = max(1, self.n)
        self.idf = {g: math.log((n + 1) / (c + 0.5)) + 1.0 for g, c in df.items()}
        post: dict = {}
        norms = np.zeros(self.n, dtype=np.float32)
        for i, v in enumerate(vecs):
            sq = 0.0
            for g, c in v.items():
                w = (1 + math.log(c)) * self.idf[g]
                sq += w * w
                post.setdefault(g, ([], []))
                post[g][0].append(i)
                post[g][1].append(w)
            norms[i] = math.sqrt(sq) or 1.0
        self.post = {g: (np.asarray(ids, dtype=np.int32), np.asarray(ws, dtype=np.float32))
                     for g, (ids, ws) in post.items()}
        self.den = np.sqrt(norms)

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float32)
        q = char_ngrams(query)
        qn = 0.0
        for g, c in q.items():
            p = self.post.get(g)
            if p is None:
                continue
            w = (1 + math.log(c)) * self.idf[g]
            qn += w * w
            np.add.at(out, p[0], w * p[1])
        qn = math.sqrt(qn) or 1.0
        # asymmetric: normalise mostly by the query so long docs are not punished
        return out / (qn * self.den)


class HybridRetriever:
    def __init__(self, cap_ids: list[str], lexical_docs: list[str], embed_fn: Optional[Callable] = None,
                 bi_texts: Optional[list[str]] = None, w_dense: float = 0.7, w_lex: float = 0.3):
        self.cap_ids = cap_ids
        self.lex = LexicalIndex(lexical_docs)
        self.embed_fn = embed_fn
        self.w_dense, self.w_lex = w_dense, w_lex
        self.emb = None
        if embed_fn is not None and bi_texts:
            self.emb = embed_fn(bi_texts)

    def retrieve(self, query: str, k: int, query_emb: Optional[np.ndarray] = None) -> list[tuple[str, float]]:
        n = len(self.cap_ids)
        if n == 0:
            return []
        lex = self.lex.scores(query)
        if lex.max() > 0:
            lex = lex / lex.max()
        score = self.w_lex * lex
        if self.emb is not None:
            if query_emb is None:
                query_emb = self.embed_fn([query])[0]
            dense = self.emb @ query_emb
            score = score + self.w_dense * dense
        order = np.argsort(-score)[:k]
        return [(self.cap_ids[i], float(score[i])) for i in order]
