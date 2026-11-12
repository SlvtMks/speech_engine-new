'use client';

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";

const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setMounted(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  if (!mounted) {
    return <div className="h-6 w-40 rounded-full bg-slate-100 dark:bg-slate-800" />;
  }

  const renderButton = (value: "light" | "dark" | "system", label: string) => (
    <button
      type="button"
      onClick={() => setTheme(value)}
      className={`px-2 py-0.5 text-xs rounded-full transition ${
        theme === value
          ? "bg-slate-900 text-slate-50 dark:bg-slate-50 dark:text-slate-900"
          : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-1 py-0.5 dark:bg-slate-800">
      {renderButton("light", "Light")}
      {renderButton("dark", "Dark")}
      {renderButton("system", "System")}
    </div>
  );
};

export default ThemeToggle;

