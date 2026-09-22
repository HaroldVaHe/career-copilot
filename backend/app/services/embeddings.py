"""Embeddings para la búsqueda semántica CV <-> vacante.

Anthropic no expone una API de embeddings, así que hay dos proveedores:

* `local`  — proyección aleatoria determinista de bolsa-de-palabras (hashing
  trick). Cero dependencias, cero costo, cero latencia, y para documentos tan
  cargados de términos técnicos como un CV o una oferta rinde sorprendentemente
  bien porque el coseno acaba midiendo solapamiento de vocabulario ponderado.
* `voyage` — Voyage AI, el proveedor de embeddings que recomienda Anthropic.
  Captura sinónimos reales ("construí APIs" ~ "desarrollo de servicios REST").

Se cambia con EMBEDDING_PROVIDER en el .env. Si cambias de proveedor tienes que
ajustar EMBEDDING_DIM y reindexar (POST /api/v1/search/reindex).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9][a-záéíóúüñ0-9+#.\-]*", re.IGNORECASE)

# Palabras que aparecen en todas las ofertas y no discriminan nada.
_STOPWORDS = {
    "de", "la", "el", "en", "y", "a", "los", "las", "del", "un", "una", "para", "con", "por",
    "que", "se", "su", "al", "lo", "como", "más", "o", "este", "esta", "nos", "the", "and",
    "for", "with", "you", "our", "are", "will", "have", "this", "that", "from", "your", "their",
    "we", "is", "to", "of", "in", "on", "at", "be", "as", "an", "or", "it", "by", "was", "were",
}


def tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) > 1 and t.lower() not in _STOPWORDS
    ]


def _hash_index(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    # Un bit aparte fija el signo: dos tokens que colisionan en el mismo índice
    # se cancelan la mitad de las veces en vez de sumarse siempre.
    return value % dim, 1.0 if (value >> 63) & 1 else -1.0


def embed_local(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vector

    # Unigramas + bigramas: el bigrama distingue "machine learning" de dos
    # menciones sueltas de "machine" y "learning".
    grams = Counter(tokens)
    grams.update(f"{a}_{b}" for a, b in zip(tokens, tokens[1:]))

    for gram, count in grams.items():
        idx, sign = _hash_index(gram, dim)
        vector[idx] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def embed_voyage(texts: list[str]) -> list[list[float]]:
    if not settings.voyage_api_key:
        raise RuntimeError("EMBEDDING_PROVIDER=voyage pero falta VOYAGE_API_KEY en el .env")
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
        json={"input": texts, "model": settings.voyage_model, "input_type": "document"},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    vectors = [d["embedding"] for d in data]
    if vectors and len(vectors[0]) != settings.embedding_dim:
        raise RuntimeError(
            f"{settings.voyage_model} devuelve {len(vectors[0])} dimensiones pero "
            f"EMBEDDING_DIM={settings.embedding_dim}. Ajusta el .env y reindexa."
        )
    return vectors


def embed(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedding_provider == "voyage":
        try:
            return embed_voyage(texts)
        except Exception as exc:  # no tumbar la app por un fallo del proveedor
            log.error("Voyage falló (%s). Usando embeddings locales para este lote.", exc)
    return [embed_local(t, settings.embedding_dim) for t in texts]


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))
