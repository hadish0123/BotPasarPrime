import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type User = {
  id: number;
  telegram_id?: number | null;
  username?: string | null;
  first_name?: string | null;
  role: string;
  status: string;
  created_at: string;
};

export default function Users() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const [rows, setRows] = useState<User[]>([]);
  const [selected, setSelected] = useState<User | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    if (!tenantId) {
      setError("ابتدا یک Tenant را از بخش Tenantها انتخاب کنید.");
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setRows(await api.get<User[]>(`/users?tenant_id=${tenantId}&limit=100`));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای دریافت کاربران");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [tenantId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((user) => [user.id, user.telegram_id, user.username, user.first_name, user.role, user.status].some((value) => String(value ?? "").toLowerCase().includes(q)));
  }, [rows, query]);

  return (
    <section className="page">
      <div className="page-heading">
        <div><h2>کاربران</h2><p>مدیریت کاربران Tenant انتخاب‌شده با جداسازی کامل داده‌ها.</p></div>
        <button onClick={() => void load()} disabled={loading}>بروزرسانی</button>
      </div>
      {error && <div className="alert error">{error}</div>}
      <div className="card" style={{ marginBottom: 18 }}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جستجو با شناسه، username، نام یا نقش..." aria-label="جستجوی کاربران" />
      </div>
      <div className="card table-wrap">
        {loading ? <div className="state">در حال دریافت کاربران...</div> : !filtered.length ? <div className="state">کاربری برای نمایش وجود ندارد.</div> : (
          <table className="table"><thead><tr><th>#</th><th>Telegram</th><th>نام</th><th>نقش</th><th>وضعیت</th><th>تاریخ</th><th>عملیات</th></tr></thead>
            <tbody>{filtered.map((user) => <tr key={user.id}><td>#{user.id}</td><td>{user.username ? `@${user.username}` : user.telegram_id ?? "—"}</td><td>{user.first_name || "—"}</td><td><span className="badge">{user.role}</span></td><td><span className="badge">{user.status}</span></td><td>{new Date(user.created_at).toLocaleString("fa-IR")}</td><td><button onClick={() => setSelected(user)}>مشاهده</button></td></tr>)}</tbody>
          </table>
        )}
      </div>
      {selected && <div className="card" style={{ marginTop: 18 }}><div className="page-heading"><div><h3>جزئیات کاربر #{selected.id}</h3><p>{selected.first_name || "بدون نام"} {selected.username ? `(@${selected.username})` : ""}</p></div><button onClick={() => setSelected(null)}>بستن</button></div><dl><dt>Telegram ID</dt><dd>{selected.telegram_id ?? "—"}</dd><dt>نقش</dt><dd>{selected.role}</dd><dt>وضعیت</dt><dd>{selected.status}</dd><dt>عضویت</dt><dd>{new Date(selected.created_at).toLocaleString("fa-IR")}</dd></dl></div>}
    </section>
  );
}
