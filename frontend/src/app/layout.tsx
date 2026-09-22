import type { Metadata } from "next";

import { Sidebar } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Career Copilot",
  description: "Copiloto de postulación: CV, matching, pipeline e inteligencia de vacantes.",
};

/** Aplica el tema guardado antes del primer pintado para evitar el parpadeo. */
const THEME_SCRIPT = `
try {
  var t = localStorage.getItem('theme');
  if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="antialiased">
        <div className="flex">
          <Sidebar />
          <main className="h-dvh flex-1 overflow-y-auto px-8 py-8">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
