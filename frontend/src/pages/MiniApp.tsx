import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  Bell,
  ChevronLeft,
  Gift,
  Headphones,
  Home,
  Menu,
  Package,
  ShoppingBag,
  ShoppingCart,
  User,
  WalletCards,
  X,
} from 'lucide-react';

type Page =
  | 'home'
  | 'shop'
  | 'product'
  | 'checkout'
  | 'payment'
  | 'wallet'
  | 'services'
  | 'orders'
  | 'referral'
  | 'profile'
  | 'support'
  | 'notifications'
  | 'admin';

type Brand = {
  name: string;
  logo?: string;
  primary: string;
  secondary: string;
  welcome: string;
};

type Product = {
  id: number;
  title: string;
  description: string;
  price: number;
  duration: string;
  quota: string;
};

const defaultBrand: Brand = {
  name: '3XSHOP',
  primary: '#2563eb',
  secondary: '#0f172a',
  welcome: 'سریع، امن و حرفه‌ای',
};

const products: Product[] = [
  {
    id: 1,
    title: 'پلن 100 گیگ',
    description: 'پلن مناسب مصرف شخصی و استفاده روزمره',
    price: 250000,
    duration: '30 روز',
    quota: '100 GB',
  },
  {
    id: 2,
    title: 'پلن 500 گیگ',
    description: 'پلن پرمصرف برای استفاده طولانی‌تر',
    price: 650000,
    duration: '60 روز',
    quota: '500 GB',
  },
  {
    id: 3,
    title: 'پلن 1 ترابایت',
    description: 'پلن حرفه‌ای برای مصرف بالا',
    price: 1100000,
    duration: '90 روز',
    quota: '1 TB',
  },
];

const formatPrice = (value: number) =>
  new Intl.NumberFormat('fa-IR').format(value) + ' تومان';

function BrandMark({ brand }: { brand: Brand }) {
  return (
    <div className="mini-brand-mark">
      {brand.logo ? (
        <img src={brand.logo} alt={brand.name} />
      ) : (
        <span>{brand.name.slice(0, 1)}</span>
      )}
    </div>
  );
}

function BottomNavigation({
  page,
  setPage,
}: {
  page: Page;
  setPage: (page: Page) => void;
}) {
  const items: Array<[Page, string, typeof Home]> = [
    ['home', 'خانه', Home],
    ['shop', 'فروشگاه', ShoppingBag],
    ['services', 'سرویس‌ها', Package],
    ['orders', 'سفارش‌ها', ShoppingCart],
    ['profile', 'حساب من', User],
  ];

  return (
    <nav className="mini-bottom-nav">
      {items.map(([target, label, Icon]) => (
        <button
          key={target}
          className={page === target ? 'active' : ''}
          onClick={() => setPage(target)}
        >
          <Icon size={20} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function SectionTitle({
  title,
  onBack,
}: {
  title: string;
  onBack: () => void;
}) {
  return (
    <div className="mini-section-title">
      <button className="icon-button" onClick={onBack} aria-label="بازگشت">
        <ArrowLeft size={20} />
      </button>
      <h2>{title}</h2>
      <div />
    </div>
  );
}

export default function MiniApp() {
  const [brand] = useState<Brand>(defaultBrand);
  const [page, setPage] = useState<Page>('home');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const brandStyle = useMemo(
    () =>
      ({
        '--mini-primary': brand.primary,
        '--mini-secondary': brand.secondary,
      }) as React.CSSProperties,
    [brand],
  );

  const openProduct = (product: Product) => {
    setSelectedProduct(product);
    setPage('product');
  };

  const backHome = () => setPage('home');

  const renderHome = () => (
    <>
      <section className="mini-hero">
        <div className="mini-hero-glow" />
        <div className="mini-hero-content">
          <BrandMark brand={brand} />
          <div>
            <p className="mini-eyebrow">خوش آمدید</p>
            <h1>{brand.name}</h1>
            <p>{brand.welcome}</p>
          </div>
        </div>
      </section>

      <section className="mini-quick-grid">
        <button onClick={() => setPage('shop')}>
          <ShoppingBag size={22} />
          <span>فروشگاه</span>
          <small>مشاهده پلن‌ها</small>
        </button>

        <button onClick={() => setPage('wallet')}>
          <WalletCards size={22} />
          <span>کیف پول</span>
          <small>اعتبار حساب</small>
        </button>

        <button onClick={() => setPage('services')}>
          <Package size={22} />
          <span>سرویس‌های من</span>
          <small>مدیریت سرویس</small>
        </button>

        <button onClick={() => setPage('support')}>
          <Headphones size={22} />
          <span>پشتیبانی</span>
          <small>ثبت تیکت</small>
        </button>
      </section>

      <section className="mini-section">
        <div className="mini-section-header">
          <div>
            <span>پیشنهاد ویژه</span>
            <h2>پلن‌های محبوب</h2>
          </div>
          <button onClick={() => setPage('shop')}>همه</button>
        </div>

        <div className="mini-products">
          {products.slice(0, 2).map((product) => (
            <button
              className="mini-product-card"
              key={product.id}
              onClick={() => openProduct(product)}
            >
              <span className="product-icon">
                <Package size={22} />
              </span>
              <div>
                <strong>{product.title}</strong>
                <small>
                  {product.quota} • {product.duration}
                </small>
                <b>{formatPrice(product.price)}</b>
              </div>
              <ChevronLeft size={19} />
            </button>
          ))}
        </div>
      </section>

      <section className="mini-info-card">
        <Gift size={23} />
        <div>
          <strong>دوستانت را دعوت کن</strong>
          <p>با معرفی سرویس به دوستانت، پاداش دریافت کن.</p>
        </div>
        <button onClick={() => setPage('referral')}>مشاهده</button>
      </section>
    </>
  );

  const renderShop = () => (
    <>
      <SectionTitle title="فروشگاه" onBack={backHome} />

      <div className="mini-page-intro">
        <span>🛍️</span>
        <div>
          <h1>انتخاب پلن</h1>
          <p>پلن موردنظر خود را انتخاب کنید.</p>
        </div>
      </div>

      <div className="mini-product-list">
        {products.map((product) => (
          <button
            className="mini-large-product"
            key={product.id}
            onClick={() => openProduct(product)}
          >
            <div className="large-product-icon">
              <Package size={26} />
            </div>

            <div className="large-product-body">
              <div className="product-topline">
                <strong>{product.title}</strong>
                <span>{product.duration}</span>
              </div>

              <p>{product.description}</p>

              <div className="product-meta">
                <span>{product.quota}</span>
                <b>{formatPrice(product.price)}</b>
              </div>
            </div>

            <ChevronLeft size={20} />
          </button>
        ))}
      </div>
    </>
  );

  const renderProduct = () => {
    if (!selectedProduct) {
      setPage('shop');
      return null;
    }

    return (
      <>
        <SectionTitle title="جزئیات محصول" onBack={() => setPage('shop')} />

        <div className="product-detail">
          <div className="product-detail-icon">
            <Package size={42} />
          </div>

          <h1>{selectedProduct.title}</h1>
          <p>{selectedProduct.description}</p>

          <div className="detail-stats">
            <div>
              <span>حجم</span>
              <strong>{selectedProduct.quota}</strong>
            </div>
            <div>
              <span>مدت</span>
              <strong>{selectedProduct.duration}</strong>
            </div>
          </div>

          <div className="price-box">
            <span>قیمت نهایی</span>
            <strong>{formatPrice(selectedProduct.price)}</strong>
          </div>

          <button
            className="mini-primary-button"
            onClick={() => setPage('checkout')}
          >
            <ShoppingCart size={20} />
            ادامه خرید
          </button>
        </div>
      </>
    );
  };

  const renderCheckout = () => {
    if (!selectedProduct) {
      setPage('shop');
      return null;
    }

    return (
      <>
        <SectionTitle title="تکمیل سفارش" onBack={() => setPage('product')} />

        <div className="checkout-card">
          <div className="checkout-product">
            <Package size={25} />
            <div>
              <strong>{selectedProduct.title}</strong>
              <span>
                {selectedProduct.quota} • {selectedProduct.duration}
              </span>
            </div>
          </div>

          <div className="checkout-row">
            <span>قیمت محصول</span>
            <strong>{formatPrice(selectedProduct.price)}</strong>
          </div>

          <div className="checkout-row">
            <span>تخفیف</span>
            <strong>۰ تومان</strong>
          </div>

          <div className="checkout-total">
            <span>مبلغ قابل پرداخت</span>
            <strong>{formatPrice(selectedProduct.price)}</strong>
          </div>

          <button
            className="mini-primary-button"
            onClick={() => setPage('payment')}
          >
            ادامه به پرداخت
          </button>
        </div>
      </>
    );
  };

  const renderPayment = () => (
    <>
      <SectionTitle title="پرداخت" onBack={() => setPage('checkout')} />

      <div className="payment-card">
        <div className="payment-icon">
          <WalletCards size={32} />
        </div>

        <h1>انتخاب روش پرداخت</h1>
        <p>
          روش پرداخت موردنظر را انتخاب کنید. اتصال واقعی در لایه پرداخت
          پلتفرم انجام می‌شود.
        </p>

        <button className="payment-method">
          <WalletCards size={21} />
          <div>
            <strong>کیف پول</strong>
            <span>پرداخت از موجودی حساب</span>
          </div>
          <ChevronLeft size={18} />
        </button>

        <button className="payment-method">
          <ShoppingCart size={21} />
          <div>
            <strong>درگاه پرداخت</strong>
            <span>انتقال به درگاه رسمی</span>
          </div>
          <ChevronLeft size={18} />
        </button>
      </div>
    </>
  );

  const renderWallet = () => (
    <>
      <SectionTitle title="کیف پول" onBack={backHome} />

      <div className="wallet-balance">
        <span>موجودی کیف پول</span>
        <strong>۰ تومان</strong>
        <small>اطلاعات موجودی از Backend دریافت می‌شود.</small>
      </div>

      <div className="mini-empty">
        <WalletCards size={32} />
        <strong>تراکنشی ثبت نشده است</strong>
        <p>تاریخچه تراکنش‌های کیف پول اینجا نمایش داده می‌شود.</p>
      </div>
    </>
  );

  const renderServices = () => (
    <>
      <SectionTitle title="سرویس‌های من" onBack={backHome} />

      <div className="mini-empty">
        <Package size={34} />
        <strong>هنوز سرویسی ندارید</strong>
        <p>پس از خرید، سرویس‌های شما در این قسمت نمایش داده می‌شوند.</p>
        <button className="mini-secondary-button" onClick={() => setPage('shop')}>
          مشاهده فروشگاه
        </button>
      </div>
    </>
  );

  const renderOrders = () => (
    <>
      <SectionTitle title="سفارش‌های من" onBack={backHome} />

      <div className="mini-empty">
        <ShoppingCart size={34} />
        <strong>سفارشی وجود ندارد</strong>
        <p>تاریخچه سفارش‌های شما در این قسمت نمایش داده می‌شود.</p>
      </div>
    </>
  );

  const renderReferral = () => (
    <>
      <SectionTitle title="دعوت دوستان" onBack={backHome} />

      <div className="referral-card">
        <Gift size={38} />
        <h1>دوستانت را دعوت کن</h1>
        <p>
          لینک دعوت اختصاصی شما پس از اتصال سیستم Referral در این بخش قرار
          می‌گیرد.
        </p>

        <div className="referral-code">
          <span>کد دعوت</span>
          <strong>---</strong>
        </div>
      </div>
    </>
  );

  const renderProfile = () => (
    <>
      <SectionTitle title="حساب من" onBack={backHome} />

      <div className="profile-card">
        <div className="profile-avatar">
          <User size={30} />
        </div>
        <div>
          <strong>کاربر</strong>
          <span>اطلاعات حساب از Telegram دریافت می‌شود.</span>
        </div>
      </div>

      <div className="profile-links">
        <button onClick={() => setPage('notifications')}>
          <Bell size={20} />
          اعلان‌ها
          <ChevronLeft size={18} />
        </button>

        <button onClick={() => setPage('support')}>
          <Headphones size={20} />
          پشتیبانی و تیکت
          <ChevronLeft size={18} />
        </button>

        <button onClick={() => setPage('referral')}>
          <Gift size={20} />
          دعوت دوستان
          <ChevronLeft size={18} />
        </button>
      </div>
    </>
  );

  const renderSupport = () => (
    <>
      <SectionTitle title="پشتیبانی" onBack={backHome} />

      <div className="support-card">
        <Headphones size={38} />
        <h1>در کنار شما هستیم</h1>
        <p>
          برای ثبت درخواست پشتیبانی، سیستم تیکت Tenant در Backend استفاده
          خواهد شد.
        </p>

        <button className="mini-primary-button">
          ثبت تیکت جدید
        </button>
      </div>
    </>
  );

  const renderNotifications = () => (
    <>
      <SectionTitle title="اعلان‌ها" onBack={() => setPage('profile')} />

      <div className="mini-empty">
        <Bell size={34} />
        <strong>اعلان جدیدی ندارید</strong>
        <p>اعلان‌های خرید، سرویس و انقضا اینجا نمایش داده می‌شوند.</p>
      </div>
    </>
  );

  const renderAdmin = () => (
    <>
      <SectionTitle title="مدیریت Tenant" onBack={backHome} />

      <div className="admin-grid">
        {[
          ['Dashboard', '📊'],
          ['Users', '👥'],
          ['Orders', '📋'],
          ['Products', '🛍️'],
          ['Payments', '💳'],
          ['Services', '🖥️'],
          ['Reports', '📈'],
          ['Settings', '⚙️'],
        ].map(([title, icon]) => (
          <button key={title} className="admin-tile">
            <span>{icon}</span>
            <strong>{title}</strong>
          </button>
        ))}
      </div>
    </>
  );

  const renderPage = () => {
    switch (page) {
      case 'home':
        return renderHome();
      case 'shop':
        return renderShop();
      case 'product':
        return renderProduct();
      case 'checkout':
        return renderCheckout();
      case 'payment':
        return renderPayment();
      case 'wallet':
        return renderWallet();
      case 'services':
        return renderServices();
      case 'orders':
        return renderOrders();
      case 'referral':
        return renderReferral();
      case 'profile':
        return renderProfile();
      case 'support':
        return renderSupport();
      case 'notifications':
        return renderNotifications();
      case 'admin':
        return renderAdmin();
      default:
        return renderHome();
    }
  };

  return (
    <div className="mini-app" dir="rtl" style={brandStyle}>
      <header className="mini-header">
        <div className="mini-header-brand">
          <BrandMark brand={brand} />
          <strong>{brand.name}</strong>
        </div>

        <div className="mini-header-actions">
          <button
            className="icon-button"
            onClick={() => setPage('notifications')}
            aria-label="اعلان‌ها"
          >
            <Bell size={20} />
          </button>

          <button
            className="icon-button"
            onClick={() => setMenuOpen(true)}
            aria-label="منو"
          >
            <Menu size={20} />
          </button>
        </div>
      </header>

      <main className="mini-content">{renderPage()}</main>

      {page !== 'product' &&
        page !== 'checkout' &&
        page !== 'payment' &&
        page !== 'notifications' &&
        page !== 'admin' && (
          <BottomNavigation page={page} setPage={setPage} />
        )}

      {menuOpen && (
        <div className="mini-drawer-backdrop" onClick={() => setMenuOpen(false)}>
          <aside
            className="mini-drawer"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer-header">
              <div className="mini-header-brand">
                <BrandMark brand={brand} />
                <strong>{brand.name}</strong>
              </div>

              <button
                className="icon-button"
                onClick={() => setMenuOpen(false)}
                aria-label="بستن"
              >
                <X size={20} />
              </button>
            </div>

            <button
              onClick={() => {
                setPage('profile');
                setMenuOpen(false);
              }}
            >
              <User size={20} />
              حساب کاربری
            </button>

            <button
              onClick={() => {
                setPage('wallet');
                setMenuOpen(false);
              }}
            >
              <WalletCards size={20} />
              کیف پول
            </button>

            <button
              onClick={() => {
                setPage('referral');
                setMenuOpen(false);
              }}
            >
              <Gift size={20} />
              دعوت دوستان
            </button>

            <button
              onClick={() => {
                setPage('support');
                setMenuOpen(false);
              }}
            >
              <Headphones size={20} />
              پشتیبانی
            </button>

            <button
              onClick={() => {
                setPage('admin');
                setMenuOpen(false);
              }}
            >
              ⚙️
              پنل مدیریت
            </button>
          </aside>
        </div>
      )}
    </div>
  );
}
