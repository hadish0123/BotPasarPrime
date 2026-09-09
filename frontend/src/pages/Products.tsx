import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { api } from "../api";
import "./products-admin.css";

type Product = {
  id: number;
  name: string;
  description?: string | null;
  category?: string | null;
  active: boolean;
};

type Plan = {
  id: number;
  name: string;
  base_price: string;
  discount: string;
  price: string;
  duration_days: number;
  quota_gb?: number | null;
  active: boolean;
};

export default function Products() {
  const [tenantId, setTenantId] = useState(localStorage.getItem("tenant_id") || "");
  const [products, setProducts] = useState<Product[]>([]);
  const [plans, setPlans] = useState<Record<number, Plan[]>>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) {
      setError("شناسه Tenant را وارد کنید.");
      return;
    }
    localStorage.setItem("tenant_id", tenantId);
    setLoading(true);
    setError("");
    try {
      const rows = await api.get<Product[]>(
        `/shop/products?tenant_id=${encodeURIComponent(tenantId)}`,
      );
      setProducts(rows);
      const entries = await Promise.all(
        rows.map(async (product) => {
          const data = await api.get<Plan[]>(
            `/shop/products/${product.id}/plans?tenant_id=${encodeURIComponent(tenantId)}`,
          );
          return [product.id, data] as const;
        }),
      );
      setPlans(Object.fromEntries(entries));
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای دریافت محصولات");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = products.filter((product) =>
    `${product.name} ${product.category || ""}`.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2>محصولات و پلن‌ها</h2>
          <p>قیمت و پلن از API واقعی Tenant خوانده می‌شود.</p>
        </div>
        <button className="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={16} /> {loading ? "در حال دریافت…" : "به‌روزرسانی"}
        </button>
      </div>

      <div className="card toolbar">
        <label>
          Tenant ID
          <input
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="grow">
          جستجو
          <div className="input-icon">
            <Search size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="نام محصول یا دسته‌بندی"
            />
          </div>
        </label>
      </div>

      {error && <div className="alert error">{error}</div>}
      {!loading && !error && filtered.length === 0 && (
        <div className="card empty">محصول فعالی برای این Tenant پیدا نشد.</div>
      )}

      <div className="grid">
        {filtered.map((product) => (
          <article className="card" key={product.id}>
            <div className="row-between">
              <div>
                <h3>{product.name}</h3>
                <span className="muted">
                  #{product.id} · {product.category || "بدون دسته"}
                </span>
              </div>
              <span className="badge">فعال</span>
            </div>
            {product.description && <p>{product.description}</p>}
            <div className="plans">
              {(plans[product.id] || []).map((plan) => (
                <div className="plan" key={plan.id}>
                  <strong>{plan.name}</strong>
                  <span>
                    {plan.price} · {plan.duration_days} روز · {plan.quota_gb ?? "∞"} GB
                  </span>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
