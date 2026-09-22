"use client";

import type { DiffLine } from "@/lib/types";

/**
 * Diff palabra a palabra, estilo Git. Lo que se quita va tachado en rojo, lo que
 * entra en verde. El color de estado nunca va solo: el subrayado y el tachado
 * llevan la misma información sin depender de la vista cromática.
 */
export function WordDiff({ words }: { words: DiffLine[] }) {
  if (!words.length) return <span className="text-ink-muted">— sin cambios —</span>;

  return (
    <p className="text-sm leading-relaxed">
      {words.map((word, index) => {
        if (word.kind === "equal") {
          return (
            <span key={index} className="text-ink-secondary">
              {word.text}
            </span>
          );
        }
        const removed = word.kind === "delete";
        return (
          <span
            key={index}
            className={removed ? "line-through decoration-2" : "underline decoration-2"}
            style={{
              color: removed ? "var(--critical)" : "var(--success-text)",
              background: removed
                ? "color-mix(in oklab, var(--critical) 8%, transparent)"
                : "color-mix(in oklab, var(--good) 10%, transparent)",
            }}
          >
            {word.text}
          </span>
        );
      })}
    </p>
  );
}

export function DiffLegend() {
  return (
    <div className="flex items-center gap-4 text-xs text-ink-muted">
      <span className="flex items-center gap-1.5">
        <span className="line-through decoration-2" style={{ color: "var(--critical)" }}>
          texto
        </span>
        se elimina
      </span>
      <span className="flex items-center gap-1.5">
        <span className="underline decoration-2" style={{ color: "var(--success-text)" }}>
          texto
        </span>
        se añade
      </span>
    </div>
  );
}
