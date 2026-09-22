"use client";

/**
 * Piezas de visualización del panel.
 *
 * Decisiones que vienen del método, no del gusto:
 * - Una puntuación suelta no es un gráfico: es una cifra protagonista o un medidor.
 * - Varias cifras de cabecera son una fila de stat tiles, no un gráfico de barras agrupado.
 * - La densidad de keywords es magnitud pura -> barras con un solo tono secuencial.
 * - El embudo usa una rampa ordinal de un solo tono, validada contra ambas superficies.
 * - El color de estado nunca va solo: siempre lo acompaña un icono o una etiqueta.
 * - Las etiquetas visten tinta, nunca el color de la serie.
 */

import { type ReactNode, useState } from "react";

import { cx, scoreLabel, scoreTone, type StatusTone } from "./ui";

const TONE: Record<StatusTone, string> = {
  good: "var(--good)",
  warning: "var(--warning)",
  serious: "var(--serious)",
  critical: "var(--critical)",
  neutral: "var(--ink-muted)",
  accent: "var(--accent)",
};

const track = (fill: string) => `color-mix(in oklab, ${fill} 16%, var(--surface-2))`;

/* -------------------------------------------------------------------------- */
/* Cifra protagonista — exactamente una por vista                             */
/* -------------------------------------------------------------------------- */
export function HeroFigure({
  value,
  unit,
  label,
  caption,
  tone,
}: {
  value: number | null;
  unit?: string;
  label: string;
  caption?: ReactNode;
  tone?: StatusTone;
}) {
  const resolved = tone ?? scoreTone(value);
  return (
    <div className="flex flex-col">
      <span className="text-xs font-medium text-ink-secondary">{label}</span>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-5xl font-semibold leading-none tracking-tight text-ink">
          {value == null ? "—" : Math.round(value)}
        </span>
        {unit && <span className="text-lg text-ink-muted">{unit}</span>}
        {value != null && (
          <span className="ml-1 inline-flex items-center gap-1.5 text-xs text-ink-secondary">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: TONE[resolved] }}
            />
            {scoreLabel(value)}
          </span>
        )}
      </div>
      {caption && <p className="mt-2 text-sm text-ink-secondary">{caption}</p>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Stat tile / KPI row                                                        */
/* -------------------------------------------------------------------------- */
export function StatTile({
  label,
  value,
  unit,
  delta,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string | number;
  unit?: string;
  delta?: { value: number; period: string; upIsGood?: boolean };
  tone?: StatusTone;
  hint?: string;
}) {
  const deltaGood = delta ? (delta.upIsGood ?? true) === delta.value >= 0 : true;
  return (
    <div className="rounded-xl border bg-surface-1 px-4 py-3.5" title={hint}>
      <div className="flex items-center gap-1.5">
        {tone !== "neutral" && (
          <span
            aria-hidden
            className="inline-block h-2 w-2 shrink-0 rounded-full"
            style={{ background: TONE[tone] }}
          />
        )}
        <span className="text-xs font-medium text-ink-secondary">{label}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold leading-none text-ink">{value}</span>
        {unit && <span className="text-sm text-ink-muted">{unit}</span>}
      </div>
      {delta && (
        <p
          className="mt-1.5 text-xs"
          style={{ color: deltaGood ? "var(--success-text)" : "var(--critical)" }}
        >
          {delta.value >= 0 ? "+" : ""}
          {delta.value}% <span className="text-ink-muted">vs {delta.period}</span>
        </p>
      )}
    </div>
  );
}

export function KpiRow({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{children}</div>
  );
}

/* -------------------------------------------------------------------------- */
/* Medidor — una razón contra un límite                                       */
/* -------------------------------------------------------------------------- */
export function Meter({
  label,
  value,
  max = 100,
  tone,
  showValue = true,
  size = "md",
  description,
}: {
  label: string;
  value: number;
  max?: number;
  tone?: StatusTone;
  showValue?: boolean;
  size?: "sm" | "md";
  description?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const resolved = tone ?? scoreTone((value / max) * 100);
  const fill = TONE[resolved];

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-ink-secondary">{label}</span>
        {showValue && (
          <span className="tabular text-xs font-semibold text-ink">{Math.round(value)}</span>
        )}
      </div>
      <div
        role="meter"
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
        className={cx(
          "mt-1.5 w-full overflow-hidden rounded-full",
          size === "sm" ? "h-1.5" : "h-2",
        )}
        style={{ background: track(fill) }}
      >
        <div
          className="meter-fill h-full rounded-full transition-[width] duration-500"
          style={{ width: `${pct}%`, background: fill, color: fill }}
        />
      </div>
      {description && <p className="mt-1 text-xs text-ink-muted">{description}</p>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Barras horizontales — magnitud, un solo tono secuencial                     */
/* -------------------------------------------------------------------------- */
export function BarList({
  data,
  max,
  valueSuffix = "",
  emptyLabel = "Sin datos",
}: {
  data: { label: string; value: number }[];
  max?: number;
  valueSuffix?: string;
  emptyLabel?: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  if (!data.length) {
    return <p className="text-sm text-ink-muted">{emptyLabel}</p>;
  }
  const ceiling = max ?? Math.max(...data.map((d) => d.value));

  return (
    <ul className="space-y-2">
      {data.map((item) => {
        const pct = ceiling ? (item.value / ceiling) * 100 : 0;
        const active = hovered === item.label;
        return (
          <li
            key={item.label}
            className="group relative grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3"
            onMouseEnter={() => setHovered(item.label)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="truncate text-xs text-ink-secondary" title={item.label}>
              {item.label}
            </span>
            {/* Barra fina: 8px, extremo redondeado, base cuadrada contra el eje. */}
            <span className="block h-2 w-full rounded-sm" style={{ background: "var(--grid)" }}>
              <span
                className="block h-full rounded-r-sm transition-[width] duration-300"
                style={{
                  width: `${Math.max(pct, 2)}%`,
                  background: active ? "var(--accent-ink)" : "var(--accent)",
                }}
              />
            </span>
            <span className="tabular text-xs text-ink">
              {item.value}
              {valueSuffix}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/* -------------------------------------------------------------------------- */
/* Embudo del pipeline — rampa ordinal de un solo tono                        */
/* -------------------------------------------------------------------------- */
export interface FunnelStage {
  label: string;
  value: number;
}

const STAGE_COLORS = [
  "var(--stage-1)",
  "var(--stage-2)",
  "var(--stage-3)",
  "var(--stage-4)",
  "var(--stage-5)",
];

export function Funnel({ stages }: { stages: FunnelStage[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const top = stages[0]?.value ?? 0;

  if (!top) {
    return (
      <p className="text-sm text-ink-muted">
        Todavía no has postulado a nada. El embudo aparece con la primera aplicación.
      </p>
    );
  }

  return (
    <div>
      <ul className="space-y-1.5">
        {stages.map((stage, index) => {
          const pct = (stage.value / top) * 100;
          const previous = index > 0 ? stages[index - 1].value : null;
          const conversion =
            previous && previous > 0 ? Math.round((stage.value / previous) * 100) : null;
          const color = STAGE_COLORS[Math.min(index, STAGE_COLORS.length - 1)];

          return (
            <li
              key={stage.label}
              className="relative grid grid-cols-[minmax(0,10rem)_1fr] items-center gap-3"
              onMouseEnter={() => setHovered(index)}
              onMouseLeave={() => setHovered(null)}
            >
              <span className="truncate text-xs text-ink-secondary">{stage.label}</span>
              <div className="relative flex items-center gap-2">
                {/* 2px de aire en color de superficie separan barras contiguas. */}
                <span
                  className="block h-5 min-w-[3px] rounded-r-sm transition-[width] duration-500"
                  style={{ width: `${Math.max(pct, 1.5)}%`, background: color }}
                />
                <span className="tabular text-xs font-medium text-ink">{stage.value}</span>
                {conversion !== null && (
                  <span className="text-xs text-ink-muted">({conversion}%)</span>
                )}

                {hovered === index && (
                  <div
                    role="tooltip"
                    className="pointer-events-none absolute left-0 top-full z-20 mt-1 rounded-lg border bg-surface-1 px-3 py-2 text-xs shadow-lg"
                  >
                    <p className="font-medium text-ink">{stage.label}</p>
                    <p className="text-ink-secondary">
                      {stage.value} de {top} ({Math.round(pct)}% del total)
                    </p>
                    {conversion !== null && (
                      <p className="text-ink-secondary">
                        Conversión desde {stages[index - 1].label}: {conversion}%
                      </p>
                    )}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {/* Vista de tabla: la identidad nunca depende solo del color. */}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink-secondary">
          Ver como tabla
        </summary>
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="border-b text-left text-ink-muted">
              <th className="py-1 font-medium">Etapa</th>
              <th className="py-1 text-right font-medium">Cantidad</th>
              <th className="py-1 text-right font-medium">% del total</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {stages.map((stage) => (
              <tr key={stage.label} className="border-b last:border-0">
                <td className="py-1 text-ink-secondary">{stage.label}</td>
                <td className="py-1 text-right text-ink">{stage.value}</td>
                <td className="py-1 text-right text-ink-secondary">
                  {Math.round((stage.value / top) * 100)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Anillo de match — una razón contra un límite, en formato compacto           */
/* -------------------------------------------------------------------------- */
export function ScoreRing({
  value,
  size = 56,
  label,
}: {
  value: number;
  size?: number;
  label?: string;
}) {
  const tone = scoreTone(value);
  const color = TONE[tone];
  const stroke = 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, value)) / 100);

  return (
    <div className="flex items-center gap-2.5">
      <svg
        width={size}
        height={size}
        role="img"
        aria-label={`${label ?? "Match"}: ${Math.round(value)} de 100`}
        className="-rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={track(color)}
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 500ms" }}
        />
      </svg>
      <div className="leading-tight">
        <p className="text-lg font-semibold text-ink">{Math.round(value)}</p>
        <p className="text-xs text-ink-muted">{label ?? "match"}</p>
      </div>
    </div>
  );
}
