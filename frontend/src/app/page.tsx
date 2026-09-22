"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Funnel, HeroFigure, KpiRow, StatTile } from "@/components/charts";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  PageHeader,
  Skeleton,
  formatDate,
  relativeDays,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Application, Board, ResumeSummary } from "@/lib/types";

export default function DashboardPage() {
  const [board, setBoard] = useState<Board | null>(null);
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.board(), api.listResumes(), api.listApplications()])
      .then(([b, r, a]) => {
        setBoard(b);
        setResumes(r);
        setApplications(a);
      })
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const primary = resumes.find((r) => r.is_primary) ?? resumes[0] ?? null;
  const stats = board?.stats;

  const pending = applications
    .flatMap((app) =>
      app.tasks
        .filter((t) => !t.done && t.due_at)
        .map((t) => ({ task: t, app })),
    )
    .sort((a, b) => (a.task.due_at! < b.task.due_at! ? -1 : 1))
    .slice(0, 6);

  // El embudo mide conversión DESPUÉS de postular: "Guardada" es previa al embudo.
  const funnelStages = board
    ? board.columns
        .filter((c) =>
          ["applied", "recruiter_contact", "technical_test", "final_interview", "offer"].includes(
            c.status,
          ),
        )
        .map((c, index, all) => ({
          label: c.label,
          // Cada etapa acumula lo que pasó por ella: quien está en Oferta también
          // pasó por prueba técnica, aunque su tarjeta ya no esté en esa columna.
          value: all.slice(index).reduce((sum, col) => sum + col.applications.length, 0),
        }))
    : [];

  if (error) {
    return (
      <>
        <PageHeader title="Panel" />
        <Alert tone="critical" title="No se pudo cargar el panel">
          {error}
          <p className="mt-2">
            Arranca el backend con <code className="rounded bg-surface-2 px-1">uvicorn app.main:app</code>{" "}
            desde <code className="rounded bg-surface-2 px-1">backend/</code>.
          </p>
        </Alert>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Panel"
        description="Estado de tu búsqueda: salud del CV, conversión del pipeline y lo que toca hacer hoy."
        actions={
          <Link href="/vacantes">
            <Button variant="primary">Buscar vacantes</Button>
          </Link>
        }
      />

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
            <Card title="Salud de tu CV">
              {primary ? (
                <>
                  <HeroFigure
                    value={primary.ats_score}
                    unit="/100"
                    label={primary.label}
                    caption={
                      primary.ats_score == null
                        ? "Sin auditar todavía."
                        : primary.ats_score >= 75
                          ? "Tu CV pasa el filtro automático sin problemas."
                          : "Hay margen de mejora antes de postular en serio."
                    }
                  />
                  <Link href="/cv" className="mt-4 inline-block">
                    <Button size="sm">Ver auditoría completa</Button>
                  </Link>
                </>
              ) : (
                <EmptyState
                  title="Todavía no has subido un CV"
                  description="Es el punto de partida: sin CV no hay match score ni adaptación."
                  action={
                    <Link href="/cv">
                      <Button variant="primary">Subir mi CV</Button>
                    </Link>
                  }
                />
              )}
            </Card>

            <Card
              title="Embudo de postulaciones"
              subtitle="Cuánta gente avanza de una etapa a la siguiente"
            >
              <Funnel stages={funnelStages} />
            </Card>
          </div>

          <KpiRow>
            <StatTile
              label="En el pipeline"
              value={stats?.total ?? 0}
              hint="Vacantes guardadas y postuladas"
            />
            <StatTile
              label="Tasa de respuesta"
              value={stats?.response_rate ?? 0}
              unit="%"
              tone={
                (stats?.response_rate ?? 0) >= 20
                  ? "good"
                  : (stats?.response_rate ?? 0) >= 8
                    ? "warning"
                    : "serious"
              }
              hint="Postulaciones que avanzaron a alguna entrevista"
            />
            <StatTile label="Ofertas" value={stats?.offers ?? 0} tone={stats?.offers ? "good" : "neutral"} />
            <StatTile
              label="Tareas vencidas"
              value={stats?.overdue_tasks ?? 0}
              tone={stats?.overdue_tasks ? "critical" : "neutral"}
            />
          </KpiRow>

          <Card
            title="Lo que toca ahora"
            subtitle="Las tareas con fecha más próxima de todo tu pipeline"
            actions={
              <Link href="/pipeline">
                <Button size="sm">Ver tablero</Button>
              </Link>
            }
          >
            {pending.length === 0 ? (
              <p className="text-sm text-ink-muted">
                No hay tareas pendientes con fecha. Guarda una vacante y se genera su checklist.
              </p>
            ) : (
              <ul className="divide-y">
                {pending.map(({ task, app }) => {
                  const overdue = task.due_at && new Date(task.due_at) < new Date();
                  return (
                    <li key={task.id} className="flex items-start gap-3 py-2.5 first:pt-0">
                      <span
                        aria-hidden
                        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                        style={{ background: overdue ? "var(--critical)" : "var(--accent)" }}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink">{task.title}</p>
                        <p className="truncate text-xs text-ink-muted">
                          {app.job?.title} · {app.job?.company}
                        </p>
                      </div>
                      <span
                        className="shrink-0 text-xs"
                        style={{ color: overdue ? "var(--critical)" : "var(--ink-muted)" }}
                        title={formatDate(task.due_at)}
                      >
                        {overdue && "⚠ "}
                        {relativeDays(task.due_at)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
