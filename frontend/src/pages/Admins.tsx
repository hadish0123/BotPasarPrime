import { useEffect, useState } from "react";
import { api } from "../api";

type Admin = {
  id: number;
  telegram_id: number;
  username?: string | null;
  is_active: boolean;
  roles: { name: string; tenant_id: number | null }[];
};

type Role = {
  id: number;
  tenant_id: number | null;
  name: string;
  description?: string | null;
  is_system: boolean;
};

export default function Admins() {
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [telegramId, setTelegramId] = useState("");
  const [role, setRole] = useState("Admin");
  const [tenantId, setTenantId] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [adminRows, roleRows] = await Promise.all([
        api.get<Admin[]>("/admins"),
        api.get<Role[]>("/admins/roles"),
      ]);
      setAdmins(adminRows);
      setRoles(roleRows);
      if (!roleRows.some((item) => item.name === role)) setRole(roleRows[0]?.name || "Admin");
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا در دریافت اطلاعات مدیران");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function createAdmin() {
    const parsedTelegramId = Number(telegramId);
    if (!Number.isInteger(parsedTelegramId) || parsedTelegramId <= 0) {
      setError("شناسه تلگرام معتبر وارد کنید.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.post("/admins", {
        telegram_id: parsedTelegramId,
        role,
        tenant_id: tenantId ? Number(tenantId) : null,
      });
      setTelegramId("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "ثبت مدیر انجام نشد");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page" dir="rtl">
      <div className="page-header">
        <div><h2>مدیران و RBAC</h2><p>مدیریت نقش‌ها و دسترسی‌های مدیران</p></div>
        <button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button>
      </div>
      {error && <div className="card error">{error}</div>}
      <div className="card">
        <h3>افزودن مدیر</h3>
        <div className="form-grid">
          <label>Telegram ID<input value={telegramId} onChange={(e) => setTelegramId(e.target.value)} placeholder="مثلاً 123456789" /></label>
          <label>نقش<select value={role} onChange={(e) => setRole(e.target.value)}>{roles.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select></label>
          <label>Tenant ID (اختیاری)<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="برای نقش tenant-scoped" /></label>
          <button className="button" onClick={() => void createAdmin()} disabled={saving}>{saving ? "در حال ثبت…" : "ثبت مدیر"}</button>
        </div>
      </div>
      <div className="card">
        <h3>مدیران فعال</h3>
        {loading ? <p>در حال بارگذاری…</p> : admins.length === 0 ? <p>مدیری ثبت نشده است.</p> : (
          <table className="table"><thead><tr><th>ID</th><th>Telegram</th><th>نام کاربری</th><th>وضعیت</th><th>نقش‌ها</th></tr></thead>
            <tbody>{admins.map((item) => <tr key={item.id}><td>{item.id}</td><td>{item.telegram_id}</td><td>{item.username || "—"}</td><td><span className="badge">{item.is_active ? "فعال" : "غیرفعال"}</span></td><td>{item.roles.map((r) => `${r.name}${r.tenant_id ? ` #${r.tenant_id}` : ""}`).join("، ") || "—"}</td></tr>)}</tbody>
          </table>
        )}
      </div>
    </section>
  );
}
