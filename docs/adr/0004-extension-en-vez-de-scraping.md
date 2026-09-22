# ADR 0004 — Extensión de navegador en vez de scraping

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

Las vacantes que le interesan al usuario están sobre todo en LinkedIn, Indeed,
Glassdoor, Workday, Greenhouse, Lever y Taleo. Ninguna ofrece API pública para
este caso, y todas prohíben el scraping automatizado en sus términos de uso.
LinkedIn además banea la cuenta, que es justo la cuenta que el usuario necesita
para buscar trabajo.

## Decisión

Dos vías separadas, y ninguna scrapea esos portales:

1. **Fuentes públicas** (`app/services/sources/`) — solo agregadores con API
   abierta sin key. Ingesta automática vía `POST /api/v1/jobs/ingest`.
2. **Extensión de navegador** (`/api/v1/capture`) — lee el DOM de la página que
   el usuario ya tiene abierta, en su propia sesión, y lo envía al backend.

## Razones

- La extensión no automatiza nada contra el servidor del portal: el usuario ya
  cargó esa página. No hay tráfico adicional ni evasión de controles.
- Funciona con ofertas detrás de login, que es donde está el contenido bueno.
- El riesgo de baneo desaparece porque no hay patrón de acceso automatizado.
- Como efecto secundario, el mismo canal sirve para el autofill de formularios
  (`/capture/autofill`, `/capture/answer`).

## Consecuencias

- No hay ingesta masiva desde los portales grandes: el usuario captura una a una
  las ofertas que le interesan. Es más trabajo manual, a cambio de una cuenta viva.
- Hay que construir y mantener una extensión, con su propio ciclo de publicación.
- CORS debe aceptar `chrome-extension://*` y `moz-extension://*` por regex,
  porque el id no se conoce de antemano (`main.py`).
- Cada portal necesita su propio extractor en `extension/extractors.js`, y un
  rediseño de su HTML lo rompe. Es mantenimiento recurrente y asumido.

## Relacionado

[Arquitectura](../arquitectura.md) · [API — Módulo 3](../api.md)
