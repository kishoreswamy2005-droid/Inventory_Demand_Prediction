import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, History, Upload } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Badge, EmptyState, ErrorBox, Loading, PageHeader } from "../components/ui";

interface ImportSummary {
  job_id: number;
  filename: string;
  status: string;
  total_rows: number;
  imported_rows: number;
  updated_rows: number;
  skipped_rows: number;
  invalid_rows: number;
  errors: { type: string; message: string; count?: number; rows?: number[] }[];
  preview: Record<string, string>[];
  missing_columns: string[];
  duplicate_rows: number;
  missing_value_cells: number;
}

export default function ImportPage() {
  const { user } = useAuth();
  const { push } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [jobs, setJobs] = useState<ImportSummary[] | null>(null);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<ImportSummary[]>("/api/import/jobs");
      setJobs(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const upload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      push("error", "Only .csv files are accepted");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post<ImportSummary>("/api/import/csv", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
      push(
        "success",
        `Import finished: ${res.data.imported_rows} new, ${res.data.updated_rows} updated, ${res.data.invalid_rows} invalid`
      );
      loadJobs();
    } catch (err) {
      push("error", errorMessage(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (!user?.is_admin) {
    return (
      <div>
        <PageHeader title="CSV import" />
        <EmptyState message="Administrator privileges are required to import data." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="CSV import"
        subtitle="Idempotent upsert on (store, product, date) — re-importing never duplicates rows"
      />

      {error && <ErrorBox message={error} />}

      {/* Upload area */}
      <div
        className={`card mb-5 border-2 border-dashed p-8 text-center transition ${
          dragOver
            ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
            : "border-slate-300 dark:border-slate-700"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files[0];
          if (f) upload(f);
        }}
      >
        <FileUp size={32} className="mx-auto mb-3 text-slate-400" aria-hidden />
        <p className="text-sm font-medium">Drag & drop a CSV file here</p>
        <p className="mt-1 text-xs text-slate-500">
          Required columns: Date, Store ID, Product ID, Category, Region, Inventory Level,
          Units Sold, Units Ordered, Demand Forecast, Price, Discount, Weather Condition,
          Holiday/Promotion, Competitor Pricing, Seasonality
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          id="csv-file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
          }}
        />
        <button
          className="btn-primary mt-4"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
        >
          <Upload size={16} aria-hidden />
          {uploading ? "Importing…" : "Choose file"}
        </button>
      </div>

      {/* Latest result */}
      {result && (
        <section className="card mb-5 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Result: {result.filename}</h2>
            <Badge tone={result.status === "completed" ? "healthy" : "critical"}>
              {result.status}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Total rows", result.total_rows],
              ["Imported", result.imported_rows],
              ["Updated", result.updated_rows],
              ["Invalid", result.invalid_rows],
              ["Duplicates", result.duplicate_rows],
              ["Missing cells", result.missing_value_cells],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800">
                <p className="text-lg font-bold tabular-nums">{value}</p>
                <p className="text-xs text-slate-500">{label}</p>
              </div>
            ))}
          </div>

          {result.missing_columns.length > 0 && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
              Missing columns: {result.missing_columns.join(", ")}
            </p>
          )}
          {result.errors.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-700 dark:text-amber-300">
              {result.errors.map((e, i) => (
                <li key={i}>
                  {e.message}
                  {e.count != null && ` (${e.count} rows)`}
                  {e.rows?.length ? ` — e.g. CSV rows ${e.rows.slice(0, 5).join(", ")}` : ""}
                </li>
              ))}
            </ul>
          )}
          {result.preview.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium text-slate-500">
                First 10 rows preview
              </summary>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      {Object.keys(result.preview[0]).map((k) => (
                        <th key={k} className="th">{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.preview.map((row, i) => (
                      <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                        {Object.values(row).map((v, j) => (
                          <td key={j} className="td whitespace-nowrap">{v}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </section>
      )}

      {/* Job history */}
      <section className="card overflow-x-auto">
        <h2 className="flex items-center gap-2 border-b border-slate-200 px-4 py-3 text-sm font-semibold dark:border-slate-700">
          <History size={15} aria-hidden /> Import history
        </h2>
        {loading && !jobs && <Loading />}
        {jobs && jobs.length === 0 && <EmptyState message="No imports yet." />}
        {jobs && jobs.length > 0 && (
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="th">#</th>
                <th className="th">File</th>
                <th className="th">Status</th>
                <th className="th text-right">Rows</th>
                <th className="th text-right">Imported</th>
                <th className="th text-right">Updated</th>
                <th className="th text-right">Invalid</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.job_id} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="td tabular-nums">{j.job_id}</td>
                  <td className="td font-medium">{j.filename}</td>
                  <td className="td">
                    <Badge tone={j.status === "completed" ? "healthy" : "critical"}>{j.status}</Badge>
                  </td>
                  <td className="td text-right tabular-nums">{j.total_rows}</td>
                  <td className="td text-right tabular-nums">{j.imported_rows}</td>
                  <td className="td text-right tabular-nums">{j.updated_rows}</td>
                  <td className="td text-right tabular-nums">{j.invalid_rows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
