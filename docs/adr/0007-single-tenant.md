# ADR 0007 — Un solo usuario, sin autenticación

- **Fecha:** 2026-09-21
- **Estado:** Reemplazado por [ADR 0008](0008-multiperfil.md)

## Contexto

Es una herramienta personal que corre en `localhost`. Añadir registro, login,
hash de contraseñas, tokens y su renovación son bastantes horas antes de escribir
una sola línea de la funcionalidad que justifica el proyecto.

## Decisión

Existe una tabla `users`, pero `get_current_user` en `app/api/deps.py` devuelve
siempre el perfil definido por `DEFAULT_USER_EMAIL`, sembrado en el arranque por
`init_db()`. No hay autenticación.

## Razones

- El modelo de datos ya está preparado (todo cuelga de `user_id`), así que la
  decisión es reversible sin tocar el esquema.
- **Hay un único punto que cambiar.** El día que haga falta multiusuario, se
  reescribe `get_current_user` para leer un token; el resto de la API ya depende
  de esa dependencia y no se entera.
- Sin login, la extensión de navegador no necesita gestionar sesión.

## Consecuencias

- **La API no debe exponerse fuera de `localhost`.** Cualquiera que la alcance
  tiene acceso total al CV y a las postulaciones.
- No hay aislamiento de datos entre usuarios porque no hay usuarios.
- Si el proyecto llega a desplegarse, este ADR se reemplaza y hace falta también
  revisar CORS, que hoy es deliberadamente permisivo.

## Relacionado

[ADR 0003](0003-sin-migraciones.md) · [Arquitectura](../arquitectura.md)
