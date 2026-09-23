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
import type {
  IngestResponse,
  JobWithMatch,
  ResumeSummary,
  SearchPlan,
  SourceInfo,
} from "@/lib/types";

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

  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [resumeId, setResumeId] = useState<number | undefined>(undefined);
  // La búsqueda espera a saber qué CV usar: así sale una sola petición y no una
  // sin CV seguida de otra con CV.
  const [resumesReady, setResumesReady] = useState(false);

  const [query, setQuery] = useState<JobSearchQuery>({ sort: "score", limit: 50 });
  const [text, setText] = useState("");
  const [semantic, setSemantic] = useState("");
  const [minScore, setMinScore] = useState<string>("");
  const [remote, setRemote] = useState<string>("");
  const [days, setDays] = useState<string>("");
  const [skills, setSkills] = useState("");
  const [country, setCountry] = useState("");

  useEffect(() => {
    api
      .listResumes()
      .then((list) => {
        setResumes(list);
        setResumeId((list.find((r) => r.is_primary) ?? list[0])?.id);
      })
      .catch(() => {})
      .finally(() => setResumesReady(true));
  }, []);

  const search = useCallback(
    async (payload: JobSearchQuery) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.searchJobs(payload, resumeId);
        setResults(response.results);
      } catch (e) {
        setError((e as ApiError).message);
      } finally {
        setLoading(false);
      }
    },
    [resumeId],
  );

  useEffect(() => {
    if (!resumesReady) return;
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.searchJobs(query, resumeId, controller.signal);
        setResults(response.results);
      } catch (e) {
        if (!controller.signal.aborted) setError((e as ApiError).message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    // Cancela de verdad la petición anterior al cambiar filtros o CV.
    return () => controller.abort();
  }, [query, resumeId, resumesReady]);

  const buildQuery = (overrides: Partial<JobSearchQuery> = {}): JobSearchQuery => ({
    sort: semantic ? "score" : query.sort,
    limit: 50,
    q: text || undefined,
    semantic: semantic || undefined,
    min_score: minScore ? Number(minScore) : undefined,
    remote_type: remote ? [remote] : undefined,
    posted_within_days: days ? Number(days) : undefined,
    country: country.trim() || undefined,
    required_skills: skills
      ? skills.split(",").map((s) => s.trim()).filter(Boolean)
      : undefined,
    ...overrides,
  });

  const applyFilters = () => setQuery(buildQuery());

  const clear = () => {
    setText("");
    setSemantic("");
    setMinScore("");
    setRemote("");
    setDays("");
    setSkills("");
    setCountry("");
    setQuery({ sort: "score", limit: 50 });
  };

  return (
    <>
      <PageHeader
        title="Vacantes"
        description="Bolsas globales filtradas por el país donde vives, búsqueda por significado y match score contra el CV que elijas."
        actions={
          <>
            <Button onClick={() => setManualOpen(true)}>Pegar una oferta</Button>
            <Button variant="primary" onClick={() => setIngestOpen(true)}>
              Buscar vacantes para un CV
            </Button>
          </>
        }
      />

      <Card className="mb-6">
        {/* Los filtros van en una sola fila por encima de los resultados. */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="CV para el match">
            <Select
              value={resumeId ?? ""}
              onChange={(e) => setResumeId(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full"
              disabled={resumes.length === 0}
            >
              {resumes.length === 0 && <option value="">Sin CV en este perfil</option>}
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.is_primary ? "★ " : ""}
                  {r.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Puedo postular desde" hint="País: incluye su región y «worldwide»">
            <Input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilters()}
              placeholder="Colombia, España…"
            />
          </Field>
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

      {/* Se monta solo al abrir: así cada apertura empieza con el estado limpio. */}
      {ingestOpen && (
        <IngestModal
          open
          onClose={() => setIngestOpen(false)}
          resumes={resumes}
          initialResumeId={resumeId}
          onDone={(usedResumeId, usedCountry) => {
            // Tras importar para un CV, el listado se pone en ese CV y ese país:
            // es exactamente lo que el usuario acaba de pedir.
            if (usedResumeId) setResumeId(usedResumeId);
            setCountry(usedCountry);
            setQuery(buildQuery({ country: usedCountry || undefined, sort: "score" }));
          }}
        />
      )}
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
  resumes,
  initialResumeId,
}: {
  open: boolean;
  onClose: () => void;
  onDone: (resumeId: number | undefined, country: string) => void;
  resumes: ResumeSummary[];
  initialResumeId?: number;
}) {
  const [mode, setMode] = useState<"cv" | "free">(resumes.length ? "cv" : "free");
  const [resumeId, setResumeId] = useState<number | undefined>(
    initialResumeId ?? resumes[0]?.id,
  );
  const [plan, setPlan] = useState<SearchPlan | null>(null);
  const [queries, setQueries] = useState("");
  const [country, setCountry] = useState("");
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState("20");
  const [analyze, setAnalyze] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    api
      .sources()
      .then((s) => {
        setNote(s.note);
        setSources(s.details);
        setSelected(new Set(s.details.filter((d) => d.default).map((d) => d.name)));
      })
      .catch(() => {});
  }, []);

  const applyPlan = (next: SearchPlan) => {
    setPlan(next);
    setQueries(next.queries.join(", "));
    setCountry(next.country);
  };

  useEffect(() => {
    if (mode !== "cv" || !resumeId) return;
    let cancelled = false;
    api
      .searchPlan(resumeId)
      .then((next) => !cancelled && applyPlan(next))
      .catch((e: ApiError) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [mode, resumeId]);

  // Mientras no haya plan para el CV elegido, se está calculando.
  const planLoading = mode === "cv" && !!resumeId && plan?.resume_id !== resumeId && !error;

  const suggestAgain = () => {
    if (!resumeId) return;
    setPlan(null);
    setError(null);
    api
      .searchPlan(resumeId, true)
      .then(applyPlan)
      .catch((e: ApiError) => setError(e.message));
  };

  const queryList = queries
    .split(",")
    .map((q) => q.trim())
    .filter(Boolean);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.ingest({
        sources: [...selected],
        queries: queryList,
        country,
        resume_id: mode === "cv" ? resumeId : undefined,
        limit: Number(limit),
        analyze,
      });
      setResult(response);
      onDone(mode === "cv" ? resumeId : undefined, response.country);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  // Una fila por fuente sumando todas sus consultas: es lo que interesa de un vistazo.
  const bySource = result
    ? Object.values(
        result.results.reduce<
          Record<string, { source: string; created: number; fetched: number; skipped: number; errors: string[] }>
        >((acc, row) => {
          const entry = (acc[row.source] ??= {
            source: row.source,
            created: 0,
            fetched: 0,
            skipped: 0,
            errors: [],
          });
          entry.created += row.created ?? 0;
          entry.fetched += row.fetched ?? 0;
          entry.skipped += row.skipped ?? 0;
          if (row.error) entry.errors.push(row.error);
          return acc;
        }, {}),
      )
    : [];
  const totalCreated = bySource.reduce((sum, s) => sum + s.created, 0);

  return (
    <Modal open={open} onClose={onClose} title="Buscar vacantes" wide>
      <div className="space-y-5">
        {error && (
          <Alert tone="critical" title="No se pudo completar">
            {error}
          </Alert>
        )}

        <div className="inline-flex rounded-lg border p-0.5 text-sm">
          {(
            [
              ["cv", "Según un CV"],
              ["free", "Búsqueda libre"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setMode(value)}
              disabled={value === "cv" && resumes.length === 0}
              className={`rounded-md px-3 py-1.5 transition-colors disabled:opacity-40 ${
                mode === value ? "bg-surface-2 font-medium text-ink" : "text-ink-secondary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "cv" && (
          <Field label="CV">
            <Select
              value={resumeId ?? ""}
              onChange={(e) => setResumeId(Number(e.target.value))}
              className="w-full"
            >
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.is_primary ? "★ " : ""}
                  {r.label}
                </option>
              ))}
            </Select>
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-[1fr_14rem]">
          <Field
            label={mode === "cv" ? "Puestos a buscar" : "Términos de búsqueda"}
            hint={
              mode === "cv"
                ? "Deducidos del CV, en inglés porque así publican las bolsas globales. Edítalos si quieres; separados por coma."
                : "Separados por coma. Vacío = lo último de cada fuente."
            }
          >
            <Input
              value={queries}
              onChange={(e) => setQueries(e.target.value)}
              placeholder={planLoading ? "Analizando el CV…" : "Graphic Designer, UX Designer"}
              disabled={planLoading}
            />
          </Field>
          <Field label="País donde vives" hint="Descarta vacantes no elegibles desde ahí">
            <Input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="Colombia"
              disabled={planLoading}
            />
          </Field>
        </div>

        {mode === "cv" && plan && !planLoading && (
          <p className="-mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            {plan.origin === "ai" && "Sugerido por Claude a partir del CV."}
            {plan.origin === "heuristic" && "Sacado de los títulos del CV (sin IA)."}
            {plan.origin === "saved" && "Última búsqueda que usaste con este CV."}
            {plan.region && ` Región: ${plan.region}.`}
            <button className="text-accent hover:underline" onClick={suggestAgain}>
              Volver a sugerir
            </button>
          </p>
        )}

        <div>
          <p className="mb-2 text-xs font-medium text-ink-secondary">Fuentes</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.map((source) => (
              <label
                key={source.name}
                className="flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-surface-2"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selected.has(source.name)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(source.name);
                    else next.delete(source.name);
                    setSelected(next);
                  }}
                />
                <span className="min-w-0">
                  <span className="text-ink">{source.label}</span>
                  {source.filters_country && (
                    <span className="ml-1.5 text-xs text-ink-muted">· filtra por país</span>
                  )}
                  <span className="block text-xs text-ink-muted">{source.description}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <Field label="Máximo por fuente y puesto">
          <Select value={limit} onChange={(e) => setLimit(e.target.value)}>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="40">40</option>
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
          <div className="rounded-lg border p-4">
            <p className="mb-2 text-sm font-medium text-ink">
              {totalCreated} vacantes nuevas
              {result.country && ` elegibles desde ${result.country}`}
            </p>
            <ul className="space-y-1 text-sm">
              {bySource.map((item) => {
                const failed = item.errors.length > 0 && item.fetched === 0;
                return (
                  <li key={item.source} className="flex items-start gap-2">
                    <span
                      aria-hidden
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                      style={{ background: failed ? "var(--critical)" : "var(--good)" }}
                    />
                    <span className="text-ink">{item.source}:</span>
                    <span className="text-ink-secondary">
                      {failed
                        ? item.errors[0]
                        : `${item.created} nuevas de ${item.fetched} encontradas` +
                          (item.skipped ? ` · ${item.skipped} descartadas por país` : "")}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            variant="primary"
            onClick={run}
            loading={loading}
            disabled={selected.size === 0 || planLoading || (mode === "cv" && !resumeId)}
          >
            {loading ? "Buscando en las bolsas…" : "Buscar e importar"}
          </Button>
          {result && <Button onClick={onClose}>Ver resultados</Button>}
        </div>
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
