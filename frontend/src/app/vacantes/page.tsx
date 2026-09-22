"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ScoreRing } from "@/components/charts";
import {
  Alert,
  Badge,
  Button,
  Card,
  Chip,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  Textarea,
  formatDate,
  formatMoney,
} from "@/components/ui";
import { api, ApiError, type JobSearchQuery } from "@/lib/api";
import type { JobWithMatch } from "@/lib/types";

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remoto",
  hybrid: "Híbrido",
  onsite: "Presencial",
  unknown: "Sin indicar",
};

export default function VacantesPage() {
  const [results, setResults] = useState<JobWithMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);

  const [query, setQuery] = useState<JobSearchQuery>({ sort: "score", limit: 50 });
  const [text, setText] = useState("");
  const [semantic, setSemantic] = useState("");
  const [minScore, setMinScore] = useState<string>("");
  const [remote, setRemote] = useState<string>("");
  const [days, setDays] = useState<string>("");
  const [skills, setSkills] = useState("");

  const search = useCallback(async (payload: JobSearchQuery) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.searchJobs(payload);
      setResults(response.results);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.searchJobs(query);
        if (!cancelled) setResults(response.results);
      } catch (e) {
        if (!cancelled) setError((e as ApiError).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [query]);

  const applyFilters = () => {
    setQuery({
      sort: semantic ? "score" : query.sort,
      limit: 50,
      q: text || undefined,
      semantic: semantic || undefined,
      min_score: minScore ? Number(minScore) : undefined,
      remote_type: remote ? [remote] : undefined,
      posted_within_days: days ? Number(days) : undefined,
      required_skills: skills
        ? skills.split(",").map((s) => s.trim()).filter(Boolean)
        : undefined,
    });
  };

  const clear = () => {
    setText("");
    setSemantic("");
    setMinScore("");
    setRemote("");
    setDays("");
    setSkills("");
    setQuery({ sort: "score", limit: 50 });
  };

  return (
    <>
      <PageHeader
        title="Vacantes"
        description="Agregación de fuentes públicas, búsqueda por significado y match score contra tu CV."
        actions={
          <>
            <Button onClick={() => setManualOpen(true)}>Pegar una oferta</Button>
            <Button variant="primary" onClick={() => setIngestOpen(true)}>
              Importar vacantes
            </Button>
          </>
        }
      />

      <Card className="mb-6">
        {/* Los filtros van en una sola fila por encima de los resultados. */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Texto literal">
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilters()}
              placeholder="backend, react…"
            />
          </Field>
          <Field label="Búsqueda por significado">
            <Input
              value={semantic}
              onChange={(e) => setSemantic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilters()}
              placeholder="APIs escalables en la nube"
            />
          </Field>
          <Field label="Match mínimo">
            <Select value={minScore} onChange={(e) => setMinScore(e.target.value)}>
              <option value="">Cualquiera</option>
              <option value="50">50% o más</option>
              <option value="65">65% o más</option>
              <option value="80">80% o más</option>
            </Select>
          </Field>
          <Field label="Modalidad">
            <Select value={remote} onChange={(e) => setRemote(e.target.value)}>
              <option value="">Todas</option>
              <option value="remote">Remoto</option>
              <option value="hybrid">Híbrido</option>
              <option value="onsite">Presencial</option>
            </Select>
          </Field>
          <Field label="Publicadas hace">
            <Select value={days} onChange={(e) => setDays(e.target.value)}>
              <option value="">Sin límite</option>
              <option value="3">3 días</option>
              <option value="7">7 días</option>
              <option value="30">30 días</option>
            </Select>
          </Field>
          <Field label="Tecnologías obligatorias" hint="Separadas por coma">
            <Input
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder="Python, Kubernetes"
            />
          </Field>
          <Field label="Ordenar por">
            <Select
              value={query.sort}
              onChange={(e) =>
                setQuery({ ...query, sort: e.target.value as JobSearchQuery["sort"] })
              }
            >
              <option value="score">Match score</option>
              <option value="date">Más recientes</option>
              <option value="salary">Mejor pagadas</option>
            </Select>
          </Field>
          <div className="flex items-end gap-2">
            <Button variant="primary" onClick={applyFilters}>
              Filtrar
            </Button>
            <Button variant="ghost" onClick={clear}>
              Limpiar
            </Button>
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="Error en la búsqueda">
            {error}
          </Alert>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : results.length === 0 ? (
        <EmptyState
          title="No hay vacantes que cumplan el filtro"
          description="Importa ofertas de las fuentes públicas o pega una manualmente."
          action={
            <Button variant="primary" onClick={() => setIngestOpen(true)}>
              Importar vacantes
            </Button>
          }
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-ink-secondary">{results.length} vacantes</p>
          <ul className="space-y-3">
            {results.map(({ job, match }) => (
              <li key={job.id}>
                <Link href={`/vacantes/${job.id}`} className="block">
                  <article className="rounded-xl border bg-surface-1 p-4 transition-colors hover:bg-surface-2">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate text-sm font-semibold text-ink">{job.title}</h3>
                        <p className="mt-0.5 truncate text-sm text-ink-secondary">
                          {job.company}
                          {job.location && ` · ${job.location}`}
                        </p>

                        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                          <Badge tone="neutral">{REMOTE_LABELS[job.remote_type]}</Badge>
                          {job.seniority && <Badge tone="neutral">{job.seniority}</Badge>}
                          {job.salary_max ? (
                            <Badge tone="good">
                              {formatMoney(job.salary_min, job.salary_currency)} –{" "}
                              {formatMoney(job.salary_max, job.salary_currency)}
                            </Badge>
                          ) : null}
                          <span className="text-xs text-ink-muted">
                            {job.source} · {formatDate(job.posted_at ?? job.created_at)}
                          </span>
                        </div>

                        {match && match.matched_skills.length > 0 && (
                          <div className="mt-2.5 flex flex-wrap gap-1.5">
                            {match.matched_skills.slice(0, 6).map((skill) => (
                              <Chip key={skill} tone="good">
                                {skill}
                              </Chip>
                            ))}
                            {match.missing_skills.slice(0, 3).map((skill) => (
                              <Chip key={skill} tone="critical">
                                falta {skill}
                              </Chip>
                            ))}
                          </div>
                        )}
                      </div>

                      {match && (
                        <div className="shrink-0">
                          <ScoreRing value={match.score} />
                        </div>
                      )}
                    </div>
                  </article>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      <IngestModal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        onDone={() => search(query)}
      />
      <ManualJobModal
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        onDone={() => search(query)}
      />
    </>
  );
}

function IngestModal({
  open,
  onClose,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [term, setTerm] = useState("");
  const [limit, setLimit] = useState("30");
  const [analyze, setAnalyze] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<
    { source: string; fetched?: number; created?: number; error?: string }[] | null
  >(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    if (open) api.sources().then((s) => setNote(s.note)).catch(() => {});
  }, [open]);

  const run = async () => {
    setLoading(true);
    try {
      const response = await api.ingest({
        query: term,
        limit: Number(limit),
        analyze,
      });
      setResult(response.results);
      onDone();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Importar vacantes">
      <div className="space-y-4">
        <Field label="Término de búsqueda" hint="Vacío = trae lo último de cada fuente.">
          <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="python" />
        </Field>
        <Field label="Máximo por fuente">
          <Select value={limit} onChange={(e) => setLimit(e.target.value)}>
            <option value="10">10</option>
            <option value="30">30</option>
            <option value="60">60</option>
            <option value="100">100</option>
          </Select>
        </Field>
        <label className="flex items-start gap-2 text-sm text-ink-secondary">
          <input
            type="checkbox"
            className="mt-1"
            checked={analyze}
            onChange={(e) => setAnalyze(e.target.checked)}
          />
          <span>
            Analizar cada oferta con Claude al importar
            <span className="block text-xs text-ink-muted">
              Más preciso, pero lento y con costo por token. Sin marcar se usa la extracción
              heurística y puedes analizar en detalle solo las que te interesen.
            </span>
          </span>
        </label>

        {note && (
          <Alert tone="neutral" title="Sobre LinkedIn, Indeed y Glassdoor">
            {note}
          </Alert>
        )}

        {result && (
          <ul className="space-y-1 text-sm">
            {result.map((item) => (
              <li key={item.source} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{ background: item.error ? "var(--critical)" : "var(--good)" }}
                />
                <span className="text-ink">{item.source}:</span>
                <span className="text-ink-secondary">
                  {item.error ?? `${item.created} nuevas de ${item.fetched}`}
                </span>
              </li>
            ))}
          </ul>
        )}

        <Button variant="primary" onClick={run} loading={loading}>
          Importar
        </Button>
      </div>
    </Modal>
  );
}

function ManualJobModal({
  open,
  onClose,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.createJob({
        title,
        company,
        url: url || null,
        description_raw: description,
        analyze: true,
      });
      onDone();
      onClose();
      setTitle("");
      setCompany("");
      setUrl("");
      setDescription("");
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Pegar una oferta" wide>
      <div className="space-y-4">
        {error && (
          <Alert tone="critical" title="No se pudo guardar">
            {error}
          </Alert>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Puesto">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Empresa">
            <Input value={company} onChange={(e) => setCompany(e.target.value)} />
          </Field>
        </div>
        <Field label="URL de la oferta">
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
        </Field>
        <Field
          label="Descripción completa"
          hint="Claude extrae requisitos, salario, modalidad y red flags."
        >
          <Textarea
            rows={12}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <Button
          variant="primary"
          onClick={save}
          loading={loading}
          disabled={description.trim().length < 50}
        >
          Guardar y analizar
        </Button>
      </div>
    </Modal>
  );
}
