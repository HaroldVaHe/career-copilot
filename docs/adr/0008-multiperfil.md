# ADR 0008 - Varios perfiles en una instalación, sin autenticación

- **Fecha:** 2026-09-23
- **Estado:** Aceptado. Reemplaza a [ADR 0007](0007-single-tenant.md)

## Contexto

La app se usa para más de una persona: en la misma instalación se subieron el CV
de Harold y el de Erika, y todo (pipeline, simulacros, preferencias, match)
quedaba mezclado en el único usuario. Hacía falta separar los datos por persona.

Alternativas:

1. **Tabla `profiles` nueva** de la que cuelguen CV, postulaciones, etc. Obliga a
   añadir `profile_id` a cinco tablas y, sin migraciones
   ([ADR 0003](0003-sin-migraciones.md)), a un `docker compose down -v` que
   borra los datos del usuario.
2. **Login real** (cuentas, contraseñas, tokens). Desproporcionado para una
   herramienta local; lo descartó ya el ADR 0007.
3. **Reutilizar `users` como perfil** y elegirlo por cabecera.

## Decisión

Cada fila de `users` es un perfil. `get_current_user` en `app/api/deps.py` lee la
cabecera `X-Profile-Id`; sin cabecera devuelve el perfil por defecto
(`DEFAULT_USER_EMAIL`), que no se puede borrar. Un id inexistente lanza
`ProfileNotFound`, que `main.py` traduce a 404 con `code: profile_not_found`.

- El frontend guarda el perfil activo en `localStorage` (`src/lib/profile.ts`) y
  lo manda en cada petición desde `src/lib/api.ts`. Cambiar de perfil recarga la
  página.
- La extensión lo guarda en `chrome.storage.sync` y lo manda igual. "Abrir
  dossier" pasa `?perfil=<id>` para que el dashboard se ponga en el mismo.
- `POST /profiles/from-resume/{id}` separa un CV subido al perfil equivocado.
- El catálogo de vacantes (`jobs`) y la inteligencia de empresa se comparten:
  son datos del mercado, no de la persona. `job_matches` ya iba por CV.

## Razones

- **Cero cambios de esquema.** Todo colgaba ya de `user_id`; el ADR 0007 dejó
  `get_current_user` como único punto a cambiar y así ha sido.
- Los datos existentes se conservan.
- Los clientes que no conocen la cabecera (una extensión sin actualizar, scripts)
  siguen funcionando contra el perfil por defecto.

## Consecuencias

- **Sigue sin haber autenticación.** Cualquiera que alcance la API puede leer y
  borrar cualquier perfil con solo cambiar la cabecera. La API no debe exponerse
  fuera de `localhost`, igual que antes.
- `users.email` es único pero ya no identifica a nadie: los perfiles nuevos
  llevan uno sintético (`perfil-<hex>@localhost`).
- El perfil activo del dashboard y el de la extensión se guardan por separado;
  pueden no coincidir. El selector del popup lo deja a la vista.
- Si algún día hace falta login de verdad, este ADR se reemplaza: la cabecera se
  sustituye por un token y `get_current_user` lo resuelve.

## Relacionado

[ADR 0007](0007-single-tenant.md) · [API](../api.md) · [Arquitectura](../arquitectura.md)
