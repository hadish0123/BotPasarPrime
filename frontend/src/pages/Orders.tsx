import { useEffect, useState } from "react";
import { api } from "../api";

type Order = { id: number; user_id: number; status: string; total: string; created_at: string };

export default function Orders() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const [rows, setRows] = useState<Order[]>([]); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = async () => { if (!tenantId) { setError("ابتدا یک Tenant را از بخش Tenantها انتخاب کنید."); setLoading(false); return; } try { setRows(await api.get<Order[]>(`/orders?tenant_id=${tenantId}&limit=100`)); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "خطای دریافت سفارش‌ها"); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, [tenantId]);
  return <section className="page"><div className="page-heading"><div><h2>سفارش‌ها</h2><p>سفارش‌های Tenant انتخاب‌شده.</p></div><button onClick={() => void load()}>بروزرسانی</button></div>{error && <div className="alert error">{error}</div>}<div className="card table-wrap">{loading ? <div className="state">در حال دریافت...</div> : !rows.length ? <div className="state">سفارشی وجود ندارد.</div> : <table className="table"><thead><tr><th>#</th><th>کاربر</th><th>وضعیت</th><th>مبلغ</th><th>تاریخ</th></tr></thead><tbody>{rows.map((o) => <tr key={o.id}><td>#{o.id}</td><td>#{o.user_id}</td><td><span className="badge">{o.status}</span></td><td>{new Intl.NumberFormat("fa-IR").format(Number(o.total))} تومان</td><td>{new Date(o.created_at).toLocaleString("fa-IR")}</td></tr>)}</tbody></table>}</div></section>;
}
