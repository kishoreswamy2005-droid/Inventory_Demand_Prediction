import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Boxes,
  PackageCheck,
  ShoppingCart,
  TrendingUp,
  TriangleAlert,
  Warehouse,
} from "lucide-react";
import api, { errorMessage } from "../api/client";
import { ErrorBox, Loading, PageHeader, StatCard } from "../components/ui";

interface Summary {
  total_products: number;
  total_stores: number;
  total_units_sold: number;
  current_inventory: number;
  predicted_demand: number;
  low_stock_products: number;
  overstocked_products: number;
  critical_stock_products: number;
  date_range: { start: string; end: string; min_record: string | null; max_record: string | null };
}
interface Point { label: string; value: number; secondary?: number | null }
interface Labeled { label: string; value: number }
interface ProductItem extends Labeled { category: string }
interface StoreItem extends Labeled { region: string; avg_units: number }

const money = (n: number) => n.toLocaleString();

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<Point[]>([]);
  const [granularity, setGranularity] = useState<"day" | "month">("month");
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<Labeled[]>([]);
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [overview, setOverview] = useState<Labeled[]>([]);
  const [avp, setAvp] = useState<{ note: string; points: Point[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.get<Summary>("/api/dashboard/summary"),
      api.get<{ points: Point[] }>(`/api/dashboard/sales-trend?granularity=${granularity}`),
      api.get<{ items: ProductItem[] }>("/api/dashboard/product-performance?top=10"),
      api.get<{ items: Labeled[] }>("/api/dashboard/category-performance"),
      api.get<{ items: StoreItem[] }>("/api/dashboard/store-performance"),
      api.get<{ items: Labeled[] }>("/api/dashboard/inventory-overview"),
      api.get<{ note: string; points: Point[] }>("/api/dashboard/actual-vs-predicted"),
    ])
      .then(([s, t, p, c, st, o, a]) => {
        if (cancelled) return;
        setSummary(s.data);
        setTrend(t.data.points);
        setProducts(p.data.items);
        setCategories(c.data.items);
        setStores(st.data.items);
        setOverview(o.data.items);
        setAvp(a.data);
      })
      .catch((err) => !cancelled && setError(errorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [granularity]);

  if (loading && !summary) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorBox message={error} />;
  if (!summary) return null;

  const range = summary.date_range;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={`Aggregated from ${range.min_record ?? range.start} to ${range.max_record ?? range.end}`}
      />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="Units sold" value={money(summary.total_units_sold)} hint="Historical total" accent="brand" />
        <StatCard label="Current inventory" value={money(summary.current_inventory)} hint="Latest records" accent="emerald" />
        <StatCard label="Low stock" value={summary.low_stock_products} hint="Products below threshold" accent="amber" />
        <StatCard label="Critical stock" value={summary.critical_stock_products} hint="≤ 1 day of cover" accent="red" />
        <StatCard label="Products" value={summary.total_products} />
        <StatCard label="Stores" value={summary.total_stores} />
        <StatCard label="Predicted demand" value={money(summary.predicted_demand)} hint="Sum of saved predictions" />
        <StatCard label="Overstocked" value={summary.overstocked_products} hint="> 30 days of cover" accent="emerald" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* Sales trend */}
        <section className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <TrendingUp size={16} aria-hidden /> Sales trend
            </h2>
            <div className="flex gap-1 rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
              {(["month", "day"] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => setGranularity(g)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    granularity === g
                      ? "bg-brand-600 text-white"
                      : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                  }`}
                >
                  {g === "month" ? "Monthly" : "Daily"}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trend} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.25} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={28} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip
                formatter={(v: number) => [money(v), "Units sold"]}
                contentStyle={{ borderRadius: 8, fontSize: 12 }}
              />
              <Line type="monotone" dataKey="value" stroke="#2543eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>

        {/* Actual vs predicted */}
        <section className="card p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
            <ShoppingCart size={16} aria-hidden /> Actual vs predicted sales
          </h2>
          <p className="mb-3 text-xs text-slate-500">{avp?.note}</p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={avp?.points ?? []} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.25} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={28} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="value" name="Actual units sold" stroke="#2543eb" strokeWidth={2} dot={false} />
              <Line
                type="monotone"
                dataKey="secondary"
                name="Predicted sales"
                stroke="#f59e0b"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </section>

        {/* Top products */}
        <section className="card p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Boxes size={16} aria-hidden /> Top products by units sold
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={products} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.25} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={70} />
              <Tooltip
                formatter={(v: number) => [money(v), "Units sold"]}
                labelFormatter={(l) => `Product ${l}`}
                contentStyle={{ borderRadius: 8, fontSize: 12 }}
              />
              <Bar dataKey="value" fill="#2543eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>

        {/* Category + store performance */}
        <section className="card p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <PackageCheck size={16} aria-hidden /> Units sold by category
          </h2>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={categories} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" strokeOpacity={0.25} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip formatter={(v: number) => [money(v), "Units sold"]} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <h2 className="mb-2 mt-4 flex items-center gap-2 text-sm font-semibold">
            <Warehouse size={16} aria-hidden /> Store performance
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="th">Store</th>
                  <th className="th">Region</th>
                  <th className="th text-right">Units sold</th>
                  <th className="th text-right">Avg / record</th>
                </tr>
              </thead>
              <tbody>
                {stores.map((s) => (
                  <tr key={s.label} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="td font-medium">{s.label}</td>
                    <td className="td">{s.region}</td>
                    <td className="td text-right tabular-nums">{money(s.value)}</td>
                    <td className="td text-right tabular-nums">{s.avg_units}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Inventory status overview */}
      <section className="card mt-6 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <TriangleAlert size={16} aria-hidden /> Inventory status overview
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {overview.map((o) => (
            <div key={o.label} className="rounded-lg bg-slate-50 p-3 text-center dark:bg-slate-800">
              <p className="text-lg font-bold tabular-nums">{money(o.value)}</p>
              <p className="mt-0.5 text-xs text-slate-500">{o.label}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
