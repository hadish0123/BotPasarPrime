import { useEffect, useState } from 'react';
import { api } from '../api';

type Metrics = { tenants: number; users: number; orders: number; pending_payments: number };

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    void api.get<Metrics>('/admin/dashboard').then(setMetrics).catch((err) => setError(err instanceof Error ? err.message : 'خطای دریافت داشبورد'));
  }, []);

  const cards = [
    ['Tenantها', metrics?.tenants ?? '—'],
    ['کاربران', metrics?.users ?? '—'],
    ['سفارش‌ها', metrics?.orders ?? '—'],
    ['پرداخت معلق', metrics?.pending_payments ?? '—'],
  ];

  return <section className="page"><div className="page-header"><div><h2>داشبورد</h2><p>نمای زنده عملیات فروش و سرویس.</p></div></div>{error && <div className="alert error">{error}</div>}<div className="grid">{cards.map(([title, value]) => <div className="card" key={title}><h3>{title}</h3><div style={{ fontSize: 28 }}>{value}</div></div>)}</div><div className="card" style={{ marginTop: 18 }}><h3>مرکز عملیات</h3><p>Tenant، فروش، پرداخت، سرویس، ربات، امنیت و Audit از API واقعی تغذیه می‌شوند.</p></div></section>;
}
