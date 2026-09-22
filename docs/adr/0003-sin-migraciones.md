# ADR 0003 — `create_all` en el arranque en vez de Alembic

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

El esquema tiene doce tablas y va a moverse mucho mientras se construyen los seis
módulos. Alembic es el estándar con SQLAlchemy, pero cada cambio implica generar
una revisión, revisarla (la autogeneración con `JSONB` y `Vector` no siempre
acierta) y aplicarla.

## Decisión

`app/db/init_db.py` se ejecuta en el `lifespan` de FastAPI: crea las extensiones
`vector` y `pg_trgm`, llama a `Base.metadata.create_all` y siembra el usuario
local del `.env`. Sin Alembic.

## Razones

- Un solo usuario, una sola instancia, datos reconstruibles: los CV están en
  disco y las vacantes se vuelven a ingerir. No hay producción que preservar.
- El arranque queda en `docker compose up -d` + `uvicorn`, sin paso intermedio
  que recordar ni documentar.
- Durante el diseño del esquema, el ciclo «cambio el modelo → borro el volumen →
  arranco» es más rápido que mantener una cadena de revisiones que nadie va a
  volver a aplicar.

## Consecuencias

- **`create_all` no altera tablas existentes.** Cambiar una columna no se
  propaga: hay que borrar el volumen (`docker compose down -v`) y perder los datos.
- Sin historial de esquema ni posibilidad de rollback.
- El día que esto tenga datos que no se puedan reconstruir —o más de un usuario—
  hay que introducir Alembic con una revisión inicial que refleje el estado
  actual. Ese día este ADR se reemplaza.

## Relacionado

[Modelo de datos](../modelo-de-datos.md) · [ADR 0007](0007-single-tenant.md)
