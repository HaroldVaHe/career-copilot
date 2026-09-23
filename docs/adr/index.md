# Decisiones de arquitectura (ADR)

[← Índice](../index.md)

Una nota por decisión que costó pensar y que sería cara de revertir. Si algo del
código parece raro, la explicación debería estar aquí.

Un ADR no se edita cuando cambias de opinión: se marca `Reemplazado por` y se
escribe uno nuevo. El historial de por qué te equivocaste vale tanto como la
decisión actual.

| # | Decisión | Estado |
|---|---|---|
| [0001](0001-postgres-pgvector.md) | Postgres con pgvector como única base de datos | Aceptado |
| [0002](0002-embeddings.md) | Embeddings locales por defecto, Voyage opcional | Aceptado |
| [0003](0003-sin-migraciones.md) | `create_all` en el arranque en vez de Alembic | Aceptado |
| [0004](0004-extension-en-vez-de-scraping.md) | Extensión de navegador en vez de scraping | Aceptado |
| [0005](0005-tailoring-con-aprobacion.md) | El tailoring propone, nunca guarda solo | Aceptado |
| [0006](0006-salida-estructurada-llm.md) | Un único cliente LLM con salida estructurada | Aceptado |
| [0007](0007-single-tenant.md) | Un solo usuario, sin autenticación | Reemplazado por 0008 |
| [0008](0008-multiperfil.md) | Varios perfiles por cabecera `X-Profile-Id`, sin autenticación | Aceptado |

Plantilla: [`../_templates/adr.md`](../_templates/adr.md)
