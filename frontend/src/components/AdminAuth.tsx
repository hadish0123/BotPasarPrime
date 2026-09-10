import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, apiClient } from "../api";

type Session = { role?: string | null; tenant_id?: number | null; is_platform_owner?: boolean; permissions?: string[] };
type TelegramWebApp = { initData: string; ready: () => void; expand: () => void };
declare global { interface Window { Telegram?: { WebApp?: TelegramWebApp } } }

function hasAdminAccess(session: Session) { return Boolean(session.is_platform_owner || (session.tenant_id && (session.permissions || []).some((permission) => permission.startsWith("dashboard.")))); }

export default function AdminAuth({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true); const [session, setSession] = useState<Session | null>(null); const [error, setError] = useState("");
  useEffect(() => { let active = true; const authenticate = async () => { try {
    const existing = localStorage.getItem("token");
    if (existing) { const current = await api.get<Session>("/auth/me"); if (active && hasAdminAccess(current)) { setSession(current); return; } localStorage.removeItem("token"); }
    const initData = window.Telegram?.WebApp?.initData || ""; if (!initData) throw new Error("پنل مدیریت باید از داخل Telegram Web App باز شود.");
    window.Telegram?.WebApp?.ready(); window.Telegram?.WebApp?.expand();
    const tenantId = Number(new URLSearchParams(window.location.search).get("tenant_id") || 0); const path = tenantId > 0 ? `/auth/telegram/${tenantId}` : "/auth/telegram";
    const response = await apiClient.post<{ access_token: string }>(path, undefined, { headers: { "X-Telegram-Init-Data": initData } }); localStorage.setItem("token", response.data.access_token);
    const current = await api.get<Session>("/auth/me"); if (!hasAdminAccess(current)) { localStorage.removeItem("token"); throw new Error("این حساب دسترسی مدیریت ندارد."); } if (active) setSession(current);
  } catch (err) { if (active) setError(err instanceof Error ? err.message : "احراز هویت مدیریت انجام نشد."); } finally { if (active) setLoading(false); } }; void authenticate(); return () => { active = false; }; }, []);
  if (loading) return <div className="state" dir="rtl">در حال احراز هویت امن…</div>;
  if (error || !session) return <main className="page" dir="rtl"><section className="card" style={{ maxWidth: 560, margin: "80px auto", textAlign: "center" }}><h2>🔐 ورود امن به پنل مدیریت</h2><p>{error || "برای ادامه، حساب مدیریتی خود را احراز هویت کنید."}</p><button onClick={() => window.location.reload()}>تلاش مجدد</button></section></main>;
  return <>{children}</>;
}
