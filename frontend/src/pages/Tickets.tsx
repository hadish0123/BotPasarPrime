import { useEffect, useState } from "react";
import { api } from "../api";

type Ticket = { id: number; user_id: number; subject: string; status: string };
type Detail = Ticket & { messages: { id: number; sender_type: string; body: string; created_at: string }[] };

export default function Tickets() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const [rows, setRows] = useState<Ticket[]>([]); const [detail, setDetail] = useState<Detail | null>(null); const [body, setBody] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function load() { if (!tenantId) { setError("ابتدا Tenant را انتخاب کنید."); return; } try { setRows(await api.get<Ticket[]>(`/support/tickets?tenant_id=${tenantId}`)); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت تیکت‌ها"); } }
  useEffect(() => { void load(); }, [tenantId]);
  async function open(id: number) { try { setDetail(await api.get<Detail>(`/support/tickets/${id}?tenant_id=${tenantId}`)); } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت تیکت"); } }
  async function reply() { if (!detail || !body.trim()) return; setBusy(true); try { await api.post(`/support/tickets/${detail.id}/reply?tenant_id=${tenantId}`, { body: body.trim() }); setBody(""); await open(detail.id); await load(); } catch (e) { setError(e instanceof Error ? e.message : "ارسال پاسخ ناموفق بود"); } finally { setBusy(false); } }
  return <section className="page" dir="rtl"><div className="page-heading"><div><h2>تیکت‌ها</h2><p>پشتیبانی Tenant و پاسخ‌گویی به کاربران</p></div><button onClick={() => void load()}>بروزرسانی</button></div>{error && <div className="alert error">{error}</div>}<div className="card table-wrap">{!rows.length ? <div className="state">تیکتی وجود ندارد.</div> : <table className="table"><thead><tr><th>#</th><th>کاربر</th><th>موضوع</th><th>وضعیت</th><th></th></tr></thead><tbody>{rows.map((t) => <tr key={t.id}><td>#{t.id}</td><td>{t.user_id}</td><td>{t.subject}</td><td><span className="badge">{t.status}</span></td><td><button onClick={() => void open(t.id)}>مشاهده</button></td></tr>)}</tbody></table>}</div>{detail && <div className="card"><div className="page-heading"><h3>تیکت #{detail.id}: {detail.subject}</h3><button onClick={() => setDetail(null)}>بستن</button></div><div>{detail.messages.map((m) => <div key={m.id} className="card"><strong>{m.sender_type === "admin" ? "پشتیبانی" : "کاربر"}</strong><p>{m.body}</p><small>{new Date(m.created_at).toLocaleString("fa-IR")}</small></div>)}</div><textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="پاسخ شما…" rows={4} /><button disabled={busy || !body.trim()} onClick={() => void reply()}>ارسال پاسخ</button></div>}</section>;
}
