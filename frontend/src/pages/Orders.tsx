import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type Order = { id: number; user_id: number; status: string; total: string; created_at: string };
type OrderDetail = Order & { items: Array<{ id: number; plan_id: number; quantity: number; unit_price: string; product_name?: string; plan_name?: string; price?: string; duration_days?: number; quota_gb?: number; category?: string }> };

export default function Orders() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const [rows, setRows] = useState<Order[]>([]);
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    if (!tenantId) { setError("ابتدا یک Tenant را از بخش Tenantها انتخاب کنید."); setLoading(false); return; }
    setLoading(true);
    try { setRows(await api.get<Order[]>(`/orders?tenant_id=${tenantId}&limit=100`)); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : "خطای دریافت سفارش‌ها"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [tenantId]);

  const filtered = useMemo(() => { const q = query.trim().toLowerCase(); return q ? rows.filter((o) => [o.id, o.user_id, o.status, o.total].some((v) => String(v).toLowerCase().includes(q))) : rows; }, [rows, query]);
  const open = async (id: number) => {
    try { setSelected(await api.get<OrderDetail>(`/orders/${id}?tenant_id=${tenantId}`)); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : "خطای دریافت جزئیات سفارش"); }
  };

  return <section className="page"><div className="page-heading"><div><h2>سفارش‌ها</h2><p>مدیریت و بررسی سفارش‌های Tenant انتخاب‌شده.</p></div><button onClick={() => void load()} disabled={loading}>بروزرسانی</button></div>{error && <div className="alert error">{error}</div>}<div className="card" style={{ marginBottom: 18 }}><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو با شماره سفارش، کاربر، وضعیت یا مبلغ..." /></div><div className="card table-wrap">{loading ? <div className="state">در حال دریافت...</div> : !filtered.length ? <div className="state">سفارشی وجود ندارد.</div> : <table className="table"><thead><tr><th>#</th><th>کاربر</th><th>وضعیت</th><th>مبلغ</th><th>تاریخ</th><th>جزئیات</th></tr></thead><tbody>{filtered.map((o) => <tr key={o.id}><td>#{o.id}</td><td>#{o.user_id}</td><td><span className="badge">{o.status}</span></td><td>{new Intl.NumberFormat("fa-IR").format(Number(o.total))} تومان</td><td>{new Date(o.created_at).toLocaleString("fa-IR")}</td><td><button onClick={() => void open(o.id)}>مشاهده</button></td></tr>)}</tbody></table>}</div>{selected && <div className="card" style={{ marginTop: 18 }}><div className="page-heading"><div><h3>سفارش #{selected.id}</h3><p>کاربر #{selected.user_id} · {selected.status}</p></div><button onClick={() => setSelected(null)}>بستن</button></div><p>مبلغ کل: <strong>{new Intl.NumberFormat("fa-IR").format(Number(selected.total))} تومان</strong></p><div className="table-wrap"><table className="table"><thead><tr><th>محصول</th><th>پلن</th><th>تعداد</th><th>قیمت</th><th>مدت</th><th>حجم</th></tr></thead><tbody>{selected.items.map((item) => <tr key={item.id}><td>{item.product_name || "—"}</td><td>{item.plan_name || `#${item.plan_id}`}</td><td>{item.quantity}</td><td>{item.price ? `${new Intl.NumberFormat("fa-IR").format(Number(item.price))} تومان` : `${item.unit_price} تومان`}</td><td>{item.duration_days ? `${item.duration_days} روز` : "—"}</td><td>{item.quota_gb == null ? "نامحدود" : `${item.quota_gb} GB`}</td></tr>)}</tbody></table></div></div>}</section>;
}
