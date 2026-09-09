import { useEffect, useMemo, useState } from "react";
import { Building2, Eye, RefreshCw, Search } from "lucide-react";
import { api } from "../api";

type Tenant = {
  id: number;
  slug: string;
  name: string;
  status: string;
  created_at: string;
};

const labels: Record<string, string> = {
  active: "فعال",
  approved: "تأیید شده",
  pending_review: "در انتظار بررسی",
  awaiting_payment: "در انتظار پرداخت",
  suspended: "تعلیق شده",
  inactive: "غیرفعال",
};

export default function Tenants() {
  const [rows, setRows] = useState<Tenant[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Tenant[]>("/tenants");
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در دریافت Tenantها");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((x) => `${x.name} ${x.slug} ${x.id}`.toLowerCase().includes(q)) : rows;
  }, [rows, query]);

  return (
    <section className="page">
      <div className="page-heading">
        <div><div className="eyebrow"><Building2 size={16} /> Multi-Tenant</div><h2>مدیریت Tenantها</h2><p>مشاهده Tenantهای مجاز در محدوده دسترسی حساب شما.</p></div>
        <button className="button secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={16} /> بروزرسانی</button>
      </div>
      <div className="toolbar card">
        <Search size={18} /><input aria-label="جستجوی Tenant" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو بر اساس نام، slug یا شناسه..." />
      </div>
      {error && <div className="alert error">{error}</div>}
      <div className="card table-wrap">
        {loading ? <div className="state">در حال دریافت اطلاعات...</div> : filtered.length === 0 ? <div className="state">Tenantی برای نمایش وجود ندارد.</div> : (
          <table className="table"><thead><tr><th>شناسه</th><th>نام</th><th>Slug</th><th>وضعیت</th><th>تاریخ ایجاد</th><th /></tr></thead>
            <tbody>{filtered.map((tenant) => <tr key={tenant.id}><td>#{tenant.id}</td><td>{tenant.name}</td><td dir="ltr">{tenant.slug}</td><td><span className="badge">{labels[tenant.status] ?? tenant.status}</span></td><td>{new Date(tenant.created_at).toLocaleString("fa-IR")}</td><td><button className="icon-button" title="مشاهده"><Eye size={17} /></button></td></tr>)}</tbody>
          </table>
        )}
      </div>
    </section>
  );
}
