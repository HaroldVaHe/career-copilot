"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { adoptProfileFromUrl, switchProfile } from "@/lib/profile";
import type { Health, Profile } from "@/lib/types";
import { cx } from "./ui";

const LINKS = [
  { href: "/", label: "Panel", icon: "◆" },
  { href: "/cv", label: "Mis CV", icon: "▤" },
  { href: "/vacantes", label: "Vacantes", icon: "◎" },
  { href: "/pipeline", label: "Pipeline", icon: "▦" },
  { href: "/entrevistas", label: "Entrevistas", icon: "◑" },
  { href: "/perfiles", label: "Perfiles", icon: "◉" },
  { href: "/ajustes", label: "Ajustes", icon: "⚙" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setFailed(true));
  }, []);

  return (
    <aside className="flex h-dvh w-60 shrink-0 flex-col border-r bg-surface-1">
      <div className="px-5 pt-5 pb-4">
        <p className="text-sm font-semibold tracking-tight text-ink">Career Copilot</p>
        <p className="text-xs text-ink-muted">Postulación asistida</p>
      </div>

      <ProfileSwitcher />

      <nav className="flex-1 space-y-0.5 px-3">
        {LINKS.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-surface-2 font-medium text-ink"
                  : "text-ink-secondary hover:bg-surface-2 hover:text-ink",
              )}
            >
              <span aria-hidden className="text-xs text-ink-muted">
                {link.icon}
              </span>
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t px-5 py-4 text-xs">
        <SystemStatus health={health} failed={failed} />
        <ThemeToggle />
      </div>
    </aside>
  );
}

/** Cambia la persona activa: sus CV, pipeline, entrevistas y preferencias. */
function ProfileSwitcher() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);

  useEffect(() => {
    if (adoptProfileFromUrl()) return;
    let cancelled = false;
    Promise.all([api.listProfiles(), api.currentProfile()])
      .then(([list, current]) => {
        if (cancelled) return;
        setProfiles(list);
        setActiveId(current.id);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (profiles.length === 0) return null;
  const active = profiles.find((p) => p.id === activeId);

  return (
    <div className="mx-3 mb-3 rounded-lg border bg-surface-2 px-3 py-2.5">
      <label className="block">
        <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          Perfil activo
        </span>
        <select
          value={activeId ?? ""}
          onChange={(e) => {
            const id = Number(e.target.value);
            const target = profiles.find((p) => p.id === id);
            // El por defecto no necesita cabecera: se borra para que la extensión y el
            // frontend coincidan aunque no se haya elegido nada.
            switchProfile(target?.is_default ? null : id);
          }}
          className="w-full truncate bg-transparent text-sm font-medium text-ink focus:outline-none"
        >
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.full_name}
            </option>
          ))}
        </select>
      </label>
      {active?.headline && (
        <p className="mt-0.5 truncate text-xs text-ink-secondary" title={active.headline}>
          {active.headline}
        </p>
      )}
    </div>
  );
}

function SystemStatus({ health, failed }: { health: Health | null; failed: boolean }) {
  if (failed) {
    return (
      <p className="flex items-center gap-2 text-ink-secondary">
        <span
          aria-hidden
          className="h-2 w-2 rounded-full"
          style={{ background: "var(--critical)" }}
        />
        API sin conexión
      </p>
    );
  }
  if (!health) return <p className="text-ink-muted">Comprobando…</p>;

  const llmOk = health.llm.configured;
  return (
    <div className="space-y-1">
      <p className="flex items-center gap-2 text-ink-secondary">
        <span
          aria-hidden
          className="h-2 w-2 rounded-full"
          style={{ background: health.database ? "var(--good)" : "var(--critical)" }}
        />
        {health.database ? "Base de datos ok" : "Base de datos caída"}
      </p>
      <p className="flex items-center gap-2 text-ink-secondary">
        <span
          aria-hidden
          className="h-2 w-2 rounded-full"
          style={{ background: llmOk ? "var(--good)" : "var(--warning)" }}
        />
        {llmOk ? health.llm.model : "Sin API key de Claude"}
      </p>
    </div>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");

  useEffect(() => {
    const stored = localStorage.getItem("theme") as typeof theme | null;
    if (stored) applyTheme(stored, setTheme);
  }, []);

  return (
    <div className="flex items-center gap-1">
      {(["light", "dark", "system"] as const).map((option) => (
        <button
          key={option}
          onClick={() => applyTheme(option, setTheme)}
          className={cx(
            "rounded px-1.5 py-0.5 text-xs transition-colors",
            theme === option
              ? "bg-surface-2 text-ink"
              : "text-ink-muted hover:text-ink-secondary",
          )}
        >
          {option === "light" ? "Claro" : option === "dark" ? "Oscuro" : "Auto"}
        </button>
      ))}
    </div>
  );
}

function applyTheme(
  value: "light" | "dark" | "system",
  setTheme: (v: "light" | "dark" | "system") => void,
) {
  setTheme(value);
  localStorage.setItem("theme", value);
  if (value === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", value);
  }
}
