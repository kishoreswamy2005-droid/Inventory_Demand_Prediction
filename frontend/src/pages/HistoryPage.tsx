import { Fragment, useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { EmptyState, ErrorBox, Loading, PageHeader } from "../components/ui";

interface HistoryItem {
  id: number;
  store_id: string;
  product_id: string;
  prediction_date: string;
  predicted_units_sold: number;
  model_name: string;
  model_version: string;
  created_at: string;
  input_features: Record<string, unknown>;
}
interface Page {
  items: HistoryItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export default function HistoryPage() {
  const [data, setData] = useState<Page | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      if (search) params.set("search", search);
      const res = await api.get<Page>(`/api/predictions/history?${params}`);
      setData(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    const t = window.setTimeout(load, search ? 300 : 0);
    return () => window.clearTimeout(t);
  }, [load, search]);

  return (
    <div>
      <PageHeader
        title="Prediction history"
        subtitle={data ? `${data.total} saved predictions` : "Every run is stored with its inputs"}
        actions={
          <div className="relative">
            <Search size={15} className="absolute left-3 top-2.5 text-slate-400" aria-hidden />
            <input
              className="input pl-9 sm:w-64"
              placeholder="Search store or product…"
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
              aria-label="Search predictions"
            />
          </div>
        }
      />

      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && (
        <EmptyState message="No predictions yet — run one on the Predict page." />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[820px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="th">#</th>
                  <th className="th">Created</th>
                  <th className="th">Store</th>
                  <th className="th">Product</th>
                  <th className="th">Target date</th>
                  <th className="th text-right">Predicted sales</th>
                  <th className="th">Model</th>
                  <th className="th text-right">Inputs</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((h) => (
                  <Fragment key={h.id}>
                    <tr className="border-b border-slate-100 dark:border-slate-800">
                      <td className="td tabular-nums">{h.id}</td>
                      <td className="td whitespace-nowrap">{new Date(h.created_at).toLocaleString()}</td>
                      <td className="td font-medium">{h.store_id}</td>
                      <td className="td font-medium">{h.product_id}</td>
                      <td className="td">{h.prediction_date}</td>
                      <td className="td text-right font-semibold tabular-nums">
                        {h.predicted_units_sold}
                      </td>
                      <td className="td text-xs text-slate-500">
                        {h.model_name} v{h.model_version}
                      </td>
                      <td className="td text-right">
                        <button
                          className="btn-ghost !px-2 !py-1 text-xs"
                          onClick={() => setExpanded(expanded === h.id ? null : h.id)}
                          aria-expanded={expanded === h.id}
                        >
                          {expanded === h.id ? "Hide" : "View"}
                        </button>
                      </td>
                    </tr>
                    {expanded === h.id && (
                      <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/40">
                        <td colSpan={8} className="td">
                          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                            Input features at prediction time
                          </p>
                          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
                            {Object.entries(h.input_features).map(([k, v]) => (
                              <div key={k} className="rounded bg-white px-2 py-1.5 text-xs dark:bg-slate-900">
                                <span className="block text-slate-400">{k}</span>
                                <span className="font-medium tabular-nums">{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
            <span>
              Page {data.page} of {data.pages}
            </span>
            <div className="flex gap-2">
              <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Prev
              </button>
              <button
                className="btn-ghost"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
