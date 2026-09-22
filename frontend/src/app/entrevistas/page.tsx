"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Meter } from "@/components/charts";
import {
  Alert,
  Badge,
  Button,
  Card,
  Chip,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Textarea,
  cx,
  formatDate,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type {
  AnswerFeedback,
  InterviewSession,
  InterviewSummary,
  Job,
  QAEntry,
} from "@/lib/types";

export default function EntrevistasPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <EntrevistasContent />
    </Suspense>
  );
}

function EntrevistasContent() {
  const [tab, setTab] = useState<"simulator" | "qa">("simulator");

  return (
    <>
      <PageHeader
        title="Entrevistas"
        description="Simulacro contextualizado con la vacante y tu CV, y banco de respuestas reutilizables."
      />

      <nav className="mb-6 flex gap-1 border-b">
        {(
          [
            ["simulator", "Simulador"],
            ["qa", "Banco de respuestas"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              tab === id
                ? "border-accent font-medium text-ink"
                : "border-transparent text-ink-secondary hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "simulator" ? <Simulator /> : <KnowledgeBase />}
    </>
  );
}

/* -------------------------------------------------------------------------- */
interface Turn {
  role: "interviewer" | "candidate";
  content: string;
  questionType?: string;
  feedback?: AnswerFeedback;
}

function Simulator() {
  const params = useSearchParams();
  const jobParam = params.get("job");

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<string>(jobParam ?? "");
  const [mode, setMode] = useState("mixed");
  const [difficulty, setDifficulty] = useState("medium");

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [answer, setAnswer] = useState("");
  const [summary, setSummary] = useState<InterviewSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [past, setPast] = useState<InterviewSession[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const loadPast = useCallback(() => {
    api.listInterviews().then(setPast).catch(() => {});
  }, []);

  useEffect(() => {
    api
      .searchJobs({ limit: 100, sort: "date" })
      .then((r) => setJobs(r.results.map((x) => x.job)))
      .catch(() => {});
    loadPast();
  }, [loadPast]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, summary]);

  const start = async () => {
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const { session, reply } = await api.startInterview({
        job_id: jobId ? Number(jobId) : undefined,
        mode,
        difficulty,
      });
      setSessionId(session.id);
      setTurns([
        {
          role: "interviewer",
          content: reply.next_question,
          questionType: reply.question_type,
        },
      ]);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  const send = async () => {
    if (!sessionId || !answer.trim()) return;
    const text = answer;
    setAnswer("");
    setTurns((current) => [...current, { role: "candidate", content: text }]);
    setLoading(true);
    try {
      const reply = await api.answerInterview(sessionId, text);
      setTurns((current) => {
        const next = [...current];
        next[next.length - 1] = { ...next[next.length - 1], feedback: reply.feedback };
        if (reply.next_question && !reply.is_final) {
          next.push({
            role: "interviewer",
            content: reply.next_question,
            questionType: reply.question_type,
          });
        }
        return next;
      });
      if (reply.is_final) await finish();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  const finish = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      setSummary(await api.finishInterview(sessionId));
      loadPast();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card title="Nueva entrevista simulada">
          <p className="mb-4 text-sm text-ink-secondary">
            El entrevistador lee tu CV y los requisitos de la vacante, pregunta sobre lo que
            realmente hiciste y te da feedback tras cada respuesta.
          </p>
          {error && (
            <div className="mb-4">
              <Alert tone="critical" title="No se pudo iniciar">
                {error}
              </Alert>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Vacante">
              <Select value={jobId} onChange={(e) => setJobId(e.target.value)}>
                <option value="">Sin vacante (general)</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} · {job.company}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tipo">
              <Select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="mixed">Mixta</option>
                <option value="technical">Técnica</option>
                <option value="behavioral">Behavioral / STAR</option>
                <option value="system_design">System design</option>
              </Select>
            </Field>
            <Field label="Dificultad">
              <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                <option value="easy">Suave</option>
                <option value="medium">Media</option>
                <option value="hard">Exigente</option>
              </Select>
            </Field>
          </div>
          <Button variant="primary" className="mt-4" onClick={start} loading={loading}>
            Empezar
          </Button>
        </Card>

        <Card title="Entrevistas anteriores">
          {past.length === 0 ? (
            <p className="text-sm text-ink-muted">Todavía ninguna.</p>
          ) : (
            <ul className="space-y-2">
              {past.slice(0, 8).map((session) => (
                <li key={session.id} className="rounded-lg border p-2.5">
                  <p className="text-xs text-ink">
                    {session.mode} · {formatDate(session.created_at)}
                  </p>
                  {typeof session.summary?.overall_score === "number" && (
                    <p className="tabular mt-0.5 text-xs text-ink-secondary">
                      Nota: {Math.round(session.summary.overall_score as number)}/100
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert tone="critical" title="Error">
          {error}
        </Alert>
      )}

      <div className="space-y-4">
        {turns.map((turn, index) => (
          <div key={index}>
            {turn.role === "interviewer" ? (
              <div className="max-w-2xl rounded-xl border bg-surface-1 p-4">
                {turn.questionType && (
                  <Badge tone="accent">{turn.questionType}</Badge>
                )}
                <p className="mt-2 text-sm leading-relaxed text-ink">{turn.content}</p>
              </div>
            ) : (
              <div className="ml-auto max-w-2xl rounded-xl bg-surface-2 p-4">
                <p className="text-sm leading-relaxed text-ink">{turn.content}</p>
                {turn.feedback && <FeedbackBlock feedback={turn.feedback} />}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {summary ? (
        <Card title="Evaluación final">
          <div className="grid gap-6 sm:grid-cols-[minmax(0,16rem)_1fr]">
            <div className="space-y-3">
              <Meter label="Nota global" value={summary.overall_score} />
              <Meter label="Técnica" value={summary.technical_score} />
              <Meter label="Comunicación" value={summary.communication_score} />
            </div>
            <div>
              <p className="text-sm leading-relaxed text-ink">{summary.verdict}</p>
              <List title="Fortalezas" items={summary.top_strengths} tone="good" />
              <List
                title="A mejorar (por orden de impacto)"
                items={summary.priority_improvements}
                tone="warning"
              />
              <List title="Plan de estudio" items={summary.study_plan} tone="accent" />
            </div>
          </div>
          <Button
            className="mt-5"
            onClick={() => {
              setSessionId(null);
              setTurns([]);
              setSummary(null);
            }}
          >
            Nueva entrevista
          </Button>
        </Card>
      ) : (
        <Card>
          <Textarea
            rows={5}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Tu respuesta… (Ctrl+Enter para enviar)"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
            }}
          />
          <div className="mt-3 flex gap-2">
            <Button variant="primary" onClick={send} loading={loading} disabled={!answer.trim()}>
              Responder
            </Button>
            <Button onClick={finish} disabled={loading}>
              Terminar y evaluar
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function FeedbackBlock({ feedback }: { feedback: AnswerFeedback }) {
  return (
    <div className="mt-3 border-t pt-3">
      <div className="mb-2">
        <Meter label="Puntuación de la respuesta" value={feedback.score} size="sm" />
      </div>
      <List title="Bien" items={feedback.strengths} tone="good" compact />
      <List title="Mejorable" items={feedback.improvements} tone="warning" compact />
      <List title="Lo que faltó" items={feedback.missing_points} tone="serious" compact />
      {feedback.star_compliance && (
        <p className="mt-2 text-xs text-ink-secondary">
          <span className="text-ink-muted">STAR:</span> {feedback.star_compliance}
        </p>
      )}
      {feedback.model_answer && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink-secondary">
            Ver respuesta de referencia
          </summary>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-secondary">
            {feedback.model_answer}
          </p>
        </details>
      )}
    </div>
  );
}

function List({
  title,
  items,
  tone,
  compact,
}: {
  title: string;
  items: string[];
  tone: "good" | "warning" | "serious" | "accent";
  compact?: boolean;
}) {
  if (!items?.length) return null;
  const color = `var(--${tone === "accent" ? "accent" : tone})`;
  return (
    <div className={compact ? "mt-1.5" : "mt-4"}>
      <p className="mb-1 text-xs font-medium text-ink-secondary">{title}</p>
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2 text-sm text-ink-secondary">
            <span
              aria-hidden
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ background: color }}
            />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
function KnowledgeBase() {
  const [entries, setEntries] = useState<QAEntry[]>([]);
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(
    (term?: string) => {
      api
        .listQa(term)
        .then(setEntries)
        .catch(() => {})
        .finally(() => setLoading(false));
    },
    [],
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = async () => {
    if (!question.trim()) return;
    if (editing) {
      await api.updateQa(editing, { question, answer, tags: [] });
    } else {
      await api.createQa({ question, answer });
    }
    setQuestion("");
    setAnswer("");
    setEditing(null);
    refresh(search);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div>
        <div className="mb-4 flex gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && refresh(search)}
            placeholder="Buscar por significado: «conflicto con un compañero»"
          />
          <Button onClick={() => refresh(search)}>Buscar</Button>
        </div>

        {loading ? (
          <Skeleton className="h-48 w-full" />
        ) : entries.length === 0 ? (
          <EmptyState
            title="Banco vacío"
            description="Guarda aquí tus respuestas a las preguntas que se repiten. La extensión las reutiliza para rellenar formularios."
          />
        ) : (
          <ul className="space-y-3">
            {entries.map((entry) => (
              <li key={entry.id} className="rounded-xl border bg-surface-1 p-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-ink">{entry.question}</p>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEditing(entry.id);
                        setQuestion(entry.question);
                        setAnswer(entry.answer);
                      }}
                    >
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await api.deleteQa(entry.id);
                        refresh(search);
                      }}
                    >
                      ×
                    </Button>
                  </div>
                </div>
                <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-ink-secondary">
                  {entry.answer || "— sin respuesta guardada —"}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  {entry.tags.map((tag) => (
                    <Chip key={tag}>{tag}</Chip>
                  ))}
                  <span className="text-xs text-ink-muted">
                    usada {entry.times_used}×
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Card title={editing ? "Editar respuesta" : "Nueva respuesta"}>
        <div className="space-y-3">
          <Field label="Pregunta">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="¿Por qué quieres trabajar aquí?"
            />
          </Field>
          <Field label="Tu respuesta">
            <Textarea rows={8} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            <Button variant="primary" onClick={save}>
              {editing ? "Guardar" : "Añadir"}
            </Button>
            {editing && (
              <Button
                onClick={() => {
                  setEditing(null);
                  setQuestion("");
                  setAnswer("");
                }}
              >
                Cancelar
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
