"""
retrieval.py — the Trace Layer.

Embeds Dr. Chen's corpus (epoch_gateway/corpus/chen_traces.py) with a Vertex AI
embedding model, builds one vector index per tenant, and answers a query with
the top matching traces plus a one-hop expansion along their `related` links
(the Pattern Layer). Retrieval never crosses the tenant boundary.

Uses faiss.IndexFlatIP when faiss is importable; otherwise an exact numpy
inner-product search, which is identical for a corpus this size.
"""
import asyncio
import os
from collections import defaultdict

import numpy as np

from .corpus.chen_traces import TRACES

try:
    import faiss  # type: ignore
    _HAVE_FAISS = True
except Exception:  # pragma: no cover
    _HAVE_FAISS = False

_EMBED_MODEL = os.environ.get("EPOCH_EMBED_MODEL", "text-embedding-004")
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

_FIELDS = ("pattern", "finding", "features", "reasoning", "recommendation")


def _doc_text(t: dict) -> str:
    return (
        f"{t['pattern']}. "
        f"Findings: {t['finding']} "
        f"Discriminating features: {'; '.join(t['features'])}. "
        f"Reasoning: {t['reasoning']}"
    )


def _normalise(m: np.ndarray) -> np.ndarray:
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)


class TwinIndex:
    """Lazily-built, per-tenant vector index over Dr. Chen's traces."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._built = False
        self._client = None
        self._by_tenant: dict[str, dict] = {}   # tenant -> {ids, matrix|faiss}
        self._traces = {t["id"]: t for t in TRACES}
        self.backend = "faiss" if _HAVE_FAISS else "numpy"

    def _genai(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(
                vertexai=True, project=_PROJECT, location=_LOCATION
            )
        return self._client

    async def _embed(self, texts: list[str]) -> np.ndarray:
        resp = await self._genai().aio.models.embed_content(
            model=_EMBED_MODEL, contents=texts
        )
        return np.array([e.values for e in resp.embeddings], dtype="float32")

    async def build(self) -> None:
        if self._built:
            return
        async with self._lock:
            if self._built:
                return
            groups: dict[str, list] = defaultdict(list)
            for t in TRACES:
                groups[t["tenant"]].append(t)
            for tenant, items in groups.items():
                vecs = _normalise(await self._embed([_doc_text(t) for t in items]))
                entry = {"ids": [t["id"] for t in items], "dim": vecs.shape[1]}
                if _HAVE_FAISS:
                    idx = faiss.IndexFlatIP(vecs.shape[1])
                    idx.add(vecs)
                    entry["faiss"] = idx
                else:
                    entry["matrix"] = vecs
                self._by_tenant[tenant] = entry
            self._built = True

    async def retrieve(self, tenant: str, query: str, k: int = 4,
                       hop: bool = True) -> list[dict]:
        await self.build()
        part = self._by_tenant.get(tenant)
        if not part:
            return []
        q = _normalise(await self._embed([query]))
        if "faiss" in part:
            scores, idxs = part["faiss"].search(q, min(k, len(part["ids"])))
            hits = [(part["ids"][j], float(scores[0][n]))
                    for n, j in enumerate(idxs[0]) if j >= 0]
        else:
            s = (part["matrix"] @ q[0])
            order = np.argsort(-s)[:k]
            hits = [(part["ids"][int(j)], float(s[int(j)])) for j in order]

        picked: list[tuple[str, float | None]] = list(hits)
        seen = {tid for tid, _ in picked}
        if hop:
            for tid, _ in hits:
                for rel in self._traces.get(tid, {}).get("related", []):
                    rt = self._traces.get(rel)
                    if rel not in seen and rt and rt["tenant"] == tenant:
                        seen.add(rel)
                        picked.append((rel, None))

        out = []
        for tid, score in picked:
            t = self._traces[tid]
            out.append({
                "id": tid,
                "score": score,
                "linked": score is None,
                **{f: t[f] for f in _FIELDS},
            })
        return out

    def get(self, tenant: str, trace_id: str) -> dict | None:
        t = self._traces.get(trace_id)
        if not t or t["tenant"] != tenant:
            return None
        return {"id": t["id"], **{f: t[f] for f in _FIELDS}, "related": t["related"]}

    def stats(self) -> dict:
        return {
            "backend": self.backend,
            "built": self._built,
            "tenants": {k: len(v["ids"]) for k, v in self._by_tenant.items()},
            "total_traces": len(self._traces),
        }


INDEX = TwinIndex()
