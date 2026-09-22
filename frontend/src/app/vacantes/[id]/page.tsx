"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Meter, ScoreRing } from "@/components/charts";
import {
  Alert,
  Badge,
  Button,
  Card,
  Chip,
  EmptyState,
  PageHeader,
  Skeleton,
  cx,
  formatDate,
  formatMoney,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type {
  Application,
  CompanyIntel,
  CoverLetter,
  InterviewIntel,
  Job,
  MatchResult,
  SalaryBenchmark,
} from "@/lib/types";

type Tab = "match" | "company" | "process" | "salary" | "letter" | "description";

const TABS: { id: Tab; label: string }[] = [
  { id: "match", label: "Encaje" },
  { id: "company", label: "Empresa" },
  { id: "process", label: "Proceso" },
  { id: "salary", label: "Salario" },
  { id: "letter", label: "Carta" },
  { id: "description", label: "Oferta original" },
];

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const jobId = Number(params.id);

  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [tab, setTab] = useState<Tab>("match");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    api.getJob(jobId).then(setJob).catch((e: ApiError) => setError(e.message));
    api.match(jobId).then(setMatch).catch(() => setMatch(null));
    api
      .listApplications()
      .then((apps) => setApplication(apps.find((a) => a.job_id === jobId) ?? null))
      .catch(() => {});
  }, [jobId]);

  const saveToPipeline = async () => {
    setSaving(true);
    try {
      const created = await api.createApplication({ job_id: jobId, generate_tasks: true });
      setApplication(created);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  if (error && !job) {
    return (
      <>
        <PageHeader title="Vacante" />
        <Alert tone="critical" title="No se pudo cargar">
          {error}
        </Alert>
      </>
    );
  }

  if (!job) return <Skeleton className="h-96 w-full" />;

  const requirements = job.requirements ?? {};

  return (
    <>
      <button
        onClick={() => router.back()}
        className="mb-4 text-sm text-ink-muted hover:text-ink"
      >
        ← Volver
      </button>

      <PageHeader
        title={job.title}
        description={`${job.company}${job.location ? ` · ${job.location}` : ""}`}
        actions={
          <>
            {job.url && (
              <a href={job.url} target="_blank" rel="noopener noreferrer">
                <Button>Ver oferta original</Button>
              </a>
            )}
            {application ? (
              <Link href="/pipeline">
                <Button variant="primary">En el pipeline · {application.status}</Button>
              </Link>
            ) : (
              <Button variant="primary" onClick={saveToPipeline} loading={saving}>
                Guardar en el pipeline
              </Button>
            )}
          </>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{job.remote_type}</Badge>
        {job.seniority && <Badge tone="neutral">{job.seniority}</Badge>}
        {job.employment_type && <Badge tone="neutral">{job.employment_type}</Badge>}
        {job.salary_max ? (
          <Badge tone="good">
            {formatMoney(job.salary_min, job.salary_currency)} –{" "}
            {formatMoney(job.salary_max, job.salary_currency)}
            {job.salary_period ? ` / ${job.salary_period}` : ""}
          </Badge>
        ) : (
          <Badge tone="warning" icon>
            Sin salario publicado
          </Badge>
        )}
        <span className="text-xs text-ink-muted">
          {job.source} · {formatDate(job.posted_at ?? job.created_at)}
        </span>
      </div>

      {(requirements.red_flags?.length ?? 0) > 0 && (
        <div className="mb-6">
          <Alert tone="serious" title="Señales de alerta en la oferta">
            <ul className="list-disc space-y-1 pl-4">
              {requirements.red_flags!.map((flag, index) => (
                <li key={index}>{flag}</li>
              ))}
            </ul>
          </Alert>
        </div>
      )}

      <nav className="mb-6 flex gap-1 border-b">
        {TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              tab === item.id
                ? "border-accent font-medium text-ink"
                : "border-transparent text-ink-secondary hover:text-ink",
            )}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {tab === "match" && <MatchTab jobId={jobId} match={match} onMatch={setMatch} job={job} />}
      {tab === "company" && <CompanyTab jobId={jobId} />}
      {tab === "process" && <ProcessTab jobId={jobId} />}
      {tab === "salary" && <SalaryTab jobId={jobId} />}
      {tab === "letter" && (
        <LetterTab
          key={application?.id ?? "none"}
          application={application}
          onSaveToPipeline={saveToPipeline}
          saving={saving}
        />
      )}
      {tab === "description" && (
        <Card title="Descripción original">
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink-secondary">
            {job.description_raw}
          </pre>
        </Card>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
function MatchTab({
  jobId,
  job,
  match,
  onMatch,
}: {
  jobId: number;
  job: Job;
  match: MatchResult | null;
  onMatch: (m: MatchResult) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deepen = async () => {
    setLoading(true);
    setError(null);
    try {
      const analysis = await api.deepAnalysis(jobId);
      onMatch({ ...(match as MatchResult), analysis });
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  if (!match) {
    return (
      <EmptyState
        title="Sin CV cargado"
        description="El match score compara tu CV con los requisitos de la oferta."
        action={
          <Link href="/cv">
            <Button variant="primary">Subir mi CV</Button>
          </Link>
        }
      />
    );
  }

  const requirements = job.requirements ?? {};

  return (
    <div className="space-y-6">
      <Card title="Compatibilidad">
        <div className="grid gap-8 sm:grid-cols-[minmax(0,12rem)_1fr]">
          <div className="flex items-center">
            <ScoreRing value={match.score} size={88} label="compatibilidad" />
          </div>
          <div className="space-y-3">
            <Meter
              label="Cobertura de requisitos"
              value={match.skill_score}
              description="Peso 50%: los requisitos excluyentes valen más que los deseables."
            />
            <Meter
              label="Similitud semántica"
              value={match.semantic_score}
              description="Peso 35%: cuánto se parece tu perfil al conjunto de la oferta."
            />
            <Meter
              label="Encaje de seniority"
              value={match.seniority_score}
              description="Peso 15%: estar por debajo penaliza más que estar por encima."
            />
          </div>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Lo que ya cumples" subtitle={`${match.matched_skills.length} requisitos`}>
          <div className="flex flex-wrap gap-1.5">
            {match.matched_skills.length === 0 ? (
              <p className="text-sm text-ink-muted">Ninguno detectado.</p>
            ) : (
              match.matched_skills.map((skill) => (
                <Chip key={skill} tone="good">
                  {skill}
                </Chip>
              ))
            )}
          </div>
        </Card>
        <Card title="Lo que te falta" subtitle={`${match.missing_skills.length} requisitos`}>
          <div className="flex flex-wrap gap-1.5">
            {match.missing_skills.length === 0 ? (
              <p className="text-sm text-ink-muted">Nada: cumples todo lo que pide.</p>
            ) : (
              match.missing_skills.map((skill) => (
                <Chip key={skill} tone="critical">
                  {skill}
                </Chip>
              ))
            )}
          </div>
        </Card>
      </div>

      {error && (
        <Alert tone="critical" title="No se pudo analizar">
          {error}
        </Alert>
      )}

      {match.analysis ? (
        <Card title="Análisis" subtitle="Juicio cualitativo de Claude sobre este encaje">
          <p className="text-sm leading-relaxed text-ink">{match.analysis.verdict}</p>

          <Section title="Tus 3 mejores argumentos" items={match.analysis.strongest_arguments} />
          <Section title="Gaps reales" items={match.analysis.gaps} tone="warning" />
          <Section title="Cómo compensarlos" items={match.analysis.gap_mitigation} />

          {match.analysis.keywords_to_add.length > 0 && (
            <>
              <p className="mt-5 mb-2 text-xs font-medium text-ink-secondary">
                Keywords que deberías añadir al CV
              </p>
              <div className="flex flex-wrap gap-1.5">
                {match.analysis.keywords_to_add.map((word) => (
                  <Chip key={word} tone="accent">
                    {word}
                  </Chip>
                ))}
              </div>
            </>
          )}
        </Card>
      ) : (
        <Card title="Análisis cualitativo">
          <p className="mb-3 text-sm text-ink-secondary">
            Claude lee la oferta y tu CV, y te dice si vale la pena postular, qué argumentos usar
            y cómo compensar lo que falta.
          </p>
          <Button variant="primary" onClick={deepen} loading={loading}>
            Analizar con Claude
          </Button>
        </Card>
      )}

      {(requirements.hard_skills?.length ?? 0) > 0 && (
        <Card title="Requisitos extraídos de la oferta">
          <div className="flex flex-wrap gap-1.5">
            {requirements.hard_skills!.map((skill) => (
              <Chip key={skill.name} tone={skill.required ? "accent" : "neutral"}>
                {skill.name}
                {skill.required ? " (imprescindible)" : " (deseable)"}
              </Chip>
            ))}
          </div>
          {(requirements.responsibilities?.length ?? 0) > 0 && (
            <Section title="Responsabilidades" items={requirements.responsibilities!} />
          )}
        </Card>
      )}
    </div>
  );
}

function Section({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone?: "warning";
}) {
  if (!items?.length) return null;
  return (
    <div className="mt-5">
      <p className="mb-2 text-xs font-medium text-ink-secondary">{title}</p>
      <ul className="space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2 text-sm text-ink-secondary">
            <span
              aria-hidden
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ background: tone === "warning" ? "var(--warning)" : "var(--accent)" }}
            />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
function useIntel<T>(loader: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [loader]);

  return { data, loading, error, run };
}

function Sources({ sources, confidence }: { sources: string[]; confidence: string }) {
  return (
    <div className="mt-5 border-t pt-4">
      <div className="mb-2 flex items-center gap-2">
        <Badge
          tone={confidence === "high" ? "good" : confidence === "medium" ? "warning" : "serious"}
          icon
        >
          Confianza {confidence}
        </Badge>
        <span className="text-xs text-ink-muted">{sources.length} fuentes consultadas</span>
      </div>
      <ul className="space-y-0.5">
        {sources.slice(0, 8).map((url) => (
          <li key={url}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="truncate text-xs text-ink-muted underline hover:text-ink-secondary"
            >
              {url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function IntelGate({
  title,
  description,
  loading,
  error,
  onRun,
}: {
  title: string;
  description: string;
  loading: boolean;
  error: string | null;
  onRun: () => void;
}) {
  return (
    <Card title={title}>
      <p className="mb-3 text-sm text-ink-secondary">{description}</p>
      {error && (
        <div className="mb-3">
          <Alert tone="critical" title="No se pudo investigar">
            {error}
          </Alert>
        </div>
      )}
      <Button variant="primary" onClick={onRun} loading={loading}>
        Investigar
      </Button>
    </Card>
  );
}

function CompanyTab({ jobId }: { jobId: number }) {
  const loader = useCallback(() => api.companyIntel(jobId), [jobId]);
  const { data, loading, error, run } = useIntel<CompanyIntel>(loader);

  if (!data) {
    return (
      <IntelGate
        title="Inteligencia de empresa"
        description="Claude busca en la web: a qué se dedica, tamaño, stack, noticias recientes y qué mencionar en la entrevista para demostrar que investigaste."
        loading={loading}
        error={error}
        onRun={run}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card title={data.company_name}>
        <p className="text-sm leading-relaxed text-ink">{data.summary}</p>
        <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          {[
            ["Sector", data.industry],
            ["Tamaño", data.size],
            ["Sede", data.headquarters],
            ["Fundada", data.founded],
            ["Financiación", data.funding_stage],
          ]
            .filter(([, value]) => value)
            .map(([label, value]) => (
              <div key={label} className="flex gap-2">
                <dt className="w-28 shrink-0 text-ink-muted">{label}</dt>
                <dd className="text-ink">{value}</dd>
              </div>
            ))}
        </dl>
        {data.tech_stack.length > 0 && (
          <>
            <p className="mt-4 mb-2 text-xs font-medium text-ink-secondary">Stack conocido</p>
            <div className="flex flex-wrap gap-1.5">
              {data.tech_stack.map((tech) => (
                <Chip key={tech} tone="accent">
                  {tech}
                </Chip>
              ))}
            </div>
          </>
        )}
        <Sources sources={data.sources} confidence={data.confidence} />
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Qué mencionar en la entrevista">
          <Section title="" items={data.talking_points} />
        </Card>
        <Card title="Qué preguntarles tú">
          <Section title="" items={data.questions_to_ask} />
        </Card>
      </div>

      {data.recent_news.length > 0 && (
        <Card title="Noticias recientes">
          <ul className="divide-y">
            {data.recent_news.map((news, index) => (
              <li key={index} className="py-3 first:pt-0 last:pb-0">
                <a
                  href={news.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-ink hover:underline"
                >
                  {news.title}
                </a>
                <p className="mt-0.5 text-sm text-ink-secondary">{news.summary}</p>
                {news.date && <p className="mt-1 text-xs text-ink-muted">{news.date}</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ProcessTab({ jobId }: { jobId: number }) {
  const loader = useCallback(() => api.interviewIntel(jobId), [jobId]);
  const { data, loading, error, run } = useIntel<InterviewIntel>(loader);

  if (!data) {
    return (
      <IntelGate
        title="Cómo entrevista esta empresa"
        description="Etapas del proceso, tipo de pruebas (LeetCode, take-home, psicotécnico, STAR) y preguntas que reportan otros candidatos."
        loading={loading}
        error={error}
        onRun={run}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card
        title="Etapas del proceso"
        subtitle={[data.difficulty && `Dificultad ${data.difficulty}`, data.typical_duration]
          .filter(Boolean)
          .join(" · ")}
      >
        {data.stages.length === 0 ? (
          <p className="text-sm text-ink-muted">No se encontraron etapas concretas.</p>
        ) : (
          <ol className="space-y-4">
            {data.stages.map((stage, index) => (
              <li key={index} className="flex gap-4">
                <span
                  className="tabular mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{ background: `var(--stage-${Math.min(index + 1, 5)})` }}
                >
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">{stage.name}</p>
                  <p className="text-xs text-ink-muted">
                    {[stage.format, stage.duration].filter(Boolean).join(" · ")}
                  </p>
                  {stage.focus && (
                    <p className="mt-1 text-sm text-ink-secondary">{stage.focus}</p>
                  )}
                  {stage.how_to_prepare.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {stage.how_to_prepare.map((tip, tipIndex) => (
                        <li key={tipIndex} className="text-sm text-ink-secondary">
                          → {tip}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
        <Sources sources={data.sources} confidence={data.confidence} />
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Tipo de pruebas">
          <div className="flex flex-wrap gap-1.5">
            {data.assessment_types.map((type) => (
              <Chip key={type} tone="accent">
                {type}
              </Chip>
            ))}
          </div>
        </Card>
        <Card title="Temas a repasar">
          <div className="flex flex-wrap gap-1.5">
            {data.technical_topics.map((topic) => (
              <Chip key={topic} tone="warning">
                {topic}
              </Chip>
            ))}
          </div>
        </Card>
      </div>

      {data.common_questions.length > 0 && (
        <Card title="Preguntas reportadas">
          <ul className="divide-y">
            {data.common_questions.map((question, index) => (
              <li key={index} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-start gap-2">
                  <Badge tone="neutral">{question.type}</Badge>
                </div>
                <p className="mt-1.5 text-sm text-ink">{question.question}</p>
                {question.why_asked && (
                  <p className="mt-0.5 text-xs text-ink-muted">{question.why_asked}</p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {data.tips.length > 0 && (
        <Card title="Consejos">
          <Section title="" items={data.tips} />
        </Card>
      )}

      <Link href={`/entrevistas?job=${jobId}`}>
        <Button variant="primary">Simular esta entrevista</Button>
      </Link>
    </div>
  );
}

function SalaryTab({ jobId }: { jobId: number }) {
  const loader = useCallback(() => api.salaryIntel(jobId), [jobId]);
  const { data, loading, error, run } = useIntel<SalaryBenchmark>(loader);

  if (!data) {
    return (
      <IntelGate
        title="Benchmark salarial"
        description="Rango real de mercado para este rol y ubicación, más un guion concreto de negociación basado en tu perfil."
        loading={loading}
        error={error}
        onRun={run}
      />
    );
  }

  const max = data.p75 || 1;

  return (
    <div className="space-y-6">
      <Card title={`Rango de mercado · ${data.role}`} subtitle={data.location}>
        {/* Tres percentiles: magnitud contra un límite común, un solo tono. */}
        <ul className="space-y-3">
          {([
            ["p25", "Percentil 25", data.p25],
            ["p50", "Mediana", data.p50],
            ["p75", "Percentil 75", data.p75],
          ] as const).map(([id, label, value]) => (
            <li key={id} className="grid grid-cols-[6rem_1fr_auto] items-center gap-3">
              <span className="text-xs text-ink-secondary">{label}</span>
              <span className="block h-2 rounded-sm" style={{ background: "var(--grid)" }}>
                <span
                  className="block h-full rounded-r-sm"
                  style={{
                    width: `${Math.max((value / max) * 100, 2)}%`,
                    background: id === "p50" ? "var(--accent-ink)" : "var(--accent)",
                  }}
                />
              </span>
              <span className="tabular text-sm font-medium text-ink">
                {Math.round(value).toLocaleString("es")} {data.currency}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-ink-secondary">{data.reasoning}</p>
        <Sources sources={data.sources} confidence={data.confidence} />
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Guion de negociación">
          <ul className="space-y-3">
            {data.negotiation_script.map((line, index) => (
              <li
                key={index}
                className="rounded-lg bg-surface-2 px-3 py-2 text-sm italic text-ink"
              >
                “{line}”
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Tus puntos de apalancamiento">
          <Section title="" items={data.leverage_points} />
        </Card>
      </div>
    </div>
  );
}

function LetterTab({
  application,
  onSaveToPipeline,
  saving,
}: {
  application: Application | null;
  onSaveToPipeline: () => void;
  saving: boolean;
}) {
  // El componente se remonta con `key` cuando cambia la postulación, así que
  // la carta ya guardada se toma como estado inicial en vez de sincronizarse.
  const [letter, setLetter] = useState<CoverLetter | null>(() =>
    application?.cover_letter
      ? {
          subject: "",
          body: application.cover_letter,
          highlighted_projects: [],
          word_count: application.cover_letter.split(/\s+/).length,
        }
      : null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!application) {
    return (
      <EmptyState
        title="Guarda la vacante primero"
        description="La carta se genera dentro de la postulación, para quedar archivada junto al resto del proceso."
        action={
          <Button variant="primary" onClick={onSaveToPipeline} loading={saving}>
            Guardar en el pipeline
          </Button>
        }
      />
    );
  }

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setLetter(await api.coverLetter(application.id));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="Carta de presentación"
      subtitle={letter ? `${letter.word_count} palabras` : undefined}
      actions={
        <>
          {letter && (
            <Button
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(letter.body);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
            >
              {copied ? "Copiado ✓" : "Copiar"}
            </Button>
          )}
          <Button size="sm" variant="primary" onClick={generate} loading={loading}>
            {letter ? "Regenerar" : "Generar"}
          </Button>
        </>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="No se pudo generar">
            {error}
          </Alert>
        </div>
      )}
      {letter ? (
        <>
          {letter.subject && (
            <p className="mb-3 text-sm text-ink-secondary">
              <span className="text-ink-muted">Asunto:</span> {letter.subject}
            </p>
          )}
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink">
            {letter.body}
          </pre>
        </>
      ) : (
        <p className="text-sm text-ink-secondary">
          Se redacta usando tu CV y la investigación de la empresa, destacando los proyectos que
          responden a los requisitos de esta vacante concreta.
        </p>
      )}
    </Card>
  );
}
