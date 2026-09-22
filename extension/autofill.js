/**
 * Autofill de formularios de postulación (Workday, Greenhouse, Lever, Taleo…).
 *
 * Dos decisiones deliberadas:
 *  - Solo rellena campos VACÍOS. Nunca pisa algo que el usuario ya escribió.
 *  - No envía el formulario. El disparo del submit es siempre humano: un envío
 *    automático con una respuesta desalineada te quema la candidatura, y en
 *    algunos portales la cuenta.
 *
 * Devuelve el recuento de campos rellenados y los que no supo mapear, para que
 * el popup diga exactamente qué queda por revisar a mano.
 */

const FIELD_PATTERNS = [
  { key: "first_name", patterns: [/first\s*name/i, /nombre\b(?!.*complet)/i, /given\s*name/i] },
  { key: "last_name", patterns: [/last\s*name/i, /apellidos?/i, /family\s*name/i, /surname/i] },
  { key: "full_name", patterns: [/full\s*name/i, /nombre\s*completo/i, /^name$/i] },
  { key: "email", patterns: [/e-?mail/i, /correo/i] },
  { key: "phone", patterns: [/phone/i, /tel[eé]fono/i, /mobile/i, /celular/i] },
  { key: "location", patterns: [/city/i, /ciudad/i, /location/i, /ubicaci[oó]n/i, /address/i] },
  { key: "linkedin", patterns: [/linkedin/i] },
  { key: "github", patterns: [/github/i] },
  { key: "portfolio", patterns: [/portfolio/i, /website/i, /sitio\s*web/i, /personal\s*site/i] },
  {
    key: "years_experience",
    patterns: [/years?\s*(of\s*)?experience/i, /a[ñn]os\s*de\s*experiencia/i],
  },
  { key: "current_company", patterns: [/current\s*(employer|company)/i, /empresa\s*actual/i] },
  { key: "current_role", patterns: [/current\s*(title|role|position)/i, /puesto\s*actual/i] },
  {
    key: "salary_expectation",
    patterns: [
      /salary\s*(expectation|requirement)/i,
      /expected\s*(salary|compensation)/i,
      /pretensi[oó]n\s*salarial/i,
      /salario\s*(deseado|pretendido)/i,
    ],
  },
  {
    key: "work_authorization",
    patterns: [/work\s*authoriz/i, /legally\s*authorized/i, /autorizaci[oó]n\s*(de|para)\s*trabaj/i],
  },
  {
    key: "requires_sponsorship",
    patterns: [/sponsorship/i, /visa\s*support/i, /patrocinio/i],
  },
  { key: "notice_period", patterns: [/notice\s*period/i, /preaviso/i, /disponibilidad/i] },
  { key: "preferred_pronouns", patterns: [/pronouns?/i, /pronombres?/i] },
];

/** Todo el texto que identifica un campo: label, aria, name, id, placeholder. */
function describe(input) {
  const parts = [
    input.getAttribute("aria-label"),
    input.getAttribute("placeholder"),
    input.getAttribute("name"),
    input.getAttribute("id"),
    input.getAttribute("data-automation-id"),
  ];

  const id = input.getAttribute("id");
  if (id) {
    const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
    if (label) parts.push(label.innerText);
  }
  parts.push(input.closest("label")?.innerText);

  // Workday y varios ATS ponen la etiqueta en un contenedor hermano.
  let ancestor = input.parentElement;
  for (let depth = 0; ancestor && depth < 3; depth += 1) {
    const label = ancestor.querySelector("label, legend, .field-label, [class*='label']");
    if (label && label.innerText.length < 120) parts.push(label.innerText);
    ancestor = ancestor.parentElement;
  }

  return parts.filter(Boolean).join(" | ");
}

function setValue(input, value) {
  // React y Angular escuchan el setter nativo; asignar `.value` a secas no
  // dispara su estado interno y el campo se vacía al primer re-render.
  const prototype =
    input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : input instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  if (setter) setter.call(input, value);
  else input.value = value;

  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  input.dispatchEvent(new Event("blur", { bubbles: true }));
}

function fillSelect(select, value) {
  const wanted = String(value).toLowerCase();
  for (const option of select.options) {
    const text = option.text.toLowerCase();
    if (text === wanted || text.includes(wanted) || wanted.includes(text)) {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }
  }
  return false;
}

function autofillForm(profile) {
  const filled = [];
  const skipped = [];
  const unmatched = [];

  const inputs = document.querySelectorAll(
    "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=file]), textarea, select",
  );

  for (const input of inputs) {
    if (input.disabled || input.readOnly) continue;
    if (input.type === "checkbox" || input.type === "radio") continue;

    const haystack = describe(input);
    if (!haystack) continue;

    const entry = FIELD_PATTERNS.find((field) =>
      field.patterns.some((pattern) => pattern.test(haystack)),
    );
    if (!entry) {
      if (input.offsetParent !== null && !input.value) {
        unmatched.push(haystack.split("|")[0].trim().slice(0, 60));
      }
      continue;
    }

    const value = profile[entry.key];
    if (!value) continue;

    if (input.value && input.value.trim()) {
      skipped.push(entry.key); // ya tenía contenido: no se toca
      continue;
    }

    if (input.tagName === "SELECT") {
      if (fillSelect(input, value)) filled.push(entry.key);
      continue;
    }

    setValue(input, String(value));
    input.style.outline = "2px solid #2a78d6";
    input.style.outlineOffset = "1px";
    filled.push(entry.key);
  }

  return {
    filled: [...new Set(filled)],
    skipped: [...new Set(skipped)],
    unmatched: [...new Set(unmatched)].slice(0, 8),
  };
}

// El popup inyecta este archivo y después llama a la función con el perfil.
// Se registra en `window` porque `executeScript({files})` no acepta argumentos.
window.__careerCopilotAutofill = autofillForm;
