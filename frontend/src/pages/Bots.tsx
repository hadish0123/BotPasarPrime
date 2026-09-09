import { useEffect, useState } from "react";
import { api } from "../api";

type Bot = { id: number; tenant_id: number | null; name: string; masked_token: string; status: string; heartbeat_at?: string | null; error_count: number };

const labels: Record<string, string> = { approved: "تأییدشده", starting: "در حال شروع", running: "در حال اجرا", stopped: "متوقف", failed: "خطا", suspended: "معلق", pending: "در انتظار" };

export default function Bots() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    setLoading(true); setError("");
    try { setBots(await api.get<Bot[]>("/bots")); }
    catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت بات‌ها"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function action(id: number, verb: "start" | "stop" | "suspend") {
    setBusy(id); setError("");
    try { await api.post(`/bots/${id}/${verb}`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "عملیات بات انجام نشد"); }
    finally { setBusy(null); }
  }

  return <section className="page" dir="rtl">
    <div className="page-header"><div><h2>مدیریت بات‌ها</h2><p>وضعیت، سلامت و چرخه عمر بات‌های نمایندگان</p></div><button className="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی</button></div>
    {error && <div className="card error">{error}</div>}
    <div className="card">
      {loading ? <p>در حال بارگذاری…</p> : bots.length === 0 ? <p>هیچ باتی ثبت نشده است.</p> : <table className="table"><thead><tr><th>ID</th><th>نام</th><th>Tenant</th><th>وضعیت</th><th>Heartbeat</th><th>خطا</th><th>عملیات</th></tr></thead><tbody>{bots.map((bot) => <tr key={bot.id}><td>{bot.id}</td><td>{bot.name}</td><td>{bot.tenant_id ?? "مرکزی"}</td><td><span className="badge">{labels[bot.status] || bot.status}</span></td><td>{bot.heartbeat_at ? new Date(bot.heartbeat_at).toLocaleString("fa-IR") : "—"}</td><td>{bot.error_count}</td><td><button className="button" disabled={busy === bot.id || bot.status === "running"} onClick={() => void action(bot.id, "start")}>شروع</button> <button className="button" disabled={busy === bot.id || bot.status === "stopped"} onClick={() => void action(bot.id, "stop")}>توقف</button> <button className="button" disabled={busy === bot.id || bot.status === "suspended"} onClick={() => void action(bot.id, "suspend")}>تعلیق</button></td></tr>)}</tbody></table>}
    </div>
  </section>;
}
