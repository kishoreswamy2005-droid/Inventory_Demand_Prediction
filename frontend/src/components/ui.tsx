import type { ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-slate-500">
      <Loader2 size={18} className="animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
      role="alert"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  accent = "brand",
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "brand" | "amber" | "red" | "emerald";
}) {
  const accents = {
    brand: "border-l-brand-500",
    amber: "border-l-amber-500",
    red: "border-l-red-500",
    emerald: "border-l-emerald-500",
  };
  const display = typeof value === "number" ? value.toLocaleString("en-US") : value;
  return (
    <div className={`card border-l-4 p-4 ${accents[accent]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{display}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <p className="py-8 text-center text-sm text-slate-500">{message}</p>
  );
}

export function Badge({ tone, children }: { tone: "critical" | "low" | "healthy" | "overstock"; children: ReactNode }) {
  const tones = {
    critical: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200",
    low: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-200",
    healthy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
    overstock: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function statusTone(status: string): "critical" | "low" | "healthy" | "overstock" {
  if (status.startsWith("Critical")) return "critical";
  if (status.startsWith("Low")) return "low";
  if (status.startsWith("Overstock")) return "overstock";
  return "healthy";
}
