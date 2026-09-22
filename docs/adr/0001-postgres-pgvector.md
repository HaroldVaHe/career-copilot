# ADR 0001 — Postgres con pgvector como única base de datos

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

El sistema necesita cuatro cosas a la vez: relaciones (usuario → CV →
postulación), documentos semiestructurados que produce el LLM y cambian de forma
a menudo, búsqueda vectorial para el matching CV↔vacante, y búsqueda por texto
para filtrar ofertas.

La vía habitual es repartirlo: Postgres para lo relacional y Qdrant/Pinecone/
Weaviate para los vectores.

## Decisión

Una sola Postgres 16 con las extensiones `vector` y `pg_trgm`. Los documentos
del LLM van en columnas `JSONB`, los vectores en columnas `Vector(EMBEDDING_DIM)`.

## Razones

- El volumen es de una persona buscando trabajo: miles de vacantes, no millones.
  Un índice vectorial dedicado resuelve un problema de escala que aquí no existe.
- Un único `docker compose up -d` y un único backup.
- El filtro que de verdad importa es híbrido — «vacantes remotas, en España,
  publicadas esta semana, parecidas a mi CV». Con la base de datos separada eso
  son dos consultas y un join a mano; en Postgres es un `WHERE` y un `ORDER BY`.
- `JSONB` evita una migración cada vez que un esquema Pydantic gana un campo.

## Consecuencias

- Si el corpus creciera a cientos de miles de vacantes habría que revisar el
  índice vectorial (HNSW) o migrar a un motor dedicado.
- Los campos `JSONB` no tienen garantía de esquema en la base de datos. Se
  compensa con un modelo Pydantic espejo por columna en `app/schemas/`.
- Postgres queda como dependencia dura: el proyecto no corre sobre SQLite.

## Relacionado

[Modelo de datos](../modelo-de-datos.md) · [ADR 0002](0002-embeddings.md)
