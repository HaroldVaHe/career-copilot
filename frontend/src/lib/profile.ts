/**
 * Perfil activo. Se guarda en localStorage y viaja en cada petición como
 * `X-Profile-Id`; sin él, el backend usa el perfil por defecto.
 *
 * Cambiar de perfil recarga la página: así todas las pantallas vuelven a pedir
 * sus datos con el perfil nuevo sin tener que coordinar estado global.
 */

const KEY = "profileId";

export function getActiveProfileId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY);
  const id = raw ? Number(raw) : NaN;
  return Number.isInteger(id) && id > 0 ? id : null;
}

export function setActiveProfileId(id: number | null) {
  if (id == null) window.localStorage.removeItem(KEY);
  else window.localStorage.setItem(KEY, String(id));
}

/**
 * Enlaces desde la extensión llegan con `?perfil=<id>`. Si difiere del activo,
 * se adopta y se recarga sin el parámetro. Devuelve true si va a recargar.
 */
export function adoptProfileFromUrl(): boolean {
  const url = new URL(window.location.href);
  const raw = url.searchParams.get("perfil");
  if (!raw) return false;
  url.searchParams.delete("perfil");
  const id = Number(raw);
  if (Number.isInteger(id) && id > 0 && id !== getActiveProfileId()) {
    setActiveProfileId(id);
    window.location.replace(url.toString());
    return true;
  }
  window.history.replaceState(null, "", url.toString());
  return false;
}

export function switchProfile(id: number | null, redirect?: string) {
  setActiveProfileId(id);
  if (redirect) window.location.assign(redirect);
  else window.location.reload();
}
