import { FormEvent, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { ArrowLeft, Gift, Headphones, Home, Package, ShoppingBag, ShoppingCart, User, WalletCards } from 'lucide-react';
import { api, apiClient } from '../api';

type Page = 'home' | 'shop' | 'product' | 'checkout' | 'payment' | 'wallet' | 'services' | 'orders' | 'referral' | 'profile' | 'support' | 'notifications';
type Plan = { id: number; name: string; price: string; duration_days: number; quota_gb: number | null; product_name: string; description?: string | null };
type Service = { id: number; status: string; external_id?: string | null; expires_at?: string | null };
type Order = { id: number; status: string; total: string; created_at: string };
type Wallet = { balance: string };
type Brand = { display_name?: string | null; logo_url?: string | null; primary_color?: string | null };
type TelegramWebApp = { initData: string; ready: () => void; expand: () => void };
declare global { interface Window { Telegram?: { WebApp?: TelegramWebApp } } }

const formatPrice = (value: string | number) => `${new Intl.NumberFormat('fa-IR').format(Number(value))} تومان`;

function SectionTitle({ title, onBack }: { title: string; onBack: () => void }) {
  return <div className="mini-section-title"><button className="icon-button" onClick={onBack} aria-label="بازگشت"><ArrowLeft size={20} /></button><h2>{title}</h2><div /></div>;
}

export default function MiniApp() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const tenantId = Number(params.get('tenant_id') || 0);
  const onboardingMode = params.get('mode') === 'onboarding';
  const onboardingPath = params.get('path') === 'personal_panel' ? 'personal_panel' : 'representative';
  const [page, setPage] = useState<Page>('home');
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selected, setSelected] = useState<Plan | null>(null);
  const [brand, setBrand] = useState<Brand>({ display_name: '3XSHOP', primary_color: '#2563eb' });
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [coupon, setCoupon] = useState('');
  const [discount, setDiscount] = useState('0');
  const [orderId, setOrderId] = useState<number | null>(null);
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [reference, setReference] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [onboarding, setOnboarding] = useState({ slug: '', name: '', pasarguard_url: '', pasarguard_api_token: '', pasarguard_username: '', bot_token: '' });
  const initData = window.Telegram?.WebApp?.initData || '';

  const auth = async () => {
    if (!initData) throw new Error('این صفحه باید از داخل Telegram Mini App باز شود.');
    const path = tenantId ? `/auth/telegram/${tenantId}` : '/auth/telegram';
    const response = await apiClient.post<{ access_token: string }>(path, undefined, { headers: { 'X-Telegram-Init-Data': initData } });
    localStorage.setItem('token', response.data.access_token);
  };
  const refreshUserData = async () => {
    if (!tenantId) return;
    const [w, s, o] = await Promise.all([api.get<Wallet>(`/wallet?tenant_id=${tenantId}`), api.get<Service[]>(`/services?tenant_id=${tenantId}`), api.get<Order[]>(`/orders?tenant_id=${tenantId}`)]);
    setWallet(w); setServices(s); setOrders(o);
  };
  const loadTenant = async () => {
    if (!tenantId) return;
    const products = await api.get<Array<{ id: number; name: string; description?: string | null }>>(`/shop/products?tenant_id=${tenantId}`);
    const loaded: Plan[] = [];
    for (const product of products) {
      const productPlans = await api.get<Array<{ id: number; name: string; price: string; duration_days: number; quota_gb: number | null }>>(`/shop/products/${product.id}/plans?tenant_id=${tenantId}`);
      for (const plan of productPlans) loaded.push({ ...plan, product_name: product.name, description: product.description });
    }
    setPlans(loaded);
    try { const result = await api.get<{ branding: Brand }>(`/settings?tenant_id=${tenantId}`); setBrand(result.branding || {}); } catch { /* branding is optional */ }
    await refreshUserData();
  };
  useEffect(() => { window.Telegram?.WebApp?.ready(); window.Telegram?.WebApp?.expand(); void (async () => { try { await auth(); if (!onboardingMode) await loadTenant(); } catch (err) { setError(err instanceof Error ? err.message : 'خطای ورود'); } finally { setLoading(false); } })(); }, []);
  const openProduct = (plan: Plan) => { setSelected(plan); setDiscount('0'); setPage('product'); };
  const applyCoupon = async () => { if (!selected || !coupon) return; try { const result = await api.post<{ discount: string }>(`/coupons/validate?tenant_id=${tenantId}&code=${encodeURIComponent(coupon)}&subtotal=${selected.price}`); setDiscount(result.discount); setNotice('کد تخفیف اعمال شد.'); } catch (err) { setNotice(err instanceof Error ? err.message : 'کد تخفیف نامعتبر است.'); } };
  const createOrder = async () => { if (!selected || !tenantId) return; try { const key = `mini-${Date.now()}-${Math.random().toString(36).slice(2)}`; const result = await api.post<{ id: number; total: string }>(`/orders?tenant_id=${tenantId}`, { plan_id: selected.id, coupon_code: coupon || undefined, idempotency_key: key }, key); setOrderId(result.id); setPage('payment'); await refreshUserData(); } catch (err) { setNotice(err instanceof Error ? err.message : 'ساخت سفارش ناموفق بود.'); } };
  const createPayment = async () => { if (!orderId || !tenantId) return; try { const detail = await api.get<{ total: string }>(`/orders/${orderId}?tenant_id=${tenantId}`); const result = await api.post<{ id: number }>(`/payments?tenant_id=${tenantId}`, { order_id: orderId, amount: detail.total, provider: 'manual', idempotency_key: `pay-${orderId}` }); setPaymentId(result.id); setNotice('پرداخت آماده ثبت رسید است.'); } catch (err) { setNotice(err instanceof Error ? err.message : 'ایجاد پرداخت ناموفق بود.'); } };
  const submitPayment = async (event: FormEvent) => { event.preventDefault(); if (!paymentId || !reference.trim() || !tenantId) return; try { await api.post(`/payments/${paymentId}/submit?tenant_id=${tenantId}&reference=${encodeURIComponent(reference.trim())}`); setNotice('رسید ثبت شد و در انتظار تأیید است.'); await refreshUserData(); } catch (err) { setNotice(err instanceof Error ? err.message : 'ثبت رسید ناموفق بود.'); } };
  const submitOnboarding = async (event: FormEvent) => { event.preventDefault(); try { const key = `onboard-${Date.now()}-${Math.random().toString(36).slice(2)}`; const result = await api.post<{ tenant_id: number; activation_fee_toman: number }>('/onboarding', { ...onboarding, path: onboardingPath, bot_name: 'Sales Bot', idempotency_key: key }, key); setNotice(result.activation_fee_toman ? `درخواست ثبت شد. مبلغ فعال‌سازی: ${formatPrice(result.activation_fee_toman)}` : 'درخواست ثبت شد و برای بررسی Owner ارسال شد.'); } catch (err) { setNotice(err instanceof Error ? err.message : 'ثبت درخواست ناموفق بود.'); } };
  if (loading) return <main className="mini-app"><div className="mini-empty"><strong>در حال اتصال امن…</strong></div></main>;
  if (error) return <main className="mini-app"><div className="mini-empty"><strong>ورود ناموفق بود</strong><p>{error}</p></div></main>;
  if (onboardingMode) return <main className="mini-app" dir="rtl"><section className="mini-hero"><div className="mini-hero-content"><div><p className="mini-eyebrow">ثبت امن</p><h1>راه‌اندازی {onboardingPath === 'personal_panel' ? 'پنل شخصی' : 'نماینده'}</h1><p>اطلاعات حساس فقط از طریق اتصال امن ارسال می‌شود.</p></div></div></section><form className="checkout-card" onSubmit={submitOnboarding}><label>نام برند<input value={onboarding.name} onChange={(e) => setOnboarding({ ...onboarding, name: e.target.value })} required /></label><label>شناسه فروشگاه<input value={onboarding.slug} onChange={(e) => setOnboarding({ ...onboarding, slug: e.target.value })} required /></label><label>آدرس PasarGuard<input type="url" value={onboarding.pasarguard_url} onChange={(e) => setOnboarding({ ...onboarding, pasarguard_url: e.target.value })} required /></label><label>API Token PasarGuard<input type="password" value={onboarding.pasarguard_api_token} onChange={(e) => setOnboarding({ ...onboarding, pasarguard_api_token: e.target.value })} required /></label><label>Username PasarGuard<input value={onboarding.pasarguard_username} onChange={(e) => setOnboarding({ ...onboarding, pasarguard_username: e.target.value })} required /></label><label>Telegram Bot Token<input type="password" value={onboarding.bot_token} onChange={(e) => setOnboarding({ ...onboarding, bot_token: e.target.value })} required /></label><button className="mini-primary-button" type="submit">ثبت درخواست</button>{notice && <p>{notice}</p>}</form></main>;
  const renderHome = () => <><section className="mini-hero"><div className="mini-hero-content"><div><p className="mini-eyebrow">خوش آمدید</p><h1>{brand.display_name || '3XSHOP'}</h1><p>خرید، پرداخت و مدیریت سرویس در یکجا</p></div></div></section><section className="mini-quick-grid"><button onClick={() => setPage('shop')}><ShoppingBag size={22}/><span>فروشگاه</span><small>پلن‌های فعال</small></button><button onClick={() => setPage('wallet')}><WalletCards size={22}/><span>کیف پول</span><small>{wallet ? formatPrice(wallet.balance) : 'در حال دریافت'}</small></button><button onClick={() => setPage('services')}><Package size={22}/><span>سرویس‌ها</span><small>{services.length} سرویس</small></button><button onClick={() => setPage('support')}><Headphones size={22}/><span>پشتیبانی</span><small>ثبت تیکت</small></button></section></>;
  const renderShop = () => <><SectionTitle title="فروشگاه" onBack={() => setPage('home')}/><div className="mini-product-list">{plans.length ? plans.map((plan) => <button className="mini-large-product" key={plan.id} onClick={() => openProduct(plan)}><div className="large-product-icon"><Package size={26}/></div><div className="large-product-body"><div className="product-topline"><strong>{plan.product_name} — {plan.name}</strong><span>{plan.duration_days} روز</span></div><p>{plan.description || 'پلن سرویس'}</p><div className="product-meta"><span>{plan.quota_gb == null ? 'نامحدود' : `${plan.quota_gb} GB`}</span><b>{formatPrice(plan.price)}</b></div></div></button>) : <div className="mini-empty"><strong>محصول فعالی وجود ندارد.</strong></div>}</div></>;
  const renderProduct = () => selected && <><SectionTitle title="جزئیات پلن" onBack={() => setPage('shop')}/><div className="product-detail"><div className="product-detail-icon"><Package size={42}/></div><h1>{selected.product_name} — {selected.name}</h1><p>{selected.description || 'پلن سرویس'}</p><div className="detail-stats"><div><span>حجم</span><strong>{selected.quota_gb == null ? 'نامحدود' : `${selected.quota_gb} GB`}</strong></div><div><span>مدت</span><strong>{selected.duration_days} روز</strong></div></div><div className="price-box"><span>قیمت</span><strong>{formatPrice(selected.price)}</strong></div><button className="mini-primary-button" onClick={() => setPage('checkout')}><ShoppingCart size={20}/> ادامه</button></div></>;
  const renderCheckout = () => selected && <><SectionTitle title="تکمیل سفارش" onBack={() => setPage('product')}/><div className="checkout-card"><div className="checkout-row"><span>قیمت</span><strong>{formatPrice(selected.price)}</strong></div><div className="checkout-row"><span>تخفیف</span><strong>{formatPrice(discount)}</strong></div><label>کد تخفیف<input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="مثلاً VIP20"/></label><button className="mini-secondary-button" onClick={() => void applyCoupon()}>اعمال کد</button><div className="checkout-total"><span>قابل پرداخت</span><strong>{formatPrice(Math.max(0, Number(selected.price) - Number(discount)))}</strong></div><button className="mini-primary-button" onClick={() => void createOrder()}>ثبت سفارش</button></div></>;
  const renderPayment = () => <><SectionTitle title="پرداخت" onBack={() => setPage('checkout')}/><div className="payment-card"><WalletCards size={32}/><h1>پرداخت دستی</h1><p>پس از پرداخت، شناسه رسید را ثبت کنید تا بررسی شود.</p>{!paymentId ? <button className="mini-primary-button" onClick={() => void createPayment()}>ایجاد پرداخت</button> : <form onSubmit={submitPayment}><label>شناسه رسید<input value={reference} onChange={(e) => setReference(e.target.value)} required /></label><button className="mini-primary-button" type="submit">ثبت رسید</button></form>}{notice && <p>{notice}</p>}</div></>;
  const renderWallet = () => <><SectionTitle title="کیف پول" onBack={() => setPage('home')}/><div className="wallet-balance"><span>موجودی</span><strong>{wallet ? formatPrice(wallet.balance) : '—'}</strong></div></>;
  const renderServices = () => <><SectionTitle title="سرویس‌های من" onBack={() => setPage('home')}/><div className="mini-product-list">{services.length ? services.map((s) => <div className="mini-large-product" key={s.id}><Package size={25}/><div><strong>سرویس #{s.id}</strong><p>وضعیت: {s.status}</p><small>انقضا: {s.expires_at || '—'}</small></div></div>) : <div className="mini-empty"><strong>هنوز سرویسی ندارید.</strong></div>}</div></>;
  const renderOrders = () => <><SectionTitle title="سفارش‌ها" onBack={() => setPage('home')}/><div className="mini-product-list">{orders.length ? orders.map((o) => <div className="mini-large-product" key={o.id}><ShoppingCart size={24}/><div><strong>سفارش #{o.id}</strong><p>{o.status}</p><b>{formatPrice(o.total)}</b></div></div>) : <div className="mini-empty"><strong>سفارشی ندارید.</strong></div>}</div></>;
  const renderSimple = (title: string, icon: ReactNode, text: string) => <><SectionTitle title={title} onBack={() => setPage('home')}/><div className="mini-empty">{icon}<strong>{text}</strong></div></>;
  return <main className="mini-app" dir="rtl" style={{ '--mini-primary': brand.primary_color || '#2563eb' } as CSSProperties}>{page === 'home' && renderHome()}{page === 'shop' && renderShop()}{page === 'product' && renderProduct()}{page === 'checkout' && renderCheckout()}{page === 'payment' && renderPayment()}{page === 'wallet' && renderWallet()}{page === 'services' && renderServices()}{page === 'orders' && renderOrders()}{page === 'referral' && renderSimple('دعوت دوستان', <Gift size={36}/>, 'سیستم Referral از Backend مدیریت می‌شود.')}{page === 'support' && renderSimple('پشتیبانی', <Headphones size={36}/>, 'برای ثبت و پیگیری تیکت از Backend استفاده کنید.')}{page === 'notifications' && renderSimple('اعلان‌ها', <Home size={36}/>, 'اعلان‌های حساب شما در این بخش نمایش داده می‌شوند.')}{page === 'profile' && renderSimple('حساب من', <User size={36}/>, 'پروفایل Telegram شما به حساب امن متصل است.')}<nav className="mini-bottom-nav"><button className={page === 'home' ? 'active' : ''} onClick={() => setPage('home')}><Home size={20}/><span>خانه</span></button><button className={page === 'shop' ? 'active' : ''} onClick={() => setPage('shop')}><ShoppingBag size={20}/><span>فروشگاه</span></button><button className={page === 'services' ? 'active' : ''} onClick={() => setPage('services')}><Package size={20}/><span>سرویس‌ها</span></button><button className={page === 'orders' ? 'active' : ''} onClick={() => setPage('orders')}><ShoppingCart size={20}/><span>سفارش‌ها</span></button><button className={page === 'profile' ? 'active' : ''} onClick={() => setPage('profile')}><User size={20}/><span>حساب</span></button></nav></main>;
}
