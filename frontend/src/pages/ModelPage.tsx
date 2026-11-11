import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Info, XCircle } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { ErrorBox, Loading, PageHeader, StatCard } from "../components/ui";

interface Status {
  ready: boolean;
  model_name: string;
  model_version: string;
  model_path: string;
  error: string | null;
  feature_columns: string[];
}
interface Metadata {
  model_name: string;
  model_version: string;
  training_date: string | null;
  metrics: Record<string, number | string>;
  limitations: string[];
  feature_columns: string[];
  categorical_columns: string[];
  numerical_columns: string[];
  validation: Record<string, unknown>;
}
interface Performance {
  generated_at: string;
  notebook_metrics: Record<string, number | string>;
  live_monitoring: {
    prediction_count: number;
    average_prediction: number;
    error_metrics: Record<string, unknown>;
  };
  limitations: string[];
  note: string;
}

export default function ModelPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [meta, setMeta] = useState<Metadata | null>(null);
  const [perf, setPerf] = useState<Performance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Status>("/api/model/status"),
      api.get<Metadata>("/api/model/metadata"),
      api.get<Performance>("/api/model/performance"),
    ])
      .then(([s, m, p]) => {
        setStatus(s.data);
        setMeta(m.data);
        setPerf(p.data);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading model info…" />;
  if (error) return <ErrorBox message={error} />;
  if (!status || !meta || !perf) return null;

  const m = perf.notebook_metrics;
  const live = perf.live_monitoring;
  const err = live.error_metrics;

  return (
    <div>
      <PageHeader
        title="Model performance"
        subtitle="Supplied Colab-trained RandomForest pipeline — baseline engine, not retrained"
      />

      {/* Status banner */}
      <div
        className={`mb-5 flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${
          status.ready
            ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
            : "border-red-300 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
        }`}
        role="status"
      >
        {status.ready ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
        <div>
          <p className="font-semibold">
            {status.ready ? "Model loaded and serving predictions" : "Model unavailable"}
          </p>
          <p className="text-xs opacity-80">
            {status.model_name} v{status.model_version}
            {status.error ? ` — ${status.error}` : ""}
          </p>
        </div>
      </div>

      {/* Notebook metrics */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="MAE" value={String(m.mae)} hint="Mean absolute error" accent="brand" />
        <StatCard label="RMSE" value={String(m.rmse)} hint="Root mean squared error" accent="brand" />
        <StatCard label="R²" value={String(m.r2)} hint="Explained variance" accent="amber" />
        <StatCard label="WAPE" value={`${m.wape_percent}%`} hint="Weighted absolute error" accent="red" />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Source: notebook saved outputs ({String(m.source ?? "Inventory_Demand_Prediction.ipynb")}) ·
        split {String(m.split_date)} · train {String(m.train_rows)} / test {String(m.test_rows)} rows
      </p>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* Live monitoring */}
        <section className="card p-5">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <Activity size={16} aria-hidden /> Live prediction monitoring
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
              <p className="text-xs text-slate-500">Predictions saved</p>
              <p className="text-xl font-bold tabular-nums">{live.prediction_count}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
              <p className="text-xs text-slate-500">Average prediction</p>
              <p className="text-xl font-bold tabular-nums">{live.average_prediction}</p>
            </div>
          </div>
          <div className="mt-4 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
            {err.available ? (
              <dl className="grid grid-cols-2 gap-2">
                {Object.entries(err)
                  .filter(([k]) => k !== "available" && k !== "matched_rows")
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <dt className="text-slate-500">{k.toUpperCase()}</dt>
                      <dd className="font-medium tabular-nums">{String(v)}</dd>
                    </div>
                  ))}
                <div className="flex justify-between">
                  <dt className="text-slate-500">Matched rows</dt>
                  <dd className="font-medium tabular-nums">{String(err.matched_rows)}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-slate-500">
                Prediction error will appear once actual sales exist for the same store,
                product and date ({String(err.matched_rows)} matched so far).
              </p>
            )}
          </div>
          <p className="mt-3 text-xs text-slate-500">{perf.note}</p>
        </section>

        {/* Validation & features */}
        <section className="card p-5">
          <h2 className="mb-3 text-sm font-semibold">Pipeline validation</h2>
          <pre className="mb-4 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-800">
            {JSON.stringify(meta.validation, null, 2)}
          </pre>

          <h2 className="mb-2 text-sm font-semibold">
            Features ({meta.feature_columns.length})
          </h2>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {meta.feature_columns.map((f) => (
              <span
                key={f}
                className={`rounded px-2 py-0.5 text-xs ${
                  meta.categorical_columns.includes(f)
                    ? "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-200"
                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
                }`}
              >
                {f}
              </span>
            ))}
          </div>
          <p className="text-xs text-slate-500">
            <span className="inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" /> categorical ·{" "}
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" /> numerical ·{" "}
            target Units Sold is excluded from features
          </p>
        </section>
      </div>

      {/* Limitations */}
      <section className="card mt-6 border-amber-300 p-5 dark:border-amber-900">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
          <Info size={16} aria-hidden /> Known limitations & leakage risks
        </h2>
        <ul className="list-disc space-y-2 pl-5 text-sm text-slate-600 dark:text-slate-300">
          {(perf.limitations.length ? perf.limitations : meta.limitations).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-500">
          Model file: <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-800">{status.model_path}</code>
        </p>
      </section>
    </div>
  );
}
