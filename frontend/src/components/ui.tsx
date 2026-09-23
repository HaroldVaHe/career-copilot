"use client";

import { type ReactNode, type TextareaHTMLAttributes, type InputHTMLAttributes, type SelectHTMLAttributes, type ButtonHTMLAttributes, useEffect } from "react";

export const cx = (...parts: (string | false | null | undefined)[]) =>
  parts.filter(Boolean).join(" ");

/* -------------------------------------------------------------------------- */
/* Contenedores                                                               */
/* -------------------------------------------------------------------------- */
export function Card({
  children,
  className,
  title,
  subtitle,
  actions,
}: {
  children?: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section
      className={cx(
        "rounded-xl border bg-surface-1 shadow-[0_1px_2px_rgba(0,0,0,0.04)]",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && (
              <p className="mt-0.5 text-xs text-ink-secondary">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-ink-secondary">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/* -------------------------------------------------------------------------- */
/* Controles                                                                  */
/* -------------------------------------------------------------------------- */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

export function Button({
  variant = "secondary",
  size = "md",
  loading,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const variants = {
    primary: "bg-accent text-white hover:opacity-90 border-transparent",
    secondary: "bg-surface-2 text-ink hover:bg-surface-1 border",
    ghost: "bg-transparent text-ink-secondary hover:bg-surface-2 border-transparent",
    danger: "bg-transparent text-[var(--critical)] hover:bg-surface-2 border",
  } as const;

  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm",
        variants[variant],
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cx(
        "w-full rounded-lg border bg-surface-1 px-3 py-2 text-sm text-ink",
        "placeholder:text-ink-muted focus:border-accent focus:outline-none",
        className,
      )}
    />
  );
}

export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={cx(
        "w-full rounded-lg border bg-surface-1 px-3 py-2 text-sm leading-relaxed text-ink",
        "placeholder:text-ink-muted focus:border-accent focus:outline-none",
        className,
      )}
    />
  );
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      className={cx(
        "rounded-lg border bg-surface-1 px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none",
        className,
      )}
    />
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-ink-secondary">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-muted">{hint}</span>}
    </label>
  );
}

/* -------------------------------------------------------------------------- */
/* Señalización                                                               */
/* -------------------------------------------------------------------------- */
export type StatusTone = "good" | "warning" | "serious" | "critical" | "neutral" | "accent";

const TONE_COLOR: Record<StatusTone, string> = {
  good: "var(--good)",
  warning: "var(--warning)",
  serious: "var(--serious)",
  critical: "var(--critical)",
  neutral: "var(--ink-muted)",
  accent: "var(--accent)",
};

/** Los colores de estado nunca van solos: siempre icono + etiqueta. */
const TONE_ICON: Record<StatusTone, string> = {
  good: "✓",
  warning: "!",
  serious: "▲",
  critical: "✕",
  neutral: "·",
  accent: "●",
};

export function Badge({
  children,
  tone = "neutral",
  icon = false,
}: {
  children: ReactNode;
  tone?: StatusTone;
  icon?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium text-ink-secondary">
      <span
        aria-hidden
        className="inline-block h-2 w-2 shrink-0 rounded-full"
        style={{ background: TONE_COLOR[tone] }}
      />
      {icon && <span aria-hidden>{TONE_ICON[tone]}</span>}
      {children}
    </span>
  );
}

export function Chip({
  children,
  tone = "neutral",
  onRemove,
}: {
  children: ReactNode;
  tone?: StatusTone;
  onRemove?: () => void;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs text-ink-secondary"
      style={{ background: "var(--surface-2)", boxShadow: `inset 2px 0 0 ${TONE_COLOR[tone]}` }}
    >
      {children}
      {onRemove && (
        <button
          onClick={onRemove}
          aria-label="Quitar"
          className="text-ink-muted hover:text-ink"
        >
          ×
        </button>
      )}
    </span>
  );
}

export function Alert({
  tone = "warning",
  title,
  children,
}: {
  tone?: StatusTone;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div
      role="status"
      className="flex gap-3 rounded-lg border bg-surface-2 px-4 py-3"
      style={{ boxShadow: `inset 3px 0 0 ${TONE_COLOR[tone]}` }}
    >
      <span aria-hidden className="mt-0.5 text-sm" style={{ color: TONE_COLOR[tone] }}>
        {TONE_ICON[tone]}
      </span>
      <div className="min-w-0 text-sm">
        <p className="font-medium text-ink">{title}</p>
        {children && <div className="mt-1 text-ink-secondary">{children}</div>}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-ink-secondary">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded bg-surface-2", className)} />;
}

/* -------------------------------------------------------------------------- */
/* Modal                                                                      */
/* -------------------------------------------------------------------------- */
export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-[6vh]"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className={cx(
          "w-full rounded-xl border bg-surface-1 shadow-xl",
          wide ? "max-w-4xl" : "max-w-xl",
        )}
      >
        <header className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            className="text-lg leading-none text-ink-muted hover:text-ink"
          >
            ×
          </button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Utilidades de formato                                                      */
/* -------------------------------------------------------------------------- */
export const scoreTone = (score: number | null | undefined): StatusTone => {
  if (score == null) return "neutral";
  if (score >= 75) return "good";
  if (score >= 55) return "warning";
  if (score >= 35) return "serious";
  return "critical";
};

export const scoreLabel = (score: number | null | undefined) => {
  if (score == null) return "sin datos";
  if (score >= 75) return "fuerte";
  if (score >= 55) return "aceptable";
  if (score >= 35) return "flojo";
  return "crítico";
};

export const severityTone = (s: string): StatusTone =>
  s === "critical" ? "critical" : s === "warning" ? "warning" : "neutral";

export function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("es", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function relativeDays(value?: string | null) {
  if (!value) return null;
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000);
  if (days === 0) return "hoy";
  if (days === 1) return "mañana";
  if (days === -1) return "ayer";
  return days > 0 ? `en ${days} días` : `hace ${-days} días`;
}

export function formatMoney(value?: number | null, currency?: string | null) {
  if (!value) return null;
  const compact =
    value >= 1000 ? `${Math.round(value / 1000)}K` : Math.round(value).toLocaleString("es");
  return `${compact}${currency ? ` ${currency}` : ""}`;
}
