import { useEffect, useState } from "react";
import { api } from "../api";

type Dashboard = { sales: string; orders: number; users: number; revenue: string; pending_payments: number; services: { total: number; active: number } };
type Grouped = { by_status: Record<string, number> };

export default function Reports() {
  const [tenantId, setTenantId] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [orders, setOrders] = useState<Grouped | null>(null);
  const [services, setServices] = useState<Grouped | null>(null);
  const [revenue, setRevenue] = useState<{ paid_revenue: string; pending_value: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    if (!tenantId || !Number.isInteger(Number(tenantId)) || Number(tenantId) <= 0) { setError("Tenant ID معتبر وارد کنید."); return; }
    setLoading(true); setError("");
    try {
      const q = `?tenant_id=${encodeURIComponent(tenantId)}`;
      const [d, o, s, r] = await Promise.all([
        api.get<Dashboard>(`/reports/dashboard${q}`), api.get<Grouped>(`/reports/orders${q}`), api.get<Grouped>(`/reports/services${q}`), api.get<{ paid_revenue: string; pending_value: string }>(`/reports/revenue${q}`),
      ]);
      setDashboard(d); setOrders(o); setServices(s); setRevenue(r);
    } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت گزارش‌ها"); }
    finally { setLoading(false); }
  }

  return <section className="page" dir="rtl">
    <div className="page-header"><div><h2>گزارش‌ها</h2><p>فروش، درآمد، سفارش‌ها، کاربران و وضعیت سرویس‌ها</p></div><button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button></div>
    <div className="card"><div className="form-grid"><label>Tenant ID<input value={tenantId} onChange={e => setTenantId(e.target.value)} placeholder="مثلاً 1" /></label><button className="button" onClick={() => void load()} disabled={loading}>دریافت گزارش</button></div></div>
    {error && <div className="card error">{error}</div>}
    {loading ? <div className="card"><p>در حال بارگذاری گزارش‌ها…</p></div> : dashboard && <>
      <div className="stats-grid"><div className="stat-card"><span>فروش</span><strong>{dashboard.sales}</strong></div><div className="stat-card"><span>درآمد پرداخت‌شده</span><strong>{dashboard.revenue}</strong></div><div className="stat-card"><span>سفارش‌ها</span><strong>{dashboard.orders}</strong></div><div className="stat-card"><span>کاربران</span><strong>{dashboard.users}</strong></div><div className="stat-card"><span>پرداخت‌های در انتظار</span><strong>{dashboard.pending_payments}</strong></div><div className="stat-card"><span>سرویس فعال / کل</span><strong>{dashboard.services.active} / {dashboard.services.total}</strong></div></div>
      <div className="card"><h3>درآمد</h3><p>پرداخت‌شده: {revenue?.paid_revenue ?? "—"}</p><p>مبلغ در انتظار: {revenue?.pending_value ?? "—"}</p></div>
      <div className="card"><h3>سفارش‌ها بر اساس وضعیت</h3><p>{orders ? Object.entries(orders.by_status).map(([k,v]) => `${k}: ${v}`).join(" · ") || "بدون داده" : "—"}</p></div>
      <div className="card"><h3>سرویس‌ها بر اساس وضعیت</h3><p>{services ? Object.entries(services.by_status).map(([k,v]) => `${k}: ${v}`).join(" · ") || "بدون داده" : "—"}</p></div>
    </>}
  </section>;
}
