import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import ThemeToggle from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "Call Agent MVP",
  description: "Voice call-agent MVP with STT, TTS, scenarios and call sessions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-50">
        <ThemeProvider attribute="class" defaultTheme="system">
          <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6 md:px-10 md:py-10">
            <header className="sticky top-0 z-40 mb-6 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
              <div className="flex items-center justify-between gap-6 py-3">
                <a href="#hero" className="flex items-center gap-3 text-slate-900 dark:text-slate-50">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-950 shadow-sm dark:bg-slate-100">
                    <span className="text-sm font-bold text-white dark:text-slate-950">CA</span>
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-300">
                    Call Agent
                  </div>
                </a>

                <div className="flex items-center gap-4">
                  <nav className="hidden items-center gap-6 text-sm text-slate-500 md:flex dark:text-slate-300">
                    <a href="#hero" className="transition hover:text-slate-900 dark:hover:text-slate-50">
                      Обзор
                    </a>
                    <a href="#tools" className="transition hover:text-slate-900 dark:hover:text-slate-50">
                      Демо
                    </a>
                  </nav>
                  <ThemeToggle />
                </div>
              </div>
            </header>

            <main className="flex-1 pb-6">{children}</main>

            <footer className="mt-4 border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>{new Date().getFullYear()} Call Agent MVP.</span>
                <span>STT · TTS · сценарии · mock-телефония</span>
              </div>
            </footer>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
