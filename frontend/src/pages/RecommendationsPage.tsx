import { useCallback, useEffect, useState } from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { Badge, EmptyState, ErrorBox, Loading, PageHeader, statusTone } from "../components/ui";

interface Recommendation {
  product_id: string;
  store_id: string;
  category: string;
  region: string;
  current_inventory: number;
  predicted_sales: number;
  avg_daily_sales: number;
  safety_stock: number;
  demand_during_lead_time: number;
  recommended_reorder_quantity: number;
  days_of_cover: number | null;
  risk_level: string;
  reason: string;
  assumptions: Record<string, unknown>;
  illustrative: boolean;
}
interface LowStockItem {
  product_id: string;
  store_id: string;
  category: string;
  current_inventory: number;
  avg_daily_sales: number;
  days_of_cover: number;
  risk_level: string;
}

const riskTone = (r: string) =>
  r === "Critical" ? "critical" : r === "High" ? "low" : r === "Medium" ? "overstock" : "healthy";

export default function RecommendationsPage() {
  const { push } = useToast();
  const [items, setItems] = useState<Recommendation[] | null>(null);
  const [low, setLow] = useState<{ threshold_days: number; count: number; items: LowStockItem[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState({
    lead_time_days: "7",
    service_level: "0.95",
    reorder_threshold_days: "3",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        lead_time_days: config.lead_time_days,
        service_level: config.service_level,
        reorder_threshold_days: config.reorder_threshold_days,
        limit: "100",
      });
      const [reorder, lowStock] = await Promise.all([
        api.get<Recommendation[]>(`/api/recommendations/reorder?${params}`),
        api.get<{ threshold_days: number; count: number; items: LowStockItem[] }>(
          `/api/recommendations/low-stock?threshold_days=${config.reorder_threshold_days}`
        ),
      ]);
      setItems(reorder.data);
      setLow(lowStock.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [config]);

  useEffect(() => {
    load();
  }, [load]);

  const update = (key: keyof typeof config) => (e: { target: { value: string } }) =>
    setConfig((c) => ({ ...c, [key]: e.target.value }));

  return (
    <div>
      <PageHeader
        title="Reorder recommendations"
        subtitle="Expected demand over lead time + safety stock − available inventory"
        actions={
          <button className="btn-ghost" onClick={load} disabled={loading}>
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} aria-hidden /> Refresh
          </button>
        }
      />

      {/* Configurable assumptions */}
      <div className="card mb-5 grid gap-4 p-4 sm:grid-cols-3 lg:grid-cols-4">
        <div>
          <label className="label" htmlFor="r-lead">Lead time (days)</label>
          <input id="r-lead" type="number" min={0} max={365} className="input" value={config.lead_time_days} onChange={update("lead_time_days")} />
        </div>
        <div>
          <label className="label" htmlFor="r-service">Service level</label>
          <select id="r-service" className="input" value={config.service_level} onChange={update("service_level")}>
            <option value="0.90">90%</option>
            <option value="0.95">95%</option>
            <option value="0.99">99%</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="r-threshold">Reorder threshold (days)</label>
          <input id="r-threshold" type="number" min={0} max={365} className="input" value={config.reorder_threshold_days} onChange={update("reorder_threshold_days")} />
        </div>
        <div className="flex items-end">
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-200">
            Lead time and service level are assumptions — results are illustrative.
          </p>
        </div>
      </div>

      {error && <ErrorBox message={error} />}
      {loading && !items && <Loading label="Computing recommendations…" />}

      {/* Low stock */}
      {low && low.items.length > 0 && (
        <section className="card mb-5 overflow-x-auto p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <TriangleAlert size={16} className="text-amber-500" aria-hidden />
            Low stock (≤ {low.threshold_days} days of cover) · {low.count}
          </h2>
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="th">Store</th>
                <th className="th">Product</th>
                <th className="th">Category</th>
                <th className="th text-right">Inventory</th>
                <th className="th text-right">Avg daily</th>
                <th className="th text-right">Cover</th>
                <th className="th">Risk</th>
              </tr>
            </thead>
            <tbody>
              {low.items.map((i) => (
                <tr key={`${i.store_id}-${i.product_id}`} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="td font-medium">{i.store_id}</td>
                  <td className="td font-medium">{i.product_id}</td>
                  <td className="td">{i.category}</td>
                  <td className="td text-right tabular-nums">{i.current_inventory}</td>
                  <td className="td text-right tabular-nums">{i.avg_daily_sales}</td>
                  <td className="td text-right tabular-nums">{i.days_of_cover} d</td>
                  <td className="td"><Badge tone={riskTone(i.risk_level)}>{i.risk_level}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Reorder table */}
      {items && items.length === 0 && !loading && (
        <EmptyState message="No inventory pairs found for these filters." />
      )}
      {items && items.length > 0 && (
        <section className="card overflow-x-auto">
          <table className="w-full min-w-[980px]">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="th">Store</th>
                <th className="th">Product</th>
                <th className="th text-right">Inventory</th>
                <th className="th text-right">Predicted sales/day</th>
                <th className="th text-right">Lead demand</th>
                <th className="th text-right">Safety stock</th>
                <th className="th text-right">Reorder qty</th>
                <th className="th text-right">Cover</th>
                <th className="th">Risk</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={`${r.store_id}-${r.product_id}`}
                  className="border-b border-slate-100 align-top hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
                  title={r.reason}
                >
                  <td className="td font-medium">{r.store_id}</td>
                  <td className="td font-medium">{r.product_id}</td>
                  <td className="td text-right tabular-nums">{r.current_inventory}</td>
                  <td className="td text-right tabular-nums">{r.predicted_sales}</td>
                  <td className="td text-right tabular-nums">{r.demand_during_lead_time}</td>
                  <td className="td text-right tabular-nums">{r.safety_stock}</td>
                  <td className="td text-right font-semibold tabular-nums">
                    {r.recommended_reorder_quantity > 0 ? r.recommended_reorder_quantity : "—"}
                  </td>
                  <td className="td text-right tabular-nums">
                    {r.days_of_cover != null ? `${r.days_of_cover} d` : "n/a"}
                  </td>
                  <td className="td"><Badge tone={riskTone(r.risk_level)}>{r.risk_level}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
