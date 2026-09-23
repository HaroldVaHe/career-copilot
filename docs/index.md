# Career Copilot — Documentación

Punto de entrada del vault. Todo lo demás cuelga de aquí.

> [!tip] Cómo leer esto
> En Obsidian: abre esta nota y usa el grafo o los backlinks.
> En GitHub: todos los enlaces son relativos, así que funcionan igual en el navegador.

## Qué es

Copiloto local para buscar trabajo, con un perfil por persona. Ingesta tu CV, lo audita
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

Los seis módulos están completos de punta a punta: backend, pantalla y -donde
aplica- extensión de navegador. 87 tests pasan (parte determinista, PDF,
geografía de vacantes y aislamiento de perfiles). Lo que queda es pulido y
cobertura, no piezas ausentes.

| Módulo | Backend | Pantalla |
|---|---|---|
| 1 - CV: parsing, ATS, tailoring, informe PDF | Listo | `/cv` - Mis CV |
| 2 - Vacantes: búsqueda según CV, filtro por país, matching | Listo | `/vacantes`, `/vacantes/[id]` |
| 3 - Extensión: captura, autofill, selector de perfil | Listo | `extension/` (Manifest V3) |
| 4 - Postulaciones: Kanban, tareas | Listo | `/pipeline` |
| 5 - Inteligencia: empresa, salario | Listo | dentro de `/vacantes/[id]` |
| 6 - Entrevistas: simulacro, banco QA | Listo | `/entrevistas` |
| Perfiles: varias personas por instalación | Listo | `/perfiles` + selector en la barra lateral |

Más `/` (Panel) y `/ajustes` (preferencias de búsqueda).

## Pendientes conocidos

Cosas detectadas y aún no resueltas. Cuando una se cierre, se borra de aquí.

- `LLM_FAST_MODEL` está en la configuración pero **ningún servicio lo usa**: la
  normalización de vacantes y el plan de búsqueda van con `LLM_MODEL` y `effort`
  bajo/medio. Antes de usarlo hay que comprobar que ese modelo acepta
  `thinking: adaptive` y `output_config.effort`, que `llm.py` manda siempre.
- **El matching solo entiende tecnología.** La taxonomía de skills es de software:
  para perfiles de diseño, marketing, etc. el match sale bajo y plano, y el orden
  por score mezcla vacantes ajenas (a una diseñadora le puntúa igual una oferta
  de Python). Haría falta ampliar la taxonomía o pesar más el embedding.
- El perfil activo del dashboard (`localStorage`) y el de la extensión
  (`chrome.storage`) son independientes. "Abrir dossier" los alinea con
  `?perfil=`, pero no hay sincronización general.
- En Windows, `localhost` resuelve primero a `::1` y uvicorn solo escucha en
  `127.0.0.1`: cada petición de PowerShell/Python a `localhost:8000` paga ~2 s.
  Chrome no lo nota. Usa `127.0.0.1` en scripts.
- En Chrome automatizado (patchright) algunas peticiones lanzadas mientras un
  `POST /jobs/search` pesado está en curso fallan con `ERR_FAILED` sin que lleguen
  al servidor. No se reproduce con peticiones sintéticas ni desde Python. El
  frontend reintenta una vez los GET; los POST no se reintentan.
- No hay migraciones: el esquema se crea con `Base.metadata.create_all`. Ver
  [ADR 0003](adr/0003-sin-migraciones.md) para cuándo dejaría de valer.
- Los tests cubren lo determinista, el PDF, la geografía y los perfiles. Las
  rutas que tocan BD están tras el marcador `needs_db` y no hay tests de los
  servicios que llaman al LLM ni de las fuentes externas (se probaron a mano).
- `backend/smoke_tmp.py` y `backend/ingest_tmp.py` son scripts de prueba manual
  en la raíz de `backend/`. Se dejan a propósito por ahora.
