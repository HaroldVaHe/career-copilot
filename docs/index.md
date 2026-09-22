# Career Copilot — Documentación

Punto de entrada del vault. Todo lo demás cuelga de aquí.

> [!tip] Cómo leer esto
> En Obsidian: abre esta nota y usa el grafo o los backlinks.
> En GitHub: todos los enlaces son relativos, así que funcionan igual en el navegador.

## Qué es

Copiloto local y de un solo usuario para buscar trabajo. Ingesta tu CV, lo audita
contra criterios ATS, agrega vacantes, las puntúa contra tu perfil, adapta el CV a
cada oferta, investiga la empresa y te entrena para la entrevista.

## Mapa

| Nota | Qué responde |
|---|---|
| [Arquitectura](arquitectura.md) | Cómo encajan las piezas y por dónde fluye un dato |
| [Modelo de datos](modelo-de-datos.md) | Qué tablas hay y por qué |
| [API](api.md) | Qué endpoints existen y qué módulo cubre cada uno |
| [Desarrollo](desarrollo.md) | Cómo levantarlo, comandos y variables de entorno |
| [Decisiones (ADR)](adr/index.md) | Por qué está hecho así y no de otra forma |
| [Diario](diario/index.md) | Qué se construyó cada sesión |

## Estado

Backend funcional con los seis módulos enrutados. El frontend ya tiene sus
cimientos — cliente de API tipado (`src/lib/`), kit de componentes, gráficos y
navegación — pero todavía no hay pantallas por módulo. La extensión de navegador
no existe aún: el backend ya expone su contrato en `/api/v1/capture`.

| Módulo | Backend | Pantalla |
|---|---|---|
| 1 — CV: parsing, ATS, tailoring | Listo | Pendiente |
| 2 — Vacantes: ingesta, matching | Listo | Pendiente |
| 3 — Extensión: captura, autofill | Contrato listo | Extensión sin empezar |
| 4 — Postulaciones: Kanban, tareas | Listo | Pendiente |
| 5 — Inteligencia: empresa, salario | Listo | Pendiente |
| 6 — Entrevistas: simulacro, banco QA | Listo | Pendiente |

## Pendientes conocidos

Cosas detectadas y aún no resueltas. Cuando una se cierre, se borra de aquí.

- `LLM_FAST_MODEL=claude-haiku-4-5` usa el alias corto; el id completo es
  `claude-haiku-4-5-20251001`. Conviene fijarlo para que la versión no se mueva sola.
- No hay migraciones: el esquema se crea con `Base.metadata.create_all`. Ver
  [ADR 0003](adr/0003-sin-migraciones.md) para cuándo dejaría de valer.
- `backend/tests/` existe pero está vacío, y `backend/smoke_tmp.py` es un script
  de prueba manual que debería moverse allí o borrarse.
