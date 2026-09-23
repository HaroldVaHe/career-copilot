"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Skeleton,
  scoreLabel,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { switchProfile } from "@/lib/profile";
import type { Profile } from "@/lib/types";

export default function PerfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  const load = useCallback(async () => {
    const [list, current] = await Promise.all([api.listProfiles(), api.currentProfile()]);
    setProfiles(list);
    setActiveId(current.id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [list, current] = await Promise.all([api.listProfiles(), api.currentProfile()]);
        if (cancelled) return;
        setProfiles(list);
        setActiveId(current.id);
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

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await api.createProfile(name.trim());
      // Un perfil nuevo empieza vacío: lo natural es ir directo a subir su CV.
      switchProfile(created.id, "/cv");
    } catch (e) {
      setError((e as ApiError).message);
      setCreating(false);
    }
  };

  const rename = async (profile: Profile) => {
    if (!draft.trim()) return;
    try {
      await api.renameProfile(profile.id, draft.trim());
      setEditing(null);
      await load();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const remove = async (profile: Profile) => {
    const ok = confirm(
      `¿Eliminar el perfil «${profile.full_name}»?\n\nSe borran sus ${profile.resumes} CV, ` +
        `${profile.applications} postulaciones, simulacros y respuestas guardadas. No se puede deshacer.`,
    );
    if (!ok) return;
    try {
      await api.deleteProfile(profile.id);
      if (profile.id === activeId) switchProfile(null);
      else await load();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Perfiles"
        description="Cada perfil es una persona con sus propios CV, pipeline, entrevistas y preferencias. Las vacantes importadas se comparten, pero el match se calcula con el CV del perfil activo."
      />

      {error && (
        <div className="mb-4">
          <Alert tone="critical" title="Algo falló">
            {error}
          </Alert>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div>
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : profiles.length === 0 ? (
            <EmptyState title="No hay perfiles" description="Crea el primero a la derecha." />
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2">
              {profiles.map((profile) => {
                const active = profile.id === activeId;
                return (
                  <li
                    key={profile.id}
                    className={`rounded-xl border bg-surface-1 p-4 ${active ? "ring-2 ring-[var(--accent)]" : ""}`}
                  >
                    <div className="flex items-start gap-3">
                      <Avatar name={profile.full_name} />
                      <div className="min-w-0 flex-1">
                        {editing === profile.id ? (
                          <div className="flex gap-2">
                            <Input
                              value={draft}
                              autoFocus
                              onChange={(e) => setDraft(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") rename(profile);
                                if (e.key === "Escape") setEditing(null);
                              }}
                            />
                            <Button size="sm" variant="primary" onClick={() => rename(profile)}>
                              OK
                            </Button>
                          </div>
                        ) : (
                          <h3 className="truncate text-sm font-semibold text-ink">
                            {profile.full_name}
                          </h3>
                        )}
                        <p className="mt-0.5 truncate text-xs text-ink-secondary">
                          {profile.headline || "Sin CV todavía"}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {active && <Badge tone="accent">Activo</Badge>}
                          {profile.is_default && <Badge tone="neutral">Por defecto</Badge>}
                        </div>
                      </div>
                    </div>

                    <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                      <Stat label="CV" value={profile.resumes} />
                      <Stat label="Postulaciones" value={profile.applications} />
                      <Stat
                        label={`ATS · ${scoreLabel(profile.best_score)}`}
                        value={profile.best_score != null ? Math.round(profile.best_score) : "—"}
                      />
                    </dl>

                    <div className="mt-4 flex flex-wrap gap-2 border-t pt-3">
                      {!active && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => switchProfile(profile.is_default ? null : profile.id, "/cv")}
                        >
                          Usar este perfil
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setEditing(profile.id);
                          setDraft(profile.full_name);
                        }}
                      >
                        Renombrar
                      </Button>
                      {!profile.is_default && (
                        <Button size="sm" variant="danger" onClick={() => remove(profile)}>
                          Eliminar
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Nuevo perfil">
            <div className="space-y-3">
              <Field label="Nombre de la persona">
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && create()}
                  placeholder="Ana Pérez"
                />
              </Field>
              <Button
                variant="primary"
                onClick={create}
                loading={creating}
                disabled={!name.trim()}
                className="w-full"
              >
                Crear y subir su CV
              </Button>
            </div>
          </Card>
          <Alert tone="neutral" title="¿Subiste el CV de otra persona a tu perfil?">
            En «Mis CV», selecciona ese CV y pulsa «Mover a perfil propio». Se crea un perfil con
            el nombre del CV y se lleva sus versiones y postulaciones.
          </Alert>
        </div>
      </div>
    </>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span
      aria-hidden
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
      style={{ background: "var(--accent)" }}
    >
      {initials || "?"}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg bg-surface-2 px-2 py-2">
      <dd className="tabular text-lg font-semibold text-ink">{value}</dd>
      <dt className="truncate text-[11px] text-ink-muted">{label}</dt>
    </div>
  );
}
