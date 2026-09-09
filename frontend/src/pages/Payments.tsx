import { useEffect, useState } from "react";
import { api } from "../api";

type Payment = { id: number; order_id: number; amount: string; provider: string; status: string; reference?: string | null; created_at: string };

export default function Payments() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const [rows, setRows] = useState<Payment[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState<number | null>(null);
  const load = async () => { if (!tenantId) { setError("ابتدا یک Tenant را انتخاب کنید."); return; } try { setRows(await api.get<Payment[]>(`/payments?tenant_id=${tenantId}`)); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "خطای دریافت پرداخت‌ها"); } };
  useEffect(() => { void load(); }, [tenantId]);
  const verify = async (id: number, approve: boolean) => { setBusy(id); try { await api.post(`/payments/${id}/verify?tenant_id=${tenantId}&approve=${approve}`); await load(); } catch (err) { setError(err instanceof Error ? err.message : "عملیات پرداخت ناموفق بود"); } finally { setBusy(null); } };
  return <section className="page"><div className="page-heading"><div><h2>پرداخت‌ها</h2><p>صف بررسی پرداخت‌های Tenant انتخاب‌شده.</p></div><button onClick={() => void load()}>بروزرسانی</button></div>{error && <div className="alert error">{error}</div>}<div className="card table-wrap">{!rows.length ? <div className="state">پرداختی برای نمایش وجود ندارد.</div> : <table className="table"><thead><tr><th>#</th><th>سفارش</th><th>مبلغ</th><th>روش</th><th>وضعیت</th><th>رسید</th><th>عملیات</th></tr></thead><tbody>{rows.map((p) => <tr key={p.id}><td>#{p.id}</td><td>#{p.order_id}</td><td>{new Intl.NumberFormat("fa-IR").format(Number(p.amount))} تومان</td><td>{p.provider}</td><td><span className="badge">{p.status}</span></td><td>{p.reference || "—"}</td><td>{["submitted", "verifying"].includes(p.status) ? <><button disabled={busy === p.id} onClick={() => void verify(p.id, true)}>تأیید</button>{" "}<button disabled={busy === p.id} onClick={() => void verify(p.id, false)}>رد</button></> : "—"}</td></tr>)}</tbody></table>}</div></section>;
}
