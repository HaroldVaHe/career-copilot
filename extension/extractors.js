/**
 * Extractores de oferta por portal.
 *
 * Se inyectan en la pestaña activa cuando el usuario pulsa el botón, y leen el
 * DOM que YA está renderizado en su sesión. No hay peticiones a los servidores
 * del portal, no hay credenciales, no hay crawling: es el equivalente a copiar
 * y pegar, automatizado.
 *
 * Orden de preferencia:
 *   1. JSON-LD `JobPosting` (schema.org) — lo publican Greenhouse, Lever,
 *      Workable, Ashby, Google Jobs y buena parte de los ATS. Es lo más fiable.
 *   2. Selectores específicos del portal.
 *   3. Heurística genérica sobre el bloque de texto más largo de la página.
 */

function textOf(selectors, root = document) {
  for (const selector of selectors) {
    const node = root.querySelector(selector);
    const value = node?.innerText?.trim();
    if (value) return value;
  }
  return "";
}

function htmlOf(selectors, root = document) {
  for (const selector of selectors) {
    const node = root.querySelector(selector);
    if (node?.innerText?.trim()) return node.innerHTML;
  }
  return "";
}

/** schema.org/JobPosting incrustado en la página. */
function fromJsonLd() {
  const blocks = document.querySelectorAll('script[type="application/ld+json"]');
  for (const block of blocks) {
    let parsed;
    try {
      parsed = JSON.parse(block.textContent);
    } catch {
      continue;
    }
    const candidates = Array.isArray(parsed) ? parsed : [parsed, ...(parsed["@graph"] ?? [])];
    for (const item of candidates) {
      if (!item || item["@type"] !== "JobPosting") continue;

      const location =
        item.jobLocation?.address?.addressLocality ??
        item.jobLocation?.[0]?.address?.addressLocality ??
        (item.jobLocationType === "TELECOMMUTE" ? "Remoto" : "");

      return {
        title: item.title ?? "",
        company: item.hiringOrganization?.name ?? "",
        location: [location, item.jobLocation?.address?.addressCountry]
          .filter(Boolean)
          .join(", "),
        description_html: item.description ?? "",
        description_text: "",
      };
    }
  }
  return null;
}

const SITE_EXTRACTORS = [
  {
    match: /linkedin\.com/,
    source: "linkedin",
    run: () => ({
      title: textOf([
        ".job-details-jobs-unified-top-card__job-title",
        ".jobs-unified-top-card__job-title",
        ".top-card-layout__title",
        "h1",
      ]),
      company: textOf([
        ".job-details-jobs-unified-top-card__company-name",
        ".jobs-unified-top-card__company-name",
        ".topcard__org-name-link",
      ]),
      location: textOf([
        ".job-details-jobs-unified-top-card__primary-description-container span:first-child",
        ".jobs-unified-top-card__bullet",
        ".topcard__flavor--bullet",
      ]),
      description_html: htmlOf([
        ".jobs-description__content",
        "#job-details",
        ".description__text",
        ".show-more-less-html__markup",
      ]),
    }),
  },
  {
    match: /indeed\./,
    source: "indeed",
    run: () => ({
      title: textOf(['[data-testid="jobsearch-JobInfoHeader-title"]', ".jobsearch-JobInfoHeader-title", "h1"]),
      company: textOf(['[data-testid="inlineHeader-companyName"]', '[data-company-name="true"]']),
      location: textOf(['[data-testid="inlineHeader-companyLocation"]', '[data-testid="job-location"]']),
      description_html: htmlOf(["#jobDescriptionText", ".jobsearch-jobDescriptionText"]),
    }),
  },
  {
    match: /glassdoor\./,
    source: "glassdoor",
    run: () => ({
      title: textOf(['[data-test="job-title"]', ".JobDetails_jobTitle__*", "h1"]),
      company: textOf(['[data-test="employer-name"]', ".EmployerProfile_employerName__*"]),
      location: textOf(['[data-test="location"]']),
      description_html: htmlOf(['[class*="JobDetails_jobDescription"]', "#JobDescriptionContainer"]),
    }),
  },
  {
    match: /myworkdayjobs\.com|workday/,
    source: "workday",
    run: () => ({
      title: textOf(['[data-automation-id="jobPostingHeader"]', "h1"]),
      company: document.title.split("-").pop()?.trim() ?? "",
      location: textOf(['[data-automation-id="locations"]', '[data-automation-id="location"]']),
      description_html: htmlOf(['[data-automation-id="jobPostingDescription"]']),
    }),
  },
  {
    match: /greenhouse\.io|boards\.greenhouse/,
    source: "greenhouse",
    run: () => ({
      title: textOf([".app-title", "h1.section-header", "h1"]),
      company: textOf([".company-name", "#header .company-name"]).replace(/^at\s+/i, ""),
      location: textOf([".location", ".job__location"]),
      description_html: htmlOf(["#content", ".job__description"]),
    }),
  },
  {
    match: /lever\.co/,
    source: "lever",
    run: () => ({
      title: textOf([".posting-headline h2", "h2"]),
      company: textOf([".main-header-logo img"]) || document.title.split("-")[0].trim(),
      location: textOf([".posting-categories .location", ".sort-by-time"]),
      description_html: htmlOf([".section-wrapper.page-full-width", ".posting-page"]),
    }),
  },
  {
    match: /taleo\.net|tal\.net/,
    source: "taleo",
    run: () => ({
      title: textOf([".title", "h1"]),
      company: document.title.split("|").pop()?.trim() ?? "",
      location: textOf([".location"]),
      description_html: htmlOf([".jobdescription", "#requisitionDescriptionInterface"]),
    }),
  },
];

/** Último recurso: el contenedor con más texto de la página. */
function genericExtract() {
  let best = null;
  let bestLength = 0;
  for (const node of document.querySelectorAll("article, main, section, div")) {
    const length = node.innerText?.length ?? 0;
    // Un contenedor con muchos hijos suele ser el layout, no la descripción.
    if (length > bestLength && length > 400 && node.children.length < 80) {
      best = node;
      bestLength = length;
    }
  }
  return {
    title: textOf(["h1", '[class*="title"]']) || document.title,
    company: "",
    location: "",
    description_html: best?.innerHTML ?? "",
    description_text: best?.innerText ?? "",
  };
}

/** Punto de entrada que inyecta el popup. Devuelve el payload de /capture. */
function extractJobPosting() {
  const site = SITE_EXTRACTORS.find((entry) => entry.match.test(location.hostname));
  const structured = fromJsonLd();
  const specific = site ? site.run() : {};
  const generic = genericExtract();

  const pick = (key) =>
    (specific[key] || "").trim() || (structured?.[key] || "").trim() || (generic[key] || "").trim();

  return {
    url: location.href.split("?")[0],
    title: pick("title"),
    company: pick("company"),
    location: pick("location"),
    description_html: pick("description_html"),
    description_text: specific.description_html || structured?.description_html
      ? ""
      : generic.description_text,
    source: site?.source ?? "extension",
  };
}

// `chrome.scripting.executeScript` evalúa el último valor del archivo.
extractJobPosting();
