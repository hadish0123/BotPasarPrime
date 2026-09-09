import { useEffect, useState } from 'react';
import { api } from '../api';

type Approval = { id: number; tenant_id: number; path: string; status: string; note?: string | null };

export default function Approvals() {
  const [items, setItems] = useState<Approval[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number | null>(null);

  const load = async () => {
    try { setItems(await api.get<Approval[]>('/approvals?status=pending_review')); setError(''); } catch (err) { setError(err instanceof Error ? err.message : 'خطای دریافت درخواست‌ها'); }
  };

  useEffect(() => { void load(); }, []);

  const act = async (id: number, approved: boolean) => {
    setBusy(id);
    try { await api.post(`/approvals/${id}`, { approved, note: approved ? 'Approved from admin panel' : 'Rejected from admin panel' }); await load(); } catch (err) { setError(err instanceof Error ? err.message : 'عملیات ناموفق بود'); } finally { setBusy(null); }
  };

  return <section className="page"><div className="page-header"><div><h2>Approval Management</h2><p>صف بررسی و فعال‌سازی Tenantها.</p></div><button onClick={() => void load()}>به‌روزرسانی</button></div>{error && <div className="alert error">{error}</div>}<div className="card">{!items.length ? <div className="empty-state">درخواست در انتظار بررسی وجود ندارد.</div> : <table className="table"><thead><tr><th>شناسه</th><th>Tenant</th><th>مسیر</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>#{item.id}</td><td>#{item.tenant_id}</td><td>{item.path}</td><td><span className="badge">{item.status}</span></td><td><button disabled={busy === item.id} onClick={() => void act(item.id, true)}>تأیید و فعال‌سازی</button>{' '}<button disabled={busy === item.id} onClick={() => void act(item.id, false)}>رد</button></td></tr>)}</tbody></table>}</div></section>;
}
