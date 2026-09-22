# ADR 0006 — Un único cliente LLM con salida estructurada

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

Ocho servicios distintos llaman al modelo: parsing de CV, revisión ATS,
normalización de vacantes, análisis de match, tailoring, intel de empresa,
generación de tareas y simulacro de entrevista. Casi todos necesitan la
respuesta como estructura de datos, no como prosa.

El patrón habitual —pedir JSON en el prompt y parsear la respuesta— falla de
formas molestas: el modelo envuelve el JSON en bloques de código, añade un
párrafo introductorio, o se salta un campo opcional.

## Decisión

Todas las llamadas pasan por `app/services/llm.py`. Para las que devuelven
estructura, se usa `output_config.format` con un JSON Schema derivado del modelo
Pydantic de destino, y la respuesta se valida contra ese mismo modelo.

## Razones

- El parseo deja de depender de que el modelo «se acuerde» de responder JSON: el
  formato lo garantiza la API.
- Un solo sitio donde ajustar modelo, `effort` y manejo de errores. Cambiar de
  `claude-opus-5` a `claude-sonnet-5` es una variable de entorno.
- Dos excepciones propias (`LLMUnavailable`, `LLMError`) con manejadores globales
  en `main.py` → 503 y 502. Ninguna ruta repite ese `try/except`.
- El esquema Pydantic sirve tres veces: contrato del LLM, validación, y forma del
  `JSONB` donde se guarda.

## Consecuencias

- Todo servicio nuevo que hable con el modelo debe definir antes su modelo
  Pydantic en `app/schemas/`. Es fricción deliberada.
- La salida estructurada restringe al modelo: para tareas donde la forma libre es
  mejor (redactar una cover letter) se usa la vía de texto del mismo cliente.
- Acopla el proyecto al SDK de Anthropic. Aceptable: el modelo es una decisión de
  producto aquí, no un detalle intercambiable.

## Relacionado

[Arquitectura](../arquitectura.md) · [API — Errores del LLM](../api.md)
