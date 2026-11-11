import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import api, { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Badge, EmptyState, ErrorBox, Loading, PageHeader, statusTone } from "../components/ui";

interface Record {
  id: number;
  store_id: string;
  product_id: string;
  date: string;
  category: string;
  region: string;
  inventory_level: number;
  units_sold: number;
  price: number;
  discount: number;
  weather_condition: string;
  seasonality: string;
  inventory_status: string | null;
  days_of_cover: number | null;
}
interface Page {
  items: Record[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
interface Filters {
  stores: string[];
  products: string[];
  categories: string[];
  regions: string[];
}

const EMPTY_FILTERS = { search: "", store: "", category: "", region: "", status: "" };

export default function InventoryPage() {
  const { user } = useAuth();
  const { push } = useToast();
  const isAdmin = user?.is_admin;

  const [data, setData] = useState<Page | null>(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [options, setOptions] = useState<Filters | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Record | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters.search) params.set("search", filters.search);
      if (filters.store) params.set("store", filters.store);
      if (filters.category) params.set("category", filters.category);
      if (filters.region) params.set("region", filters.region);
      if (filters.status) params.set("status", filters.status);
      params.set("page", String(page));
      params.set("page_size", "25");
      const res = await api.get<Page>(`/api/inventory?${params.toString()}`);
      setData(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api
      .get<Filters>("/api/dashboard/filters")
      .then((res) => setOptions(res.data))
      .catch(() => setOptions({ stores: [], products: [], categories: [], regions: [] }));
  }, []);

  const set = (key: keyof typeof EMPTY_FILTERS) => (value: string) => {
    setPage(1);
    setFilters((f) => ({ ...f, [key]: value }));
  };

  const remove = async (rec: Record) => {
    if (!window.confirm(`Delete record for ${rec.product_id} @ ${rec.store_id} on ${rec.date}?`)) return;
    try {
      await api.delete(`/api/inventory/${rec.id}`);
      push("success", "Record deleted");
      load();
    } catch (err) {
      push("error", errorMessage(err));
    }
  };

  return (
    <div>
      <PageHeader
        title="Inventory"
        subtitle={data ? `${data.total} records` : "Loading…"}
        actions={
          isAdmin ? (
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <Plus size={16} aria-hidden /> New record
            </button>
          ) : undefined
        }
      />

      {/* Filters */}
      <div className="card mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label className="label" htmlFor="f-search">Search</label>
          <input
            id="f-search"
            className="input"
            placeholder="Product or store ID"
            value={filters.search}
            onChange={(e) => set("search")(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="f-store">Store</label>
          <select id="f-store" className="input" value={filters.store} onChange={(e) => set("store")(e.target.value)}>
            <option value="">All stores</option>
            {options?.stores.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-cat">Category</label>
          <select id="f-cat" className="input" value={filters.category} onChange={(e) => set("category")(e.target.value)}>
            <option value="">All categories</option>
            {options?.categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-region">Region</label>
          <select id="f-region" className="input" value={filters.region} onChange={(e) => set("region")(e.target.value)}>
            <option value="">All regions</option>
            {options?.regions.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-status">Status</label>
          <select id="f-status" className="input" value={filters.status} onChange={(e) => set("status")(e.target.value)}>
            <option value="">All statuses</option>
            <option>Critical Stock</option>
            <option>Low Stock</option>
            <option>Healthy Stock</option>
            <option>Overstocked</option>
          </select>
        </div>
      </div>

      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && !loading && <EmptyState message="No inventory records match these filters." />}

      {data && data.items.length > 0 && (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="th">Date</th>
                  <th className="th">Store</th>
                  <th className="th">Product</th>
                  <th className="th">Category</th>
                  <th className="th text-right">Inventory</th>
                  <th className="th text-right">Units sold</th>
                  <th className="th text-right">Price</th>
                  <th className="th">Status</th>
                  <th className="th text-right">Cover</th>
                  {isAdmin && <th className="th text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50">
                    <td className="td whitespace-nowrap">{r.date}</td>
                    <td className="td font-medium">{r.store_id}</td>
                    <td className="td font-medium">{r.product_id}</td>
                    <td className="td">{r.category}</td>
                    <td className="td text-right tabular-nums">{r.inventory_level}</td>
                    <td className="td text-right tabular-nums">{r.units_sold}</td>
                    <td className="td text-right tabular-nums">${r.price.toFixed(2)}</td>
                    <td className="td">
                      {r.inventory_status ? (
                        <Badge tone={statusTone(r.inventory_status)}>{r.inventory_status}</Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="td text-right tabular-nums">
                      {r.days_of_cover != null ? `${r.days_of_cover.toFixed(1)} d` : "—"}
                    </td>
                    {isAdmin && (
                      <td className="td text-right">
                        <button
                          className="mr-1 rounded p-1 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700"
                          onClick={() => setEditing(r)}
                          aria-label={`Edit ${r.product_id}`}
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          className="rounded p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-950"
                          onClick={() => remove(r)}
                          aria-label={`Delete ${r.product_id}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
            <span>
              Page {data.page} of {data.pages} · {data.total} records
            </span>
            <div className="flex gap-2">
              <button
                className="btn-ghost"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={16} /> Prev
              </button>
              <button
                className="btn-ghost"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </>
      )}

      {editing && (
        <EditModal
          record={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            push("success", "Record updated");
            load();
          }}
        />
      )}
      {creating && (
        <CreateModal
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            push("success", "Record created");
            load();
          }}
        />
      )}
    </div>
  );
}

function EditModal({
  record,
  onClose,
  onSaved,
}: {
  record: Record;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { push } = useToast();
  const [level, setLevel] = useState(String(record.inventory_level));
  const [price, setPrice] = useState(String(record.price));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/api/inventory/${record.id}`, {
        inventory_level: Number(level),
        price: Number(price),
      });
      onSaved();
    } catch (err) {
      push("error", errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Edit ${record.product_id} @ ${record.store_id}`} onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="label" htmlFor="inv-level">Inventory level</label>
          <input id="inv-level" type="number" min={0} className="input" value={level} onChange={(e) => setLevel(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="inv-price">Price</label>
          <input id="inv-price" type="number" min={0} step="0.01" className="input" value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CreateModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { push } = useToast();
  const [form, setForm] = useState({
    store_id: "S001",
    product_id: "",
    date: new Date().toISOString().slice(0, 10),
    category: "Electronics",
    region: "East",
    inventory_level: "0",
    units_sold: "0",
    price: "0",
  });
  const [busy, setBusy] = useState(false);

  const update = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async () => {
    if (!form.product_id.trim()) {
      push("error", "Product ID is required");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/inventory", {
        ...form,
        inventory_level: Number(form.inventory_level),
        units_sold: Number(form.units_sold),
        price: Number(form.price),
      });
      onSaved();
    } catch (err) {
      push("error", errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="New inventory record" onClose={onClose}>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="c-store">Store ID</label>
          <input id="c-store" className="input" value={form.store_id} onChange={update("store_id")} />
        </div>
        <div>
          <label className="label" htmlFor="c-product">Product ID *</label>
          <input id="c-product" className="input" value={form.product_id} onChange={update("product_id")} placeholder="P0001" />
        </div>
        <div>
          <label className="label" htmlFor="c-date">Date</label>
          <input id="c-date" type="date" className="input" value={form.date} onChange={update("date")} />
        </div>
        <div>
          <label className="label" htmlFor="c-cat">Category</label>
          <select id="c-cat" className="input" value={form.category} onChange={update("category")}>
            {["Clothing", "Electronics", "Furniture", "Groceries", "Toys"].map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="c-region">Region</label>
          <select id="c-region" className="input" value={form.region} onChange={update("region")}>
            {["East", "North", "South", "West"].map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="c-level">Inventory level</label>
          <input id="c-level" type="number" min={0} className="input" value={form.inventory_level} onChange={update("inventory_level")} />
        </div>
        <div>
          <label className="label" htmlFor="c-sold">Units sold</label>
          <input id="c-sold" type="number" min={0} className="input" value={form.units_sold} onChange={update("units_sold")} />
        </div>
        <div>
          <label className="label" htmlFor="c-price">Price</label>
          <input id="c-price" type="number" min={0} step="0.01" className="input" value={form.price} onChange={update("price")} />
        </div>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={save} disabled={busy}>
          {busy ? "Creating…" : "Create"}
        </button>
      </div>
    </Modal>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div className="card relative w-full max-w-md p-5" role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="mb-4 text-base font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
