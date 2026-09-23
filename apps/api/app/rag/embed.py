"""Sentence embeddings via a lazily loaded SentenceTransformer singleton.

Importing this module MUST NOT touch the model or the network: the heavy
``SentenceTransformer`` import and checkpoint load happen on first use inside
``get_model()``.

The singleton is a module-global guarded by a double-checked ``threading.Lock``:
concurrent first use loads the model exactly once, and every later call is an
uncontended global read. ``encode()`` itself is thread-safe on the published
instance.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from ..config import get_settings


_model = None
_load_lock = threading.Lock()
_load_seconds: float | None = None


class EmbeddingDimensionError(RuntimeError):
    """The loaded embed model disagrees with settings.embed_dim."""


def get_model():
    """Return the lazily loaded ``SentenceTransformer`` singleton.

    Double-checked under a lock so concurrent first-use loads the model once;
    subsequent calls are an uncontended attribute-free global read.
    """
    global _model, _load_seconds
    if _model is not None:
        return _model
    with _load_lock:
        if _model is None:
            # Heavy import deliberately deferred to first use.
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            started = time.perf_counter()
            _model = SentenceTransformer(settings.embed_model)
            _load_seconds = time.perf_counter() - started
    return _model


def _check_dim(vec: np.ndarray) -> None:
    """Assert the model's output width matches EMBED_DIM; name both numbers."""
    expected = get_settings().embed_dim
    actual = int(vec.shape[-1])
    if actual != expected:
        raise EmbeddingDimensionError(
            f"embed model returns {actual}-d vectors, EMBED_DIM={expected}"
        )


def _prefix(kind: str) -> str:
    """Input prefix the model family was trained with; '' when it uses none.

    E5 checkpoints (intfloat/multilingual-e5-*) expect ``query: `` / ``passage: ``.
    bge-m3 (the default) and kazembed-v5 take raw text: prefixes measured
    neutral-to-worse for kazembed on Belebele kk/ru, 2026-09-23.
    """
    name = get_settings().embed_model.lower()
    if "e5" in name and "instruct" not in name:
        return "query: " if kind == "query" else "passage: "
    return ""


def _encode(texts: list[str], kind: str, batch_size: int) -> np.ndarray:
    settings = get_settings()
    if not texts:
        return np.zeros((0, settings.embed_dim), dtype=np.float32)
    prefix = _prefix(kind)
    vecs = get_model().encode(
        [prefix + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    out = np.asarray(vecs, dtype=np.float32)
    if out.ndim != 2:  # defensive: encode() should always give (n, d)
        out = out.reshape(len(texts), -1)
    _check_dim(out)
    return out


def embed_texts(texts: list[str], *, batch_size: int = 16) -> np.ndarray:
    """Embed documents/passages as float32, L2-normalised rows of width ``embed_dim``.

    Empty input returns a valid ``(0, embed_dim)`` array without loading the
    model.
    """
    return _encode(list(texts), "passage", batch_size)


def embed_query(text: str) -> np.ndarray:
    """Embed a single search query; 1-D float32 vector of width ``embed_dim``."""
    return _encode([text], "query", 1)[0]


def warmup() -> float:
    """Force the model load now; return the load time in seconds."""
    get_model()
    return float(_load_seconds or 0.0)
