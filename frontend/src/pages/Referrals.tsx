import { useEffect, useState } from "react";
import { api } from "../api";

type Ledger = { id: number; tenant_id: number; referral_id: number; order_id: number | null; user_id: number; amount: string; commission_percent: string; ledger_type: string; created_at: string | null };

export default function Referrals() {
  const [tenantId, setTenantId] = useState("");
  const [rows, setRows] = useState<Ledger[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    const tenant = Number(tenantId); if (!Number.isInteger(tenant) || tenant <= 0) { setError("Tenant ID معتبر وارد کنید."); return; }
    setLoading(true); setError("");
    try { setRows(await api.get<Ledger[]>(`/referrals?tenant_id=${tenant}`)); } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت پورسانت‌ها"); } finally { setLoading(false); }
  }
  useEffect(() => { const saved = localStorage.getItem("tenant_id"); if (saved) setTenantId(saved); }, []);
  return <section className="page" dir="rtl"><div className="page-header"><div><h2>ارجاع و پورسانت</h2><p>دفترکل کمیسیون‌ها به تفکیک Tenant و کاربر</p></div></div>{error && <div className="card error">{error}</div>}<div className="card"><div className="form-grid"><label>Tenant ID<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} /></label><button className="button" onClick={() => void load()} disabled={loading}>{loading ? "در حال دریافت…" : "نمایش دفترکل"}</button></div></div><div className="card"><h3>دفترکل</h3>{loading ? <p>در حال بارگذاری…</p> : rows.length === 0 ? <p>رکوردی برای نمایش وجود ندارد.</p> : <table className="table"><thead><tr><th>ID</th><th>کاربر</th><th>سفارش</th><th>مبلغ</th><th>درصد</th><th>نوع</th><th>تاریخ</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.user_id}</td><td>{row.order_id ?? "—"}</td><td>{row.amount}</td><td>{row.commission_percent}%</td><td>{row.ledger_type}</td><td>{row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}</td></tr>)}</tbody></table>}</div></section>;
}
