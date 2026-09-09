import { useEffect, useState } from "react";
import { api } from "../api";

type Wallet = { tenant_id: number; user_id: number; balance: string };
type Tx = { id: number; amount: string; direction: string; reason: string; created_at: string };

export default function Wallet() {
  const tenantId = Number(localStorage.getItem("tenant_id") || 0);
  const currentUserId = Number(localStorage.getItem("user_id") || 0);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Tx[]>([]);
  const [userId, setUserId] = useState(currentUserId ? String(currentUserId) : "");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("شارژ کیف پول");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!tenantId) { setError("ابتدا Tenant را انتخاب کنید."); return; }
    setError("");
    try {
      const target = userId ? `&user_id=${encodeURIComponent(userId)}` : "";
      const [w, tx] = await Promise.all([
        api.get<Wallet>(`/wallet?tenant_id=${tenantId}${target}`),
        api.get<Tx[]>(`/wallet/transactions?tenant_id=${tenantId}${target}`),
      ]);
      setWallet(w); setTransactions(tx);
    } catch (e) { setError(e instanceof Error ? e.message : "خطا در دریافت کیف پول"); }
  }
  useEffect(() => { void load(); }, [tenantId]);

  async function credit() {
    const parsed = Number(amount);
    const target = Number(userId);
    if (!tenantId || !target || !Number.isFinite(parsed) || parsed <= 0) { setError("مبلغ و کاربر معتبر وارد کنید."); return; }
    setBusy(true); setError("");
    try {
      await api.post(`/wallet/transactions?tenant_id=${tenantId}&user_id=${target}&amount=${encodeURIComponent(amount)}&direction=credit&reason=${encodeURIComponent(reason)}&idempotency_key=admin-${Date.now()}-${target}`);
      setAmount(""); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "شارژ کیف پول ناموفق بود"); }
    finally { setBusy(false); }
  }

  return <section className="page" dir="rtl">
    <div className="page-heading"><div><h2>کیف پول</h2><p>موجودی و دفتر immutable تراکنش‌های Tenant</p></div><button onClick={() => void load()}>به‌روزرسانی</button></div>
    {error && <div className="alert error">{error}</div>}
    <div className="card"><label>شناسه کاربر <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="User ID" /></label> <label>مبلغ <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="مثلاً 100000" /></label> <label>علت <input value={reason} onChange={(e) => setReason(e.target.value)} /></label> <button disabled={busy} onClick={() => void credit()}>افزایش موجودی</button></div>
    {wallet && <div className="card"><h3>موجودی</h3><strong>{new Intl.NumberFormat("fa-IR").format(Number(wallet.balance))} تومان</strong></div>}
    <div className="card table-wrap"><h3>تراکنش‌ها</h3>{!transactions.length ? <div className="state">تراکنشی وجود ندارد.</div> : <table className="table"><thead><tr><th>#</th><th>مبلغ</th><th>نوع</th><th>علت</th><th>تاریخ</th></tr></thead><tbody>{transactions.map((tx) => <tr key={tx.id}><td>#{tx.id}</td><td>{new Intl.NumberFormat("fa-IR").format(Number(tx.amount))} تومان</td><td>{tx.direction === "credit" ? "بستانکار" : "بدهکار"}</td><td>{tx.reason}</td><td>{new Date(tx.created_at).toLocaleString("fa-IR")}</td></tr>)}</tbody></table>}</div>
  </section>;
}
