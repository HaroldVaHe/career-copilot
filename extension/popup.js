const DEFAULT_API = "http://localhost:8000";
const RING_CIRCUMFERENCE = 2 * Math.PI * 22;

const $ = (id) => document.getElementById(id);

let apiUrl = DEFAULT_API;
let capturedJobId = null;

/* -------------------------------------------------------------------------- */
async function api(path, options = {}) {
  const res = await fetch(`${apiUrl}/api/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(payload?.detail ?? `Error ${res.status}`);
  }
  return payload;
}

function showError(message) {
  const node = $("error");
  node.textContent = message;
  node.classList.toggle("hidden", !message);
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

/* -------------------------------------------------------------------------- */
async function init() {
  const stored = await chrome.storage.sync.get("apiUrl");
  apiUrl = stored.apiUrl || DEFAULT_API;
  $("api-url").value = apiUrl;

  try {
    const health = await api("/capture/ping");
    $("status").textContent = health.llm
      ? `Conectado · ${health.user}`
      : `Conectado · sin API key de Claude`;
    $("status").className = "status ok";
  } catch {
    $("status").textContent = "API sin conexión";
    $("status").className = "status bad";
    showError(
      `No se pudo hablar con ${apiUrl}. Arranca el backend o corrige la URL en ajustes.`,
    );
  }
}

$("settings-toggle").addEventListener("click", () => {
  $("settings").classList.toggle("hidden");
});

$("save-settings").addEventListener("click", async () => {
  apiUrl = $("api-url").value.replace(/\/$/, "") || DEFAULT_API;
  await chrome.storage.sync.set({ apiUrl });
  showError("");
  init();
});

/* -------------------------------------------------------------------------- */
$("capture").addEventListener("click", async () => {
  const button = $("capture");
  button.disabled = true;
  button.textContent = "Leyendo la página…";
  showError("");

  try {
    const tab = await activeTab();
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["extractors.js"],
    });
    const payload = injected?.result;

    if (!payload || (!payload.description_html && !payload.description_text)) {
      throw new Error(
        "No se encontró la descripción. Abre la oferta completa (no el listado) y reintenta.",
      );
    }

    button.textContent = "Analizando con Claude…";
    const response = await api("/capture", {
      method: "POST",
      body: JSON.stringify({ ...payload, analyze: true }),
    });

    renderCapture(response);
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Capturar esta oferta";
  }
});

function renderCapture(response) {
  const { job, match, application_id } = response;
  capturedJobId = job.id;

  $("result").classList.remove("hidden");
  $("job-title").textContent = job.title || "(sin título)";
  $("job-company").textContent = [job.company, job.location].filter(Boolean).join(" · ");

  if (match) {
    $("score-box").classList.remove("hidden");
    $("score-value").textContent = Math.round(match.score);
    $("ring-fill").style.strokeDashoffset = String(
      RING_CIRCUMFERENCE * (1 - Math.min(100, match.score) / 100),
    );
    $("ring-fill").style.stroke = toneFor(match.score);
    $("score-detail").textContent =
      `${match.matched_skills.length} requisitos cumplidos · ${match.missing_skills.length} pendientes`;

    $("skills").innerHTML = "";
    for (const skill of match.matched_skills.slice(0, 8)) {
      $("skills").appendChild(chip(skill, "have"));
    }
    for (const skill of match.missing_skills.slice(0, 5)) {
      $("skills").appendChild(chip(`falta ${skill}`, "missing"));
    }
  }

  const saveButton = $("save-pipeline");
  if (application_id) {
    saveButton.textContent = "Ya está en el pipeline";
    saveButton.disabled = true;
  } else {
    saveButton.textContent = "Guardar en el pipeline";
    saveButton.disabled = false;
  }
}

function chip(text, variant) {
  const node = document.createElement("span");
  node.className = `chip ${variant}`;
  node.textContent = text;
  return node;
}

function toneFor(score) {
  if (score >= 75) return "var(--good)";
  if (score >= 55) return "var(--warning)";
  return "var(--critical)";
}

$("save-pipeline").addEventListener("click", async () => {
  if (!capturedJobId) return;
  const button = $("save-pipeline");
  button.disabled = true;
  button.textContent = "Guardando…";
  try {
    await api("/applications", {
      method: "POST",
      body: JSON.stringify({ job_id: capturedJobId, generate_tasks: true }),
    });
    button.textContent = "Guardada ✓";
  } catch (error) {
    showError(error.message);
    button.disabled = false;
    button.textContent = "Guardar en el pipeline";
  }
});

$("open-app").addEventListener("click", () => {
  if (!capturedJobId) return;
  // El dashboard vive en 3000; la API en 8000.
  const dashboard = apiUrl.replace(/:\d+$/, ":3000");
  chrome.tabs.create({ url: `${dashboard}/vacantes/${capturedJobId}` });
});

/* -------------------------------------------------------------------------- */
$("autofill").addEventListener("click", async () => {
  const button = $("autofill");
  button.disabled = true;
  showError("");
  $("autofill-result").textContent = "Leyendo tu perfil…";

  try {
    const profile = await api("/capture/autofill");
    const tab = await activeTab();

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["autofill.js"],
    });
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (data) => window.__careerCopilotAutofill(data),
      args: [profile],
    });

    const result = injected?.result ?? { filled: [], skipped: [], unmatched: [] };
    const parts = [`${result.filled.length} campos rellenados`];
    if (result.skipped.length) parts.push(`${result.skipped.length} ya tenían valor`);
    if (result.unmatched.length) {
      parts.push(`sin mapear: ${result.unmatched.slice(0, 3).join(", ")}`);
    }
    $("autofill-result").textContent = `${parts.join(" · ")}. Revisa antes de enviar.`;
  } catch (error) {
    $("autofill-result").textContent = "";
    showError(error.message);
  } finally {
    button.disabled = false;
  }
});

/* -------------------------------------------------------------------------- */
$("answer").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (!question) return;

  const button = $("answer");
  button.disabled = true;
  button.textContent = "Redactando…";
  showError("");

  try {
    const response = await api("/capture/answer", {
      method: "POST",
      body: JSON.stringify({ question, job_id: capturedJobId }),
    });
    $("answer-box").classList.remove("hidden");
    $("answer-text").textContent = response.answer;
    $("copy-answer").textContent =
      response.source === "knowledge_base" ? "Copiar (reutilizada)" : "Copiar";
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Redactar respuesta";
  }
});

$("copy-answer").addEventListener("click", async () => {
  await navigator.clipboard.writeText($("answer-text").textContent ?? "");
  $("copy-answer").textContent = "Copiado ✓";
});

init();
