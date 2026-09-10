import { useEffect, useState } from "react";
import { api } from "../api";

type AuditRow = { id: number; actor_type: string; actor_id?: string | null; tenant_id?: number | null; action: string; target_type?: string | null; target_id?: string | null; timestamp: string; metadata?: Record<string, unknown> };

export default function Audit() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
      setRows(await api.get<AuditRow[]>(`/audit${query}`));
    } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت Audit Log"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  return <section className="page" dir="rtl">
    <div className="page-header"><div><h2>Audit Log</h2><p>ردیابی امن عملیات حساس و تغییرات مدیریتی</p></div><button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button></div>
    <div className="card"><div className="form-grid"><label>Tenant ID (اختیاری برای Owner)<input value={tenantId} onChange={e => setTenantId(e.target.value)} placeholder="همه tenantها" /></label><button className="button" onClick={() => void load()} disabled={loading}>اعمال فیلتر</button></div></div>
    {error && <div className="card error">{error}</div>}
    <div className="card">{loading ? <p>در حال بارگذاری…</p> : rows.length === 0 ? <p>رویداد ثبت‌شده‌ای وجود ندارد.</p> : <div className="table-wrap"><table className="table"><thead><tr><th>زمان</th><th>Tenant</th><th>عملیات</th><th>بازیگر</th><th>هدف</th><th>جزئیات</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{new Date(row.timestamp).toLocaleString("fa-IR")}</td><td>{row.tenant_id ?? "Platform"}</td><td><span className="badge">{row.action}</span></td><td>{row.actor_type}{row.actor_id ? ` #${row.actor_id}` : ""}</td><td>{row.target_type ?? "—"}{row.target_id ? ` #${row.target_id}` : ""}</td><td><code>{JSON.stringify(row.metadata ?? {})}</code></td></tr>)}</tbody></table></div>}</div>
  </section>;
}
