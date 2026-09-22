"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { KpiRow, StatTile } from "@/components/charts";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Skeleton,
  Textarea,
  cx,
  formatDate,
  relativeDays,
  scoreTone,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Application, ApplicationStatus, Board, Task } from "@/lib/types";

const CATEGORY_LABELS: Record<string, string> = {
  study: "Estudiar",
  storytelling: "Historia STAR",
  networking: "Networking",
  follow_up: "Seguimiento",
  logistics: "Logística",
  other: "Otro",
};

export default function PipelinePage() {
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [hoverColumn, setHoverColumn] = useState<string | null>(null);
  const [detail, setDetail] = useState<Application | null>(null);

  const refresh = useCallback(async () => {
    try {
      setBoard(await api.board());
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.board();
        if (!cancelled) setBoard(data);
      } catch (e) {
        if (!cancelled) setError((e as ApiError).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const move = async (applicationId: number, status: ApplicationStatus) => {
    setDragging(null);
    setHoverColumn(null);

    // Optimista: la tarjeta se mueve al soltar y se reconcilia con el servidor.
    setBoard((current) => {
      if (!current) return current;
      let moved: Application | null = null;
      const columns = current.columns.map((column) => ({
        ...column,
        applications: column.applications.filter((app) => {
          if (app.id === applicationId) {
            moved = { ...app, status };
            return false;
          }
          return true;
        }),
      }));
      if (moved) {
        const target = columns.find((c) => c.status === status);
        target?.applications.unshift(moved);
      }
      return { ...current, columns };
    });

    try {
      await api.updateApplication(applicationId, { status });
    } catch (e) {
      setError((e as ApiError).message);
    }
    refresh();
  };

  if (loading) return <Skeleton className="h-96 w-full" />;

  const stats = board?.stats;
  const isEmpty = board?.columns.every((c) => c.applications.length === 0) ?? true;

  return (
    <>
      <PageHeader
        title="Pipeline"
        description="Arrastra las tarjetas entre columnas. Cada movimiento queda registrado en el timeline de la postulación."
        actions={
          <Link href="/vacantes">
            <Button variant="primary">Añadir vacantes</Button>
          </Link>
        }
      />

      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="Error">
            {error}
          </Alert>
        </div>
      )}

      <div className="mb-6">
        <KpiRow>
          <StatTile label="Total" value={stats?.total ?? 0} />
          <StatTile
            label="Tasa de respuesta"
            value={stats?.response_rate ?? 0}
            unit="%"
            tone={(stats?.response_rate ?? 0) >= 15 ? "good" : "warning"}
          />
          <StatTile
            label="Ofertas"
            value={stats?.offers ?? 0}
            tone={stats?.offers ? "good" : "neutral"}
          />
          <StatTile
            label="Tareas vencidas"
            value={stats?.overdue_tasks ?? 0}
            tone={stats?.overdue_tasks ? "critical" : "neutral"}
          />
        </KpiRow>
      </div>

      {isEmpty ? (
        <EmptyState
          title="El tablero está vacío"
          description="Guarda una vacante desde el explorador y aparecerá aquí con su checklist de preparación."
          action={
            <Link href="/vacantes">
              <Button variant="primary">Ir a vacantes</Button>
            </Link>
          }
        />
      ) : (
        <div className="-mx-2 flex gap-3 overflow-x-auto px-2 pb-4">
          {board?.columns.map((column) => (
            <div
              key={column.status}
              onDragOver={(e) => {
                e.preventDefault();
                setHoverColumn(column.status);
              }}
              onDragLeave={() => setHoverColumn(null)}
              onDrop={() => dragging && move(dragging, column.status)}
              className={cx(
                "flex w-64 shrink-0 flex-col rounded-xl border bg-surface-1 transition-colors",
                hoverColumn === column.status && "border-accent bg-surface-2",
              )}
            >
              <header className="flex items-center justify-between border-b px-3 py-2.5">
                <span className="text-xs font-semibold text-ink">{column.label}</span>
                <span className="tabular text-xs text-ink-muted">
                  {column.applications.length}
                </span>
              </header>

              <ul className="flex-1 space-y-2 p-2">
                {column.applications.map((app) => {
                  const pending = app.tasks.filter((t) => !t.done).length;
                  const overdue = app.tasks.some(
                    (t) => !t.done && t.due_at && new Date(t.due_at) < new Date(),
                  );
                  return (
                    <li
                      key={app.id}
                      draggable
                      onDragStart={() => setDragging(app.id)}
                      onDragEnd={() => setDragging(null)}
                      onClick={() => setDetail(app)}
                      className={cx(
                        "cursor-grab rounded-lg border bg-surface-1 p-2.5 transition-opacity hover:bg-surface-2 active:cursor-grabbing",
                        dragging === app.id && "opacity-40",
                      )}
                    >
                      <p className="truncate text-xs font-medium text-ink">
                        {app.job?.title ?? "Vacante"}
                      </p>
                      <p className="truncate text-xs text-ink-secondary">{app.job?.company}</p>

                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {app.match_score != null && (
                          <Badge tone={scoreTone(app.match_score)}>
                            {Math.round(app.match_score)}%
                          </Badge>
                        )}
                        {pending > 0 && (
                          <span
                            className="text-xs"
                            style={{ color: overdue ? "var(--critical)" : "var(--ink-muted)" }}
                          >
                            {overdue && "⚠ "}
                            {pending} tarea{pending > 1 ? "s" : ""}
                          </span>
                        )}
                      </div>

                      {app.next_action_at && (
                        <p className="mt-1.5 text-xs text-ink-muted">
                          Siguiente: {relativeDays(app.next_action_at)}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}

      {detail && (
        <ApplicationDetail
          key={detail.id}
          application={detail}
          onClose={() => setDetail(null)}
          onChanged={refresh}
        />
      )}
    </>
  );
}

function ApplicationDetail({
  application,
  onClose,
  onChanged,
}: {
  application: Application;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [tasks, setTasks] = useState<Task[]>(application.tasks);
  const [notes, setNotes] = useState(application.notes);
  const [newTask, setNewTask] = useState("");
  const [busy, setBusy] = useState(false);

  const toggle = async (task: Task) => {
    setTasks((current) =>
      current.map((t) => (t.id === task.id ? { ...t, done: !t.done } : t)),
    );
    await api.updateTask(task.id, { done: !task.done });
    onChanged();
  };

  const addTask = async () => {
    if (!newTask.trim()) return;
    const created = await api.addTask(application.id, { title: newTask });
    setTasks((current) => [...current, created]);
    setNewTask("");
    onChanged();
  };

  const regenerate = async () => {
    setBusy(true);
    try {
      const generated = await api.generateTasks(application.id, true);
      setTasks(generated);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const saveNotes = async () => {
    await api.updateApplication(application.id, { notes });
    onChanged();
  };

  const remove = async () => {
    if (!confirm("¿Quitar esta postulación del pipeline?")) return;
    await api.deleteApplication(application.id);
    onClose();
    onChanged();
  };

  const done = tasks.filter((t) => t.done).length;

  return (
    <Modal
      open
      onClose={onClose}
      title={`${application.job?.title ?? "Postulación"} · ${application.job?.company ?? ""}`}
      wide
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          {application.match_score != null && (
            <Badge tone={scoreTone(application.match_score)} icon>
              Match {Math.round(application.match_score)}%
            </Badge>
          )}
          <Badge tone="neutral">{application.status}</Badge>
          {application.applied_at && (
            <span className="text-xs text-ink-muted">
              Postulada el {formatDate(application.applied_at)}
            </span>
          )}
          <Link href={`/vacantes/${application.job_id}`} className="ml-auto">
            <Button size="sm">Ver dossier</Button>
          </Link>
        </div>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-ink">
              Checklist · {done}/{tasks.length}
            </h3>
            <Button size="sm" variant="ghost" onClick={regenerate} loading={busy}>
              Regenerar con IA
            </Button>
          </div>

          <ul className="space-y-1.5">
            {tasks.map((task) => {
              const overdue = !task.done && task.due_at && new Date(task.due_at) < new Date();
              return (
                <li key={task.id} className="flex items-start gap-2.5 rounded-lg border p-2.5">
                  <input
                    type="checkbox"
                    checked={task.done}
                    onChange={() => toggle(task)}
                    className="mt-0.5"
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className={cx(
                        "text-sm",
                        task.done ? "text-ink-muted line-through" : "text-ink",
                      )}
                    >
                      {task.title}
                    </p>
                    {task.detail && (
                      <p className="mt-0.5 text-xs text-ink-secondary">{task.detail}</p>
                    )}
                    <div className="mt-1 flex items-center gap-2 text-xs text-ink-muted">
                      <span>{CATEGORY_LABELS[task.category] ?? task.category}</span>
                      {task.due_at && (
                        <span style={{ color: overdue ? "var(--critical)" : undefined }}>
                          · {overdue && "⚠ "}
                          {relativeDays(task.due_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={async () => {
                      await api.deleteTask(task.id);
                      setTasks((current) => current.filter((t) => t.id !== task.id));
                      onChanged();
                    }}
                    aria-label="Eliminar tarea"
                    className="text-ink-muted hover:text-ink"
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="mt-2 flex gap-2">
            <Input
              value={newTask}
              onChange={(e) => setNewTask(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTask()}
              placeholder="Añadir tarea…"
            />
            <Button onClick={addTask}>Añadir</Button>
          </div>
        </section>

        <Field label="Notas">
          <Textarea
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onBlur={saveNotes}
            placeholder="Nombre del reclutador, feedback recibido, lo que pediste de salario…"
          />
        </Field>

        {application.cover_letter && (
          <Card title="Carta de presentación guardada">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink-secondary">
              {application.cover_letter}
            </pre>
          </Card>
        )}

        <div className="border-t pt-4">
          <Button variant="danger" onClick={remove}>
            Quitar del pipeline
          </Button>
        </div>
      </div>
    </Modal>
  );
}
