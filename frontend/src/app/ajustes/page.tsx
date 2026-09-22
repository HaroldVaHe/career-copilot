"use client";

import { useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  PageHeader,
  Skeleton,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Health } from "@/lib/types";

/** Campos que el autofill de la extensión no puede deducir del CV. */
const PREFERENCE_FIELDS: { key: string; label: string; placeholder: string; hint?: string }[] = [
  {
    key: "salary_expectation",
    label: "Salario pretendido",
    placeholder: "55.000 – 65.000 EUR brutos/año",
  },
  {
    key: "work_authorization",
    label: "Autorización de trabajo",
    placeholder: "Ciudadanía de la UE",
    hint: "Lo que respondes en Workday/Greenhouse a «work authorization».",
  },
  {
    key: "requires_sponsorship",
    label: "¿Necesitas patrocinio de visado?",
    placeholder: "No",
  },
  { key: "notice_period", label: "Preaviso", placeholder: "15 días" },
  { key: "preferred_pronouns", label: "Pronombres", placeholder: "elle / they" },
];

export default function AjustesPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [prefs, setPrefs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);

  useEffect(() => {
    Promise.all([api.health(), api.getPreferences()])
      .then(([h, p]) => {
        setHealth(h);
        setPrefs(p);
      })
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    try {
      setPrefs(await api.setPreferences(prefs));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  if (loading) return <Skeleton className="h-96 w-full" />;

  return (
    <>
      <PageHeader
        title="Ajustes"
        description="Estado del sistema y datos que no salen del CV pero que los formularios piden siempre."
      />

      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="Error">
            {error}
          </Alert>
        </div>
      )}

      <div className="space-y-6">
        <Card title="Estado del sistema">
          <dl className="grid gap-3 sm:grid-cols-2">
            <StatusRow
              label="Base de datos"
              ok={health?.database ?? false}
              value={health?.database ? "Conectada" : "Sin conexión"}
            />
            <StatusRow
              label="Claude"
              ok={health?.llm.configured ?? false}
              value={
                health?.llm.configured
                  ? `${health.llm.model} · effort ${health.llm.effort}`
                  : "Sin API key"
              }
            />
            <StatusRow
              label="Embeddings"
              ok
              value={`${health?.embeddings.provider} · ${health?.embeddings.dim} dimensiones`}
            />
            <StatusRow
              label="Fuentes de vacantes"
              ok={(health?.job_sources.length ?? 0) > 0}
              value={health?.job_sources.join(", ") ?? "—"}
            />
          </dl>

          {!health?.llm.configured && (
            <div className="mt-4">
              <Alert tone="warning" title="Funcionando en modo degradado">
                Sin <code className="rounded bg-surface-1 px-1">ANTHROPIC_API_KEY</code> el sistema
                parsea CVs y ofertas con heurísticas, pero no hay adaptación de CV, investigación
                de empresa, cartas ni simulacros. Añade la clave al{" "}
                <code className="rounded bg-surface-1 px-1">.env</code> de la raíz y reinicia la
                API.
              </Alert>
            </div>
          )}
        </Card>

        <Card
          title="Datos para el autofill"
          subtitle="La extensión los usa para rellenar Workday, Greenhouse, Lever y Taleo"
          actions={
            <Button variant="primary" onClick={save}>
              {saved ? "Guardado ✓" : "Guardar"}
            </Button>
          }
        >
          <div className="grid gap-3 sm:grid-cols-2">
            {PREFERENCE_FIELDS.map((field) => (
              <Field key={field.key} label={field.label} hint={field.hint}>
                <Input
                  value={prefs[field.key] ?? ""}
                  onChange={(e) => setPrefs({ ...prefs, [field.key]: e.target.value })}
                  placeholder={field.placeholder}
                />
              </Field>
            ))}
          </div>
        </Card>

        <Card title="Extensión de navegador">
          <p className="text-sm text-ink-secondary">
            LinkedIn, Indeed y Glassdoor prohíben el scraping en sus términos de uso. La extensión
            es la vía soportada: lee la oferta que ya tienes abierta en tu propia sesión, calcula
            el match al instante y rellena los formularios.
          </p>
          <ol className="mt-3 space-y-1.5 text-sm text-ink-secondary">
            <li>
              1. Abre <code className="rounded bg-surface-2 px-1">chrome://extensions</code> y
              activa el modo desarrollador.
            </li>
            <li>
              2. «Cargar descomprimida» →{" "}
              <code className="rounded bg-surface-2 px-1">career-copilot/extension</code>
            </li>
            <li>3. Navega a una oferta y pulsa el icono de la extensión.</li>
          </ol>
        </Card>

        <Card title="Mantenimiento">
          <p className="mb-3 text-sm text-ink-secondary">
            Recalcula los embeddings de todos los CVs y vacantes. Necesario tras cambiar{" "}
            <code className="rounded bg-surface-2 px-1">EMBEDDING_PROVIDER</code> en el{" "}
            <code className="rounded bg-surface-2 px-1">.env</code>.
          </p>
          <Button
            onClick={async () => {
              setReindexing(true);
              await api.reindex();
              setTimeout(() => setReindexing(false), 3000);
            }}
            loading={reindexing}
          >
            Reindexar
          </Button>
        </Card>
      </div>
    </>
  );
}

function StatusRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
      <dt className="text-sm text-ink-secondary">{label}</dt>
      <dd>
        <Badge tone={ok ? "good" : "warning"} icon>
          {value}
        </Badge>
      </dd>
    </div>
  );
}
