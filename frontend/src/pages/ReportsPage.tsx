import { useCallback, useEffect, useState } from "react";
import { Download, FileSpreadsheet } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { ErrorBox, Loading, PageHeader } from "../components/ui";

type ReportType = "sales" | "inventory" | "predictions";
interface ReportResponse {
  report_type: string;
  generated_at: string;
  filters: Record<string, string | null>;
  row_count: number;
  rows: Record<string, unknown>[];
}

const TABS: { id: ReportType; label: string }[] = [
  { id: "sales", label: "Sales" },
  { id: "inventory", label: "Inventory" },
  { id: "predictions", label: "Predictions" },
];

export default function ReportsPage() {
  const [type, setType] = useState<ReportType>("sales");
  const [data, setData] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ start: "", end: "", store: "", category: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters.start) params.set("start", filters.start);
      if (filters.end) params.set("end", filters.end);
      if (filters.store) params.set("store", filters.store);
      if (filters.category) params.set("category", filters.category);
      const res = await api.get<ReportResponse>(`/api/reports/${type}?${params}`);
      setData(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [type, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const downloadCsv = async () => {
    try {
      const params = new URLSearchParams({ report: type });
      if (filters.start) params.set("start", filters.start);
      if (filters.end) params.set("end", filters.end);
      if (filters.store) params.set("store", filters.store);
      if (filters.category) params.set("category", filters.category);
      const res = await api.get<Blob>(`/api/reports/export/csv?${params}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${type}_report.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const columns = data?.rows.length ? Object.keys(data.rows[0]) : [];

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Aggregated from database records — exports include exactly the rows shown"
        actions={
          <button className="btn-primary" onClick={downloadCsv} disabled={!data}>
            <Download size={15} aria-hidden /> Export CSV
          </button>
        }
      />

      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-lg border border-slate-200 p-1 dark:border-slate-700 sm:w-fit">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setType(t.id)}
            className={`flex-1 rounded-md px-4 py-1.5 text-sm font-medium transition sm:flex-none ${
              type === t.id
                ? "bg-brand-600 text-white"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="card mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="label" htmlFor="rp-start">Start date</label>
          <input id="rp-start" type="date" className="input" value={filters.start}
            onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))} />
        </div>
        <div>
          <label className="label" htmlFor="rp-end">End date</label>
          <input id="rp-end" type="date" className="input" value={filters.end}
            onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))} />
        </div>
        <div>
          <label className="label" htmlFor="rp-store">Store ID</label>
          <input id="rp-store" className="input" placeholder="e.g. S001" value={filters.store}
            onChange={(e) => setFilters((f) => ({ ...f, store: e.target.value }))} />
        </div>
        <div>
          <label className="label" htmlFor="rp-cat">Category</label>
          <input id="rp-cat" className="input" placeholder="e.g. Electronics" value={filters.category}
            onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))} />
        </div>
      </div>

      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading label="Running report…" />}

      {data && (
        <div className="card overflow-x-auto">
          <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-slate-700">
            <FileSpreadsheet size={14} aria-hidden />
            {data.row_count} rows · generated {new Date(data.generated_at).toLocaleString()}
          </div>
          {data.rows.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500">
              No rows match these filters.
            </p>
          ) : (
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  {columns.map((c) => (
                    <th key={c} className="th">{c.replace(/_/g, " ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50">
                    {columns.map((c) => (
                      <td key={c} className="td whitespace-nowrap tabular-nums">
                        {row[c] == null ? "—" : String(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
