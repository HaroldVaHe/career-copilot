/**
 * Service worker: solo guarda la URL de la API y comprueba que responde.
 * Toda la lógica vive en el popup, que es donde hay interacción del usuario.
 */

const DEFAULT_API = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(async () => {
  const { apiUrl } = await chrome.storage.sync.get("apiUrl");
  if (!apiUrl) {
    await chrome.storage.sync.set({ apiUrl: DEFAULT_API });
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "ping") {
    chrome.storage.sync.get("apiUrl").then(async ({ apiUrl }) => {
      const base = apiUrl || DEFAULT_API;
      try {
        const res = await fetch(`${base}/api/v1/capture/ping`);
        sendResponse({ ok: res.ok, data: await res.json() });
      } catch (error) {
        sendResponse({ ok: false, error: String(error) });
      }
    });
    return true; // respuesta asíncrona
  }
  return false;
});
