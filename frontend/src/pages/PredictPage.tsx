import { useEffect, useState, type FormEvent } from "react";
import { Cpu, Info, Sparkles } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { ErrorBox, Loading, PageHeader } from "../components/ui";

interface FilterOptions {
  stores: string[];
  products: string[];
  categories: string[];
  regions: string[];
}
interface PredictionResult {
  id: number;
  store_id: string;
  product_id: string;
  prediction_date: string;
  predicted_units_sold: number;
  predicted_units_sold_raw: number;
  model_name: string;
  model_version: string;
  status: string;
  rounding: string;
  input_features: Record<string, unknown>;
}

const WEATHER = ["Sunny", "Cloudy", "Rainy", "Snowy"];
const SEASONS = ["Spring", "Summer", "Autumn", "Winter"];

export default function PredictPage() {
  const { push } = useToast();
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    store_id: "S001",
    product_id: "",
    category: "Electronics",
    region: "East",
    inventory_level: "100",
    price: "99.99",
    discount: "0",
    weather_condition: "Sunny",
    holiday_promotion: "0",
    competitor_pricing: "95.0",
    seasonality: "Winter",
    prediction_date: new Date().toISOString().slice(0, 10),
  });

  useEffect(() => {
    api
      .get<FilterOptions>("/api/dashboard/filters")
      .then((res) => {
        setOptions(res.data);
        setForm((f) => ({ ...f, product_id: res.data.products[0] ?? "" }));
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, []);

  const update = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const res = await api.post<PredictionResult>("/api/predictions/predict", {
        ...form,
        inventory_level: Number(form.inventory_level),
        price: Number(form.price),
        discount: Number(form.discount),
        holiday_promotion: Number(form.holiday_promotion),
        competitor_pricing: Number(form.competitor_pricing),
      });
      setResult(res.data);
      push("success", "Prediction completed and saved to history");
    } catch (err) {
      push("error", errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (loadError) return <ErrorBox message={loadError} />;
  if (!options && !loadError) return <Loading label="Loading options…" />;

  return (
    <div>
      <PageHeader
        title="Predict demand"
        subtitle="Runs the supplied Colab-trained RandomForest pipeline — the model is never retrained."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <form onSubmit={onSubmit} className="card p-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="label" htmlFor="p-store">Store</label>
              <select id="p-store" className="input" value={form.store_id} onChange={update("store_id")} required>
                {options?.stores.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-product">Product</label>
              <select id="p-product" className="input" value={form.product_id} onChange={update("product_id")} required>
                {options?.products.map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-date">Prediction date</label>
              <input id="p-date" type="date" className="input" value={form.prediction_date} onChange={update("prediction_date")} required />
            </div>
            <div>
              <label className="label" htmlFor="p-category">Category</label>
              <select id="p-category" className="input" value={form.category} onChange={update("category")}>
                {options?.categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-region">Region</label>
              <select id="p-region" className="input" value={form.region} onChange={update("region")}>
                {options?.regions.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-inventory">Inventory level</label>
              <input id="p-inventory" type="number" min={0} className="input" value={form.inventory_level} onChange={update("inventory_level")} required />
            </div>
            <div>
              <label className="label" htmlFor="p-price">Price ($)</label>
              <input id="p-price" type="number" min={0} step="0.01" className="input" value={form.price} onChange={update("price")} required />
            </div>
            <div>
              <label className="label" htmlFor="p-discount">Discount (%)</label>
              <input id="p-discount" type="number" min={0} max={100} className="input" value={form.discount} onChange={update("discount")} required />
            </div>
            <div>
              <label className="label" htmlFor="p-competitor">Competitor pricing ($)</label>
              <input id="p-competitor" type="number" min={0} step="0.01" className="input" value={form.competitor_pricing} onChange={update("competitor_pricing")} required />
            </div>
            <div>
              <label className="label" htmlFor="p-weather">Weather</label>
              <select id="p-weather" className="input" value={form.weather_condition} onChange={update("weather_condition")}>
                {WEATHER.map((w) => <option key={w}>{w}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-season">Seasonality</label>
              <select id="p-season" className="input" value={form.seasonality} onChange={update("seasonality")}>
                {SEASONS.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p-holiday">Holiday / promotion</label>
              <select id="p-holiday" className="input" value={form.holiday_promotion} onChange={update("holiday_promotion")}>
                <option value="0">No</option>
                <option value="1">Yes</option>
              </select>
            </div>
          </div>

          <button type="submit" disabled={busy} className="btn-primary mt-5">
            <Sparkles size={16} aria-hidden />
            {busy ? "Predicting…" : "Run prediction"}
          </button>
        </form>

        {/* Result panel */}
        <div className="space-y-4">
          {result && (
            <div className="card border-emerald-300 p-5 dark:border-emerald-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Predicted sales
              </p>
              <p className="mt-1 text-4xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                {result.predicted_units_sold}
                <span className="ml-1 text-sm font-medium text-slate-500">units</span>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Raw model output: {result.predicted_units_sold_raw.toFixed(3)}
              </p>
              <dl className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Product</dt>
                  <dd className="font-medium">{result.product_id} @ {result.store_id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Date</dt>
                  <dd className="font-medium">{result.prediction_date}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Model</dt>
                  <dd className="font-medium">{result.model_name} v{result.model_version}</dd>
                </div>
              </dl>
              <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500 dark:bg-slate-800">
                {result.rounding}
              </p>
            </div>
          )}

          <div className="card p-4 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700 dark:text-slate-200">
              <Info size={14} aria-hidden /> How to read this
            </h2>
            <ul className="list-disc space-y-1.5 pl-4">
              <li>Output is <strong>predicted sales</strong>, not guaranteed demand.</li>
              <li>
                <strong>Inventory Level</strong> timing is unverified — if it is measured
                after sales, it leaks same-day information.
              </li>
              <li>
                <strong>Units Sold</strong> is censored when a product is out of stock,
                so true demand may be higher.
              </li>
              <li>
                Notebook WAPE ≈ 51%: use predictions as directional planning aids.
              </li>
            </ul>
          </div>

          <div className="card flex items-start gap-2 p-4 text-xs text-slate-500">
            <Cpu size={14} className="mt-0.5 shrink-0" aria-hidden />
            Every prediction is stored in History with its input features for audit.
          </div>
        </div>
      </div>
    </div>
  );
}
