# ADR 0005 — El tailoring propone, nunca guarda solo

- **Fecha:** 2026-09-21
- **Estado:** Aceptado

## Contexto

Adaptar el CV a una oferta es la función más útil del sistema y también la más
peligrosa: un modelo que reescribe bullets para encajar con unos requisitos tiene
un incentivo directo a exagerar. Un CV con una afirmación que no puedes defender
no es un CV optimizado, es un problema en la entrevista técnica.

## Decisión

El flujo está partido en dos endpoints y el sistema nunca persiste una
reescritura por iniciativa propia:

| Paso | Endpoint | Efecto |
|---|---|---|
| Proponer | `POST /api/v1/resumes/tailor` | Devuelve `TailorResponse` con diff palabra a palabra. **No escribe en BD** |
| Aceptar | `POST /api/v1/resumes/variants` | Guarda lo que el usuario aprobó, como CV nuevo |

La variante se guarda como fila nueva en `resumes` con `parent_id` al original y
`tailored_for_job_id` a la vacante. El CV base nunca se sobrescribe.

## Razones

- El usuario tiene que **ver exactamente qué cambió** antes de aceptarlo. De ahí
  el diff palabra a palabra estilo Git (`difflib` en `services/tailoring.py`), no
  un «aquí tienes tu CV mejorado».
- Las reescrituras que podrían ser invención se marcan explícitamente.
- Conservar el linaje `parent_id` permite volver atrás y comparar variantes.
- Quien responde por el contenido del CV en la entrevista es el usuario, así que
  la última palabra tiene que ser suya.

## Consecuencias

- Dos llamadas en vez de una, y el frontend necesita una vista de diff decente.
- Proliferan filas en `resumes`: una variante por oferta trabajada.
- El sistema es más lento de usar de lo que podría ser. Es intencional.

## Relacionado

[API — Módulo 1](../api.md) · [Modelo de datos](../modelo-de-datos.md)
