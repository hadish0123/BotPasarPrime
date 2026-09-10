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

type Permission = {
  id: number;
  key: string;
  description?: string | null;
};

export default function Admins() {
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [telegramId, setTelegramId] = useState("");
  const [role, setRole] = useState("Admin");
  const [tenantId, setTenantId] = useState("");
  const [saving, setSaving] = useState(false);
  const [roleName, setRoleName] = useState("");
  const [roleDescription, setRoleDescription] = useState("");
  const [roleTenantId, setRoleTenantId] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [creatingRole, setCreatingRole] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [adminRows, roleRows, permissionRows] = await Promise.all([
        api.get<Admin[]>("/admins"),
        api.get<Role[]>("/admins/roles"),
        api.get<Permission[]>("/admins/permissions"),
      ]);
      setAdmins(adminRows);
      setRoles(roleRows);
      setPermissions(permissionRows);
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

  async function createRole() {
    const name = roleName.trim();
    if (name.length < 2) {
      setError("نام نقش باید حداقل ۲ کاراکتر باشد.");
      return;
    }
    if (!roleTenantId && !confirm("این نقش سراسری است و فقط Owner می‌تواند آن را بسازد. ادامه می‌دهید؟")) return;
    setCreatingRole(true);
    setError("");
    try {
      await api.post("/admins/roles", {
        name,
        description: roleDescription.trim() || null,
        tenant_id: roleTenantId ? Number(roleTenantId) : null,
        permissions: selectedPermissions,
      });
      setRoleName("");
      setRoleDescription("");
      setRoleTenantId("");
      setSelectedPermissions([]);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "ساخت نقش انجام نشد");
    } finally {
      setCreatingRole(false);
    }
  }

  function togglePermission(key: string) {
    setSelectedPermissions((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key]);
  }

  return (
    <section className="page" dir="rtl">
      <div className="page-header">
        <div><h2>مدیران و RBAC</h2><p>مدیریت نقش‌ها، دسترسی‌ها و مدیران با محدوده tenant</p></div>
        <button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button>
      </div>
      {error && <div className="card error">{error}</div>}

      <div className="card">
        <h3>افزودن مدیر</h3>
        <div className="form-grid">
          <label>Telegram ID<input value={telegramId} onChange={(e) => setTelegramId(e.target.value)} placeholder="مثلاً 123456789" /></label>
          <label>نقش<select value={role} onChange={(e) => setRole(e.target.value)}>{roles.map((item) => <option key={item.id} value={item.name}>{item.name}{item.tenant_id ? ` — tenant #${item.tenant_id}` : ""}</option>)}</select></label>
          <label>Tenant ID (اختیاری)<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="برای مدیر tenant" /></label>
          <button className="button" onClick={() => void createAdmin()} disabled={saving}>{saving ? "در حال ثبت…" : "ثبت مدیر"}</button>
        </div>
      </div>

      <div className="card">
        <h3>ساخت نقش سفارشی</h3>
        <div className="form-grid">
          <label>نام نقش<input value={roleName} onChange={(e) => setRoleName(e.target.value)} placeholder="مثلاً Sales Iran" /></label>
          <label>توضیح<input value={roleDescription} onChange={(e) => setRoleDescription(e.target.value)} placeholder="شرح دسترسی نقش" /></label>
          <label>Tenant ID<input value={roleTenantId} onChange={(e) => setRoleTenantId(e.target.value)} placeholder="خالی = نقش سراسری" /></label>
        </div>
        <div className="form-grid" style={{ marginTop: 12 }}>
          {permissions.map((permission) => (
            <label key={permission.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={selectedPermissions.includes(permission.key)} onChange={() => togglePermission(permission.key)} />
              <span>{permission.key}{permission.description ? ` — ${permission.description}` : ""}</span>
            </label>
          ))}
        </div>
        <button className="button" onClick={() => void createRole()} disabled={creatingRole || permissions.length === 0}>
          {creatingRole ? "در حال ساخت…" : `ساخت نقش (${selectedPermissions.length} دسترسی)`}
        </button>
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
