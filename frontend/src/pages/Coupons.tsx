import { useEffect, useState } from "react";
import { api } from "../api";

type Coupon = { id: number; tenant_id: number; code: string; kind: string; value: string; max_discount: string | null; min_purchase: string; usage_limit: number | null; used_count: number; active: boolean; starts_at: string | null; expires_at: string | null };

export default function Coupons() {
  const [items, setItems] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [code, setCode] = useState("");
  const [value, setValue] = useState("");
  const [kind, setKind] = useState("fixed");
  const [tenantId, setTenantId] = useState("");

  async function load() {
    setLoading(true); setError("");
    try { setItems(await api.get<Coupon[]>("/coupons")); } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت کوپن‌ها"); } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function create() {
    const tenant = Number(tenantId); const amount = Number(value);
    if (!Number.isInteger(tenant) || tenant <= 0 || !code.trim() || !Number.isFinite(amount) || amount < 0) { setError("Tenant، کد و مقدار کوپن را معتبر وارد کنید."); return; }
    setBusy(-1); setError("");
    try { await api.post("/coupons", { tenant_id: tenant, code: code.trim(), kind, value: amount }); setCode(""); setValue(""); await load(); } catch (e) { setError(e instanceof Error ? e.message : "ایجاد کوپن ناموفق بود"); } finally { setBusy(null); }
  }

  async function toggle(item: Coupon) {
    setBusy(item.id); setError("");
    try { await api.post(`/coupons/${item.id}`, { active: !item.active }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "تغییر وضعیت ناموفق بود"); } finally { setBusy(null); }
  }

  return <section className="page" dir="rtl">
    <div className="page-header"><div><h2>کوپن‌ها</h2><p>ساخت و مدیریت تخفیف‌های فروشگاه</p></div><button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button></div>
    {error && <div className="card error">{error}</div>}
    <div className="card"><h3>کوپن جدید</h3><div className="form-grid"><label>Tenant ID<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} /></label><label>کد<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="WELCOME" /></label><label>نوع<select value={kind} onChange={(e) => setKind(e.target.value)}><option value="fixed">مبلغ ثابت</option><option value="percentage">درصدی</option></select></label><label>مقدار<input value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal" /></label><button className="button" onClick={() => void create()} disabled={busy !== null}>{busy === -1 ? "در حال ثبت…" : "ایجاد کوپن"}</button></div></div>
    <div className="card"><h3>فهرست کوپن‌ها</h3>{loading ? <p>در حال بارگذاری…</p> : items.length === 0 ? <p>کوپنی ثبت نشده است.</p> : <table className="table"><thead><tr><th>کد</th><th>Tenant</th><th>نوع</th><th>مقدار</th><th>استفاده</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.code}</td><td>{item.tenant_id}</td><td>{item.kind === "percentage" ? "درصدی" : "ثابت"}</td><td>{item.value}</td><td>{item.used_count}{item.usage_limit ? ` / ${item.usage_limit}` : ""}</td><td><span className="badge">{item.active ? "فعال" : "غیرفعال"}</span></td><td><button className="button" disabled={busy === item.id} onClick={() => void toggle(item)}>{item.active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button></td></tr>)}</tbody></table>}</div>
  </section>;
}
