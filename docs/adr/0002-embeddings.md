# ADR 0002 — Embeddings locales por defecto, Voyage opcional

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

El matching semántico necesita embeddings, y Anthropic no expone API de
embeddings. Las alternativas son un proveedor externo (Voyage, OpenAI, Cohere),
un modelo local tipo `sentence-transformers`, o algo puramente determinista.

Un modelo local de verdad implica arrastrar PyTorch: cientos de megas y un
arranque lento para un proyecto que por lo demás son cuatro dependencias.

## Decisión

Dos proveedores tras la misma interfaz en `app/services/embeddings.py`, elegidos
con `EMBEDDING_PROVIDER`:

- **`local`** (default) — proyección aleatoria determinista de bolsa-de-palabras
  (*hashing trick*). Cero dependencias, cero costo, cero latencia.
- **`voyage`** — Voyage AI, el proveedor que recomienda Anthropic. Requiere
  `VOYAGE_API_KEY`.

## Razones

- Un CV y una oferta están tan cargados de términos técnicos concretos que el
  coseno sobre vocabulario ponderado acaba midiendo algo bastante útil.
- La parte del matching que más pesa no es semántica: es la cobertura de skills
  duras vía taxonomía (0.50 frente a 0.35). El embedding es desempate.
- El proyecto arranca sin ninguna API key y sigue siendo funcional.
- Cuando el desempate importa de verdad, un cambio de variable de entorno da
  sinónimos reales («construí APIs» ≈ «desarrollo de servicios REST»).

## Consecuencias

- El proveedor `local` no entiende sinónimos ni paráfrasis. Es solapamiento de
  vocabulario con otro nombre.
- **Cambiar de proveedor o de `EMBEDDING_DIM` invalida todos los vectores
  guardados.** `EMB_DIM` se lee en tiempo de import y define el tipo de columna,
  así que hay que recrear las tablas y llamar a `POST /api/v1/jobs/reindex`.
- Comparar puntuaciones de matching entre proveedores no tiene sentido.

## Relacionado

[Arquitectura](../arquitectura.md) · [Modelo de datos](../modelo-de-datos.md)
