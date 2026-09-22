"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { BarList, HeroFigure, Meter } from "@/components/charts";
import { DiffLegend, WordDiff } from "@/components/diff";
import {
  Alert,
  Badge,
  Button,
  Card,
  Chip,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  Textarea,
  formatDate,
  severityTone,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { BulletDiff, Resume, ResumeSummary, TailorResponse } from "@/lib/types";

export default function CvPage() {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tailorOpen, setTailorOpen] = useState(false);

  const refreshList = useCallback(async () => {
    const list = await api.listResumes();
    setResumes(list);
    setSelectedId((current) => current ?? list.find((r) => r.is_primary)?.id ?? list[0]?.id ?? null);
    return list;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.listResumes();
        if (cancelled) return;
        setResumes(list);
        setSelectedId(list.find((r) => r.is_primary)?.id ?? list[0]?.id ?? null);
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

  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await api.getResume(selectedId);
        if (!cancelled) setResume(detail);
      } catch (e) {
        if (!cancelled) setError((e as ApiError).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const handleUpload = async (file: File, label: string, targetRole: string) => {
    setBusy("Leyendo el CV, estructurándolo y auditándolo…");
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("label", label || file.name);
      if (targetRole) form.append("target_role", targetRole);
      form.append("make_primary", "true");
      const created = await api.uploadResume(form);
      await refreshList();
      setSelectedId(created.id);
      setResume(created);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  const handleReaudit = async () => {
    if (!resume) return;
    setBusy("Re-auditando…");
    try {
      await api.reaudit(resume.id);
      setResume(await api.getResume(resume.id));
      await refreshList();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Eliminar esta versión del CV? No se puede deshacer.")) return;
    await api.deleteResume(id);
    const list = await refreshList();
    setSelectedId(list[0]?.id ?? null);
  };

  const active = selectedId == null ? null : resume;
  const report = active?.ats_report ?? null;
  const keywords = report
    ? Object.entries(report.keyword_density)
        .slice(0, 12)
        .map(([label, value]) => ({ label, value }))
    : [];

  return (
    <>
      <PageHeader
        title="Mi CV"
        description="Estructura, auditoría ATS y adaptación por vacante. Nada se guarda sin que lo apruebes."
        actions={
          active && (
            <>
              <Button onClick={handleReaudit} loading={busy === "Re-auditando…"}>
                Re-auditar
              </Button>
              <Button variant="primary" onClick={() => setTailorOpen(true)}>
                Adaptar a una vacante
              </Button>
            </>
          )
        }
      />

      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="Algo falló">
            {error}
          </Alert>
        </div>
      )}
      {busy && (
        <div className="mb-4">
          <Alert tone="accent" title={busy}>
            Puede tardar unos segundos: se extrae el texto, se estructura con Claude y se puntúa.
          </Alert>
        </div>
      )}

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : resumes.length === 0 ? (
        <UploadCard onUpload={handleUpload} busy={!!busy} large />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
          <div className="space-y-4">
            <Card title="Versiones">
              <ul className="space-y-1">
                {resumes.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => setSelectedId(item.id)}
                      className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                        item.id === selectedId ? "bg-surface-2" : "hover:bg-surface-2"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm text-ink">{item.label}</span>
                        {item.ats_score != null && (
                          <span className="tabular shrink-0 text-xs text-ink-secondary">
                            {Math.round(item.ats_score)}
                          </span>
                        )}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-muted">
                        {item.is_primary && "★ "}
                        {item.parent_id ? "variante" : "original"} · {formatDate(item.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
            <UploadCard onUpload={handleUpload} busy={!!busy} />
          </div>

          <div className="space-y-6">
            {!active ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <>
                <Card
                  title="Puntuación ATS"
                  subtitle={active.target_role ? `Rol objetivo: ${active.target_role}` : undefined}
                  actions={
                    resumes.length > 1 && (
                      <Button size="sm" variant="danger" onClick={() => handleDelete(active.id)}>
                        Eliminar
                      </Button>
                    )
                  }
                >
                  {report ? (
                    <div className="grid gap-8 sm:grid-cols-[minmax(0,14rem)_1fr]">
                      <HeroFigure
                        value={report.overall_score}
                        unit="/100"
                        label="Puntuación global"
                        caption={
                          report.overall_score >= 75
                            ? "Listo para postular."
                            : "Aplica los quick wins antes de mandarlo."
                        }
                      />
                      <div className="space-y-3">
                        <Meter
                          label="Relevancia técnica"
                          value={report.breakdown.technical_relevance}
                        />
                        <Meter label="Claridad y formato" value={report.breakdown.clarity_format} />
                        <Meter
                          label="Cuantificación de logros"
                          value={report.breakdown.achievement_quantification}
                        />
                        <Meter
                          label="Cobertura de habilidades"
                          value={report.breakdown.skill_coverage}
                        />
                        <Meter
                          label="Legibilidad para el ATS"
                          value={report.breakdown.ats_parseability}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-ink-muted">Sin auditoría todavía.</p>
                  )}
                </Card>

                {report && report.quick_wins.length > 0 && (
                  <Card title="Quick wins" subtitle="Máximo impacto, mínimo esfuerzo">
                    <ol className="space-y-2">
                      {report.quick_wins.map((win, index) => (
                        <li key={index} className="flex gap-3 text-sm">
                          <span className="tabular shrink-0 font-semibold text-accent">
                            {index + 1}.
                          </span>
                          <span className="text-ink-secondary">{win}</span>
                        </li>
                      ))}
                    </ol>
                  </Card>
                )}

                {report && report.findings.length > 0 && (
                  <Card
                    title="Hallazgos de la auditoría"
                    subtitle={`${report.findings.length} puntos detectados, ordenados por gravedad`}
                  >
                    <ul className="divide-y">
                      {report.findings.map((finding, index) => (
                        <li key={index} className="py-3 first:pt-0 last:pb-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={severityTone(finding.severity)} icon>
                              {finding.severity === "critical"
                                ? "Crítico"
                                : finding.severity === "warning"
                                  ? "Aviso"
                                  : "Nota"}
                            </Badge>
                            <span className="text-xs uppercase tracking-wide text-ink-muted">
                              {finding.area}
                            </span>
                          </div>
                          <p className="mt-1.5 text-sm text-ink">{finding.message}</p>
                          {finding.fix && (
                            <p className="mt-1 text-sm text-ink-secondary">→ {finding.fix}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}

                {report && report.rewrites.length > 0 && (
                  <Card
                    title="Reescrituras propuestas"
                    subtitle="Fórmula X-Y-Z: logré [X] medido por [Y] haciendo [Z]"
                  >
                    <ul className="space-y-4">
                      {report.rewrites.map((rewrite, index) => (
                        <li key={index} className="rounded-lg border p-4">
                          {rewrite.invented_facts && (
                            <div className="mb-3">
                              <Alert tone="warning" title="Contiene datos que no estaban en tu CV">
                                Verifica que sea cierto antes de usarlo.
                              </Alert>
                            </div>
                          )}
                          <p className="text-xs uppercase tracking-wide text-ink-muted">Antes</p>
                          <p className="mt-0.5 text-sm text-ink-secondary">{rewrite.original}</p>
                          <p className="mt-3 text-xs uppercase tracking-wide text-ink-muted">
                            Después
                          </p>
                          <p className="mt-0.5 text-sm text-ink">{rewrite.suggestion}</p>
                          {rewrite.rationale && (
                            <p className="mt-2 text-xs text-ink-muted">{rewrite.rationale}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}

                <div className="grid gap-6 md:grid-cols-2">
                  <Card
                    title="Densidad de keywords"
                    subtitle="Cuántas veces aparece cada tecnología"
                  >
                    <BarList
                      data={keywords}
                      valueSuffix="×"
                      emptyLabel="No se reconoció ninguna tecnología."
                    />
                  </Card>

                  <Card title="Perfil extraído">
                    <dl className="space-y-2 text-sm">
                      <Row label="Nombre" value={active.parsed.contact.full_name} />
                      <Row label="Titular" value={active.parsed.contact.headline} />
                      <Row label="Email" value={active.parsed.contact.email} />
                      <Row label="Ubicación" value={active.parsed.contact.location} />
                      <Row
                        label="Experiencia"
                        value={
                          active.parsed.total_years_experience
                            ? `${active.parsed.total_years_experience} años`
                            : ""
                        }
                      />
                      <Row label="Seniority" value={active.parsed.detected_seniority} />
                    </dl>

                    <p className="mt-4 mb-2 text-xs font-medium text-ink-secondary">Stack</p>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        ...active.parsed.skills.languages,
                        ...active.parsed.skills.frameworks,
                        ...active.parsed.skills.databases,
                        ...active.parsed.skills.cloud_devops,
                        ...active.parsed.skills.tools,
                        ...active.parsed.skills.other,
                      ]
                        .slice(0, 30)
                        .map((skill) => (
                          <Chip key={skill} tone="accent">
                            {skill}
                          </Chip>
                        ))}
                    </div>

                    {report && report.missing_sections.length > 0 && (
                      <p className="mt-4 text-xs text-ink-muted">
                        Secciones ausentes: {report.missing_sections.join(", ")}
                      </p>
                    )}
                  </Card>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {active && (
        <TailorModal
          open={tailorOpen}
          onClose={() => setTailorOpen(false)}
          resume={active}
          onSaved={async (created) => {
            await refreshList();
            setSelectedId(created);
            setTailorOpen(false);
          }}
        />
      )}
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-ink-muted">{label}</dt>
      <dd className="min-w-0 flex-1 truncate text-ink">{value || "—"}</dd>
    </div>
  );
}

function UploadCard({
  onUpload,
  busy,
  large,
}: {
  onUpload: (file: File, label: string, role: string) => void;
  busy: boolean;
  large?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [label, setLabel] = useState("");
  const [role, setRole] = useState("");
  const [dragging, setDragging] = useState(false);

  const submit = (file?: File | null) => {
    if (file) onUpload(file, label, role);
  };

  return (
    <Card title={large ? "Empieza subiendo tu CV" : "Subir otra versión"}>
      {large && (
        <p className="mb-4 text-sm text-ink-secondary">
          PDF, DOCX o TXT. Se extrae el texto, se estructura a JSON y se audita contra los
          criterios que aplican los ATS reales.
        </p>
      )}
      <div className="space-y-3">
        {large && (
          <>
            <Field label="Nombre de esta versión">
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="CV principal"
              />
            </Field>
            <Field label="Rol objetivo" hint="Afina la auditoría hacia ese puesto.">
              <Input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Backend Engineer"
              />
            </Field>
          </>
        )}

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            submit(e.dataTransfer.files?.[0]);
          }}
          onClick={() => fileRef.current?.click()}
          className={`cursor-pointer rounded-lg border border-dashed px-4 text-center transition-colors ${
            large ? "py-10" : "py-6"
          } ${dragging ? "border-accent bg-surface-2" : "hover:bg-surface-2"}`}
        >
          <p className="text-sm text-ink">Arrastra el archivo o haz clic</p>
          <p className="mt-1 text-xs text-ink-muted">.pdf · .docx · .txt · máx 10 MB</p>
        </div>

        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => submit(e.target.files?.[0])}
          disabled={busy}
        />
      </div>
    </Card>
  );
}

function TailorModal({
  open,
  onClose,
  resume,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  resume: Resume;
  onSaved: (newResumeId: number) => void;
}) {
  const [description, setDescription] = useState("");
  const [tone, setTone] = useState("professional");
  const [injectGaps, setInjectGaps] = useState(false);
  const [result, setResult] = useState<TailorResponse | null>(null);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [acceptSummary, setAcceptSummary] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = (d: BulletDiff) => `${d.experience_index}:${d.bullet_index}`;

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.tailor({
        resume_id: resume.id,
        job_description: description,
        inject_gaps: injectGaps,
        tone,
      });
      setResult(response);
      // Por defecto se preseleccionan solo las que no inventan nada.
      setAccepted(
        new Set(response.bullet_diffs.filter((d) => !d.invented_facts).map(key)),
      );
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!result) return;
    setLoading(true);
    try {
      const created = await api.saveVariant({
        resume_id: resume.id,
        job_id: result.job_id,
        label: `Adaptado · ${new Date().toLocaleDateString("es")}`,
        accepted_summary: acceptSummary ? result.summary_after : null,
        accepted_bullets: result.bullet_diffs.filter((d) => accepted.has(key(d))),
      });
      onSaved(created.id);
      setResult(null);
      setDescription("");
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Adaptar el CV a una vacante" wide>
      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="No se pudo adaptar">
            {error}
          </Alert>
        </div>
      )}

      {!result ? (
        <div className="space-y-4">
          <Field label="Descripción de la vacante" hint="Pega el texto completo de la oferta.">
            <Textarea
              rows={10}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Buscamos un Senior Backend Engineer…"
            />
          </Field>
          <div className="flex flex-wrap items-end gap-4">
            <Field label="Tono">
              <Select value={tone} onChange={(e) => setTone(e.target.value)}>
                <option value="professional">Profesional</option>
                <option value="direct">Directo</option>
                <option value="warm">Cercano</option>
              </Select>
            </Field>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink-secondary">
              <input
                type="checkbox"
                checked={injectGaps}
                onChange={(e) => setInjectGaps(e.target.checked)}
              />
              Inyectar tecnologías que faltan
            </label>
          </div>
          {injectGaps && (
            <Alert tone="warning" title="Modo de inyección de gaps">
              Se integrarán tecnologías de la oferta que no están en tu CV. Cada una se marca
              como posible invención y tendrás que aprobarla una por una.
            </Alert>
          )}
          <Button
            variant="primary"
            onClick={run}
            loading={loading}
            disabled={description.trim().length < 50}
          >
            Generar propuesta
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          {result.warnings.length > 0 && (
            <Alert tone="warning" title="Revisa antes de aceptar">
              <ul className="list-disc space-y-1 pl-4">
                {result.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </Alert>
          )}

          <DiffLegend />

          {result.summary_diff.length > 0 && (
            <div className="rounded-lg border p-4">
              <label className="mb-2 flex items-center gap-2 text-xs font-medium text-ink-secondary">
                <input
                  type="checkbox"
                  checked={acceptSummary}
                  onChange={(e) => setAcceptSummary(e.target.checked)}
                />
                Resumen profesional
              </label>
              <WordDiff words={result.summary_diff} />
            </div>
          )}

          {result.bullet_diffs.map((diff) => (
            <div key={key(diff)} className="rounded-lg border p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-xs font-medium text-ink-secondary">
                  <input
                    type="checkbox"
                    checked={accepted.has(key(diff))}
                    onChange={(e) => {
                      const next = new Set(accepted);
                      if (e.target.checked) next.add(key(diff));
                      else next.delete(key(diff));
                      setAccepted(next);
                    }}
                  />
                  {diff.role} · {diff.company}
                </label>
                {diff.invented_facts && (
                  <Badge tone="warning" icon>
                    Posible invención
                  </Badge>
                )}
              </div>
              <WordDiff words={diff.words} />
              {diff.rationale && (
                <p className="mt-2 text-xs text-ink-muted">{diff.rationale}</p>
              )}
            </div>
          ))}

          {result.added_keywords.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-ink-secondary">Keywords incorporadas</p>
              <div className="flex flex-wrap gap-1.5">
                {result.added_keywords.map((word) => (
                  <Chip key={word} tone="good">
                    {word}
                  </Chip>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 border-t pt-4">
            <Button variant="primary" onClick={save} loading={loading}>
              Guardar como nueva versión ({accepted.size + (acceptSummary ? 1 : 0)} cambios)
            </Button>
            <Button onClick={() => setResult(null)}>Volver</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
