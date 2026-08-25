"use client";

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Search, CheckCircle2, Copy, Zap, Shield,
  Wallet, Tag, ArrowRight, X, AlertCircle, RefreshCw, Sparkles,
  Sun, Moon, Check, PackageCheck, PackageX, LayoutGrid,
  List, Bolt, HeartHandshake, QrCode, Globe, Mail, FileText,
  UploadCloud, ImageIcon, Camera, Trash2, ThumbsUp, Star, MessageSquare,
  Flame, Bot, Film, Palette, Briefcase, ShieldCheck, Code2, Rocket,
  ChevronDown, ChevronUp, Info, HelpCircle, CreditCard, AlertTriangle
} from 'lucide-react';
import { ProductIcon } from '@/components/ProductIcon';

interface Product {
  id: string;
  raw_id: number;
  name: string;
  description: string;
  price: number;
  price_npr?: number;
  stock: number;
  image?: string;
  type: string;
  source?: string;
  category_id?: number;
  is_instant?: boolean;
  is_featured?: boolean;
  is_hot?: boolean;
  is_bestseller?: boolean;
  badge_text?: string;
  auto_delivery?: boolean;
  delivery_type?: string;
  account_type?: string;
  rating?: number;
  reviews_count?: number;
}

interface UserProfile {
  id: number;
  username: string;
  email?: string;
  balance: number;
}

interface PromoDiscount {
  code: string;
  discount_type: string;
  discount_value: number;
  discount_amount: number;
  final_price: number;
}

const AUTO_CATEGORIES = [
  { id: 'ai', label: 'AI & ChatBots', purchases: '1,420+ Purchases', keywords: ['chatgpt', 'gpt', 'claude', 'gemini', 'perplexity', 'midjourney', 'cursor', 'copilot', 'openai', 'anthropic', 'deepseek'] },
  { id: 'streaming', label: 'Streaming', purchases: '890+ Purchases', keywords: ['netflix', 'spotify', 'youtube', 'prime', 'disney', 'hulu', 'hbo', 'crunchyroll', 'apple music', 'tidal'] },
  { id: 'creative', label: 'Creative Tools', purchases: '640+ Purchases', keywords: ['canva', 'adobe', 'figma', 'envato', 'freepik', 'capcut', 'elementor', 'shutterstock'] },
  { id: 'productivity', label: 'Productivity', purchases: '520+ Purchases', keywords: ['notion', 'office', 'windows', 'grammarly', 'quillbot', 'linkedin', 'github', 'zoom', 'slack'] },
  { id: 'vpn', label: 'VPN & Security', purchases: '380+ Purchases', keywords: ['vpn', 'nordvpn', 'expressvpn', 'surfshark', 'kaspersky', 'malwarebytes', 'ipvanish', 'proton'] },
  { id: 'dev', label: 'Developer APIs', purchases: '460+ Purchases', keywords: ['api', 'token', 'credits', 'key', 'aws', 'digitalocean', 'vps', 'jetbrains', 'replit', 'claude code'] },
  { id: 'email', label: 'Email & Storage', purchases: '290+ Purchases', keywords: ['gmail', 'google drive', 'onedrive', 'icloud', 'protonmail', 'storage', 'edu email'] },
  { id: 'other', label: 'Other Software', purchases: '210+ Purchases', keywords: [] },
];

function getCategoryIcon(catId: string, isSelected: boolean = false) {
  const cls = `w-4 h-4 shrink-0 transition-colors ${isSelected ? 'text-white' : 'text-red-400'}`;
  switch (catId) {
    case 'featured': return <Star className={cls} />;
    case 'all': return <Flame className={cls} />;
    case 'ai': return <Bot className={cls} />;
    case 'streaming': return <Film className={cls} />;
    case 'creative': return <Palette className={cls} />;
    case 'productivity': return <Briefcase className={cls} />;
    case 'vpn': return <ShieldCheck className={cls} />;
    case 'dev': return <Code2 className={cls} />;
    case 'email': return <Mail className={cls} />;
    default: return <Sparkles className={cls} />;
  }
}

function getAutoCategory(productName: string): string {
  const lower = productName.toLowerCase();
  for (const cat of AUTO_CATEGORIES) {
    if (cat.id === 'other') continue;
    if (cat.keywords.some(k => lower.includes(k))) return cat.id;
  }
  return 'other';
}

function getProductBadges(p: Product) {
  // 1. Delivery Mode
  const isInstant = p.auto_delivery !== false && p.delivery_type !== 'manual';
  const deliveryBadge = isInstant ? {
    label: "⚡ Instant Delivery",
    cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    icon: <Zap className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
  } : {
    label: "⏱️ Manual Dispatch",
    cls: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    icon: <FileText className="w-2.5 h-2.5 text-amber-400 shrink-0" />
  };

  // 2. Account / Key Type
  const lower = (p.name + " " + (p.description || "")).toLowerCase();
  let accType = p.account_type || "";
  let accLabel = "🔑 Pre-Activated";
  let accCls = "bg-purple-500/15 text-purple-300 border-purple-500/30";

  if (accType === "existing_account" || lower.includes("existing") || lower.includes("upgrade") || lower.includes("own email") || lower.includes("own account") || lower.includes("on your email") || lower.includes("invitation")) {
    accLabel = "👤 On Your Email";
    accCls = "bg-cyan-500/15 text-cyan-300 border-cyan-500/30";
  } else if (accType === "key" || lower.includes("key") || lower.includes("license") || lower.includes("token") || lower.includes("code") || lower.includes("serial")) {
    accLabel = "🛡️ License Key";
    accCls = "bg-indigo-500/15 text-indigo-300 border-indigo-500/30";
  } else if (accType === "invite" || lower.includes("invite") || lower.includes("team invite") || lower.includes("workspace")) {
    accLabel = "📩 Direct Invite";
    accCls = "bg-blue-500/15 text-blue-300 border-blue-500/30";
  } else {
    accLabel = "🔑 Pre-Activated";
    accCls = "bg-purple-500/15 text-purple-300 border-purple-500/30";
  }

  return { deliveryBadge, accBadge: { label: accLabel, cls: accCls } };
}


export default function NepalStorePage() {
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('featured');
  const [stockFilter, setStockFilter] = useState<'all' | 'in_stock' | 'out_of_stock'>('all');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [publicSettings, setPublicSettings] = useState<any>(null);
  const [isDisclaimerExpanded, setIsDisclaimerExpanded] = useState(false);
  const [isPricingInfoExpanded, setIsPricingInfoExpanded] = useState(false);
  const [isAboutExpanded, setIsAboutExpanded] = useState(false);

  // Modal states
  const [activeModalProduct, setActiveModalProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [customerEmail, setCustomerEmail] = useState('');
  const [proofImage, setProofImage] = useState<string | null>(null);
  const [proofFileName, setProofFileName] = useState<string>('');
  const [promoCodeInput, setPromoCodeInput] = useState('');
  const [appliedPromo, setAppliedPromo] = useState<PromoDiscount | null>(null);
  const [promoError, setPromoError] = useState('');
  const [isValidatingPromo, setIsValidatingPromo] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'nepal_qr' | 'balance'>('nepal_qr');
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [orderError, setOrderError] = useState('');
  const [nepalQrData, setNepalQrData] = useState<any>(null);
  const [nepalTxId, setNepalTxId] = useState('');
  const [deliveredContent, setDeliveredContent] = useState<string | null>(null);
  const [deliveredEmail, setDeliveredEmail] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Lock region to Nepal for this route
    localStorage.setItem('region', 'nepal');

    // Theme
    const savedTheme = (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
    if (savedTheme === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
    setTheme(savedTheme);

    fetchCatalog();
    fetchUser();
    fetchNepalQrDetails();
    fetchPublicSettings();
  }, []);

  const fetchPublicSettings = async () => {
    try {
      const res = await api.get('/settings/public');
      if (res.data) setPublicSettings(res.data);
    } catch { /* empty */ }
  };

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
    if (next === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
  };

  // Strictly NPR price formatter (Rate 1 USD = 300 NPR)
  const formatNpr = (usd: number = 0) => {
    const npr = Math.round(usd * 300);
    return `NPR ${npr.toLocaleString()}`;
  };

  const fetchCatalog = async () => {
    setLoading(true);
    try {
      const res = await api.get('/catalog/products');
      setProducts(res.data || []);
    } catch { /* empty */ } finally { setLoading(false); }
  };

  const fetchUser = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const res = await api.get('/user/me');
      if (res.data) {
        setUser(res.data);
        if (res.data.email) setCustomerEmail(res.data.email);
      }
    } catch { /* ignore */ }
  };

  const fetchNepalQrDetails = async () => {
    try {
      const res = await api.get('/payments/nepal-qr');
      setNepalQrData(res.data);
    } catch { /* empty */ }
  };

  const isProductFeatured = (p: Product) => {
    return Boolean(p.is_featured || p.is_hot || p.is_bestseller || (p.badge_text && p.badge_text.trim().length > 0));
  };

  const featuredCount = useMemo(() => {
    const count = products.filter(isProductFeatured).length;
    return count > 0 ? count : Math.min(products.length, 24);
  }, [products]);

  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      const matchSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) || (p.description && p.description.toLowerCase().includes(searchTerm.toLowerCase()));
      
      let matchCat = true;
      if (selectedCategory === 'featured') {
        const explicitFeatured = products.filter(isProductFeatured);
        if (explicitFeatured.length > 0) {
          matchCat = isProductFeatured(p);
        } else {
          matchCat = true;
        }
      } else if (selectedCategory === 'all') {
        matchCat = true;
      } else {
        matchCat = getAutoCategory(p.name) === selectedCategory;
      }

      const matchStock =
        stockFilter === 'all' ? true :
        stockFilter === 'in_stock' ? p.stock > 0 :
        p.stock === 0;
      return matchSearch && matchCat && matchStock;
    });
  }, [products, searchTerm, selectedCategory, stockFilter]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: products.length };
    for (const p of products) {
      const cat = getAutoCategory(p.name);
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [products]);

  const handleOpenBuyModal = (p: Product) => {
    setActiveModalProduct(p);
    setQuantity(1);
    setPromoCodeInput('');
    setAppliedPromo(null);
    setPromoError('');
    setOrderError('');
    setProofImage(null);
    setProofFileName('');
    setPaymentMethod('nepal_qr');
    if (user?.email && !customerEmail) {
      setCustomerEmail(user.email);
    }
  };

  const handleProofImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setOrderError('Payment screenshot size must be under 5MB.');
      return;
    }
    setProofFileName(file.name);
    const reader = new FileReader();
    reader.onloadend = () => {
      setProofImage(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const getSubtotalUsd = () => (activeModalProduct?.price ?? 0) * quantity;
  const getFinalTotalUsd = () => {
    const sub = getSubtotalUsd();
    return appliedPromo ? Math.max(0, sub - appliedPromo.discount_amount) : sub;
  };

  const handleValidatePromo = async () => {
    if (!promoCodeInput.trim() || !activeModalProduct) return;
    setIsValidatingPromo(true); setPromoError('');
    try {
      const res = await api.post('/catalog/promocode/validate', {
        code: promoCodeInput, amount: getSubtotalUsd(), product_id: activeModalProduct.id,
      });
      if (res.data?.valid) setAppliedPromo(res.data);
    } catch (err: any) {
      setPromoError(err.response?.data?.detail || 'Invalid or expired promocode');
      setAppliedPromo(null);
    } finally { setIsValidatingPromo(false); }
  };

  // Upvotes & Reviews state
  const [upvotes, setUpvotes] = useState<Record<string, { count: number; has_upvoted: boolean }>>({});
  const [reviewModalProduct, setReviewModalProduct] = useState<Product | null>(null);
  const [reviewsData, setReviewsData] = useState<{ average_rating: number; total_reviews: number; reviews: any[] }>({
    average_rating: 5.0,
    total_reviews: 0,
    reviews: []
  });
  const [isLoadingReviews, setIsLoadingReviews] = useState(false);
  const [newRating, setNewRating] = useState(5);
  const [newComment, setNewComment] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const handleUpvote = async (productId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }
    try {
      const res = await api.post(`/catalog/products/${productId}/upvote`);
      const hasUp = res.data.has_upvoted;
      setUpvotes(prev => {
        const current = prev[productId] || { count: 12, has_upvoted: false };
        return {
          ...prev,
          [productId]: {
            count: hasUp ? current.count + 1 : Math.max(0, current.count - 1),
            has_upvoted: hasUp
          }
        };
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to upvote.");
    }
  };

  const handleOpenReviews = async (p: Product, e: React.MouseEvent) => {
    e.stopPropagation();
    setReviewModalProduct(p);
    setIsLoadingReviews(true);
    try {
      const res = await api.get(`/catalog/products/${p.id}/reviews`);
      setReviewsData(res.data);
    } catch {
      setReviewsData({ average_rating: 5.0, total_reviews: 0, reviews: [] });
    } finally {
      setIsLoadingReviews(false);
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewModalProduct || !newComment.trim()) return;
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }
    setIsSubmittingReview(true);
    try {
      const res = await api.post(`/catalog/products/${reviewModalProduct.id}/reviews`, {
        rating: newRating,
        comment: newComment.trim(),
      });
      setReviewsData(prev => ({
        ...prev,
        total_reviews: prev.total_reviews + 1,
        reviews: [res.data.review, ...prev.reviews]
      }));
      setNewComment('');
      alert("Thank you! Your verified review has been published.");
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to submit review.");
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const handleBalanceCheckout = async () => {
    if (!activeModalProduct) return;
    if (!customerEmail.trim()) {
      setOrderError('Please enter your delivery email address');
      return;
    }
    const finalCostUsd = getFinalTotalUsd();
    if (user && user.balance < finalCostUsd) {
      setPaymentMethod('nepal_qr');
      setOrderError(`Insufficient wallet balance (${formatNpr(user.balance)}). Switched to direct eSewa/Fonepay QR payment below!`);
      return;
    }
    setIsSubmittingOrder(true); setOrderError('');
    try {
      const res = await api.post('/payments/checkout', {
        items: [{ product_id: activeModalProduct.id, quantity }],
        promo_code: appliedPromo?.code || null,
        payment_method: 'balance',
        customer_email: customerEmail.trim(),
      });
      if (res.data?.status === 'success') {
        setDeliveredContent(res.data.delivered_content || 'Purchase complete!');
        setDeliveredEmail(customerEmail.trim());
        setActiveModalProduct(null); fetchUser();
      } else { setOrderError(res.data?.message || 'Checkout failed'); }
    } catch (err: any) {
      setPaymentMethod('nepal_qr');
      setOrderError('Insufficient wallet balance. Scan the eSewa / Fonepay QR below to complete your order!');
    } finally { setIsSubmittingOrder(false); }
  };

  const handleNepalQrSubmit = async () => {
    if (!customerEmail.trim() || !customerEmail.includes('@')) {
      setOrderError('Please enter a valid customer email address for delivery');
      return;
    }
    if (!nepalTxId.trim() || !activeModalProduct) { 
      setOrderError('Please enter your transaction reference ID / eSewa code'); 
      return; 
    }
    setIsSubmittingOrder(true); setOrderError('');
    const totalUsd = getFinalTotalUsd();
    const totalNpr = Math.round(totalUsd * 300);
    try {
      const res = await api.post('/payments/nepal-submit', {
        tx_id: nepalTxId.trim(),
        amount_usd: totalUsd,
        amount_npr: totalNpr,
        product_id: activeModalProduct.id,
        customer_email: customerEmail.trim(),
        proof_image: proofImage,
        note: `Order: ${activeModalProduct.name} x${quantity} | Delivery Email: ${customerEmail.trim()}`,
      });
      if (res.data?.status === 'success') {
        setDeliveredContent(
          `🇳🇵 NEPAL PAYMENT SUBMITTED!\n\n` +
          `Transaction / Ref ID: ${nepalTxId}\n` +
          `Amount: NPR ${totalNpr.toLocaleString()}\n` +
          `Product: ${activeModalProduct.name} (x${quantity})\n` +
          `Delivery Email: ${customerEmail.trim()}\n` +
          (proofImage ? `Receipt Screenshot: Attached ✓\n\n` : `\n`) +
          `Status: Pending Admin Verification\n` +
          `Our system will automatically dispatch your credentials & order confirmation to ${customerEmail.trim()} upon admin verification.`
        );
        setDeliveredEmail(customerEmail.trim());
        setActiveModalProduct(null); setNepalTxId(''); setProofImage(null); setProofFileName('');
      }
    } catch (err: any) { setOrderError(err.response?.data?.detail || 'Failed to submit payment reference'); }
    finally { setIsSubmittingOrder(false); }
  };

  const inStockCount = products.filter(p => p.stock > 0).length;
  const outOfStockCount = products.filter(p => p.stock === 0).length;

  return (
    <div className="min-h-screen bg-background relative transition-colors duration-300 selection:bg-red-600 selection:text-white">
      {/* Top Sacred Mantra Bar */}
      <div className="top-mantra-bar w-full bg-gradient-to-r from-red-950/80 via-red-900/40 to-red-950/80 border-b border-red-500/20 py-1.5 px-4 text-center">
        <p className="text-[10px] font-bold text-red-400 tracking-widest font-vedic uppercase flex items-center justify-center gap-2">
          <Shield className="w-3.5 h-3.5 text-red-400 shrink-0" />
          <span>{publicSettings?.mantra_bar_text || "॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥"}</span>
          <Shield className="w-3.5 h-3.5 text-red-400 shrink-0" />
        </p>
      </div>

      {/* Broadcast Announcement Banner */}
      {publicSettings?.announcement_banner_enabled && publicSettings?.announcement_banner_text && (
        <div className={`w-full py-2 px-4 text-center text-xs font-semibold flex items-center justify-center gap-2 border-b animate-in slide-in-from-top ${
          publicSettings.announcement_banner_type === "warning"
            ? "bg-amber-950/90 text-amber-200 border-amber-500/40"
            : publicSettings.announcement_banner_type === "success"
            ? "bg-emerald-950/90 text-emerald-200 border-emerald-500/40"
            : "bg-purple-950/90 text-purple-200 border-purple-500/40"
        }`}>
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>{publicSettings.announcement_banner_text}</span>
        </div>
      )}

      {/* Ambient background glows */}
      <div className="fixed top-0 left-0 w-[600px] h-[600px] rounded-full bg-red-600/10 blur-[160px] pointer-events-none -translate-x-1/2 -translate-y-1/2" />
      <div className="fixed bottom-0 right-0 w-[500px] h-[500px] rounded-full bg-rose-600/10 blur-[140px] pointer-events-none translate-x-1/3 translate-y-1/3" />

      {/* ─── Navbar ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-red-500/20 glass">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-[62px] flex items-center justify-between gap-4">
          {/* Logo */}
          <Link href="/nepal" className="flex items-center gap-2.5 flex-shrink-0 group">
            <div className="relative w-10 h-10 rounded-full p-0.5 bg-gradient-to-br from-red-500 to-rose-600 shadow-md shadow-red-500/40 overflow-hidden shrink-0 animate-kaali-pulse">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.png" alt="Kali Digital Store" className="w-full h-full object-cover rounded-full" />
            </div>
            <div className="flex flex-col">
              <span className="font-black text-sm tracking-tight font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
                KALI DIGITAL STORE
              </span>
              <span className="text-[9px] font-bold text-red-400 mt-0.5 flex items-center gap-1">
                <span className="px-1 py-0.2 rounded bg-red-500/20 text-[8px] font-mono font-bold text-red-300">NPR</span>
                <span>NEPAL PORTAL</span>
              </span>
            </div>
          </Link>

          {/* Search bar */}
          <div className="hidden md:flex flex-1 max-w-md mx-4 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search products in Nepali Rupees (NPR)..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-secondary/50 border border-red-500/30 rounded-full pl-10 pr-4 py-2 text-xs focus:outline-none focus:border-red-500 focus:bg-secondary transition-all font-medium"
            />
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Switch Region back to Gateway */}
            <Link
              href="/"
              title="Change Country / Region"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-secondary/70 border border-red-500/30 text-xs font-bold text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              <Globe className="w-3.5 h-3.5 text-red-400" />
              <span>Nepal (NPR)</span>
            </Link>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
              className="w-9 h-9 rounded-full bg-secondary/60 border border-red-500/20 flex items-center justify-center hover:bg-accent transition-all"
            >
              {theme === 'dark'
                ? <Sun className="w-4 h-4 text-amber-400" />
                : <Moon className="w-4 h-4 text-indigo-500" />}
            </button>

            {user ? (
              <>
                <Link
                  href="/dashboard"
                  className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-red-500/15 border border-red-500/30 text-xs font-bold text-red-400 hover:bg-red-500/25 transition-all shadow-sm"
                >
                  <Wallet className="w-3.5 h-3.5" />
                  {formatNpr(user.balance)}
                </Link>
                <Link
                  href="/dashboard"
                  className="px-3.5 py-1.5 rounded-full bg-secondary border border-border/80 text-xs font-bold hover:bg-accent transition-all"
                >
                  Account
                </Link>
              </>
            ) : (
              <Link
                href="/login"
                className="px-4 py-2 rounded-full bg-red-600 text-white text-xs font-extrabold hover:bg-red-500 transition-all shadow-md shadow-red-600/30"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* ─── Nepal Store Coming Soon Announcement Banner ─────────────────────── */}
      {nepalQrData?.coming_soon && (
        <div className="w-full bg-gradient-to-r from-amber-950/90 via-red-950/80 to-amber-950/90 border-b border-amber-500/40 p-4 sm:p-5 animate-in slide-in-from-top-4 duration-300 relative z-30">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 text-amber-400 shadow-lg shadow-amber-500/10">
              <Rocket className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                  <span className="px-1 py-0.2 rounded bg-amber-500/30 text-[8px] font-bold">NPR</span>
                  <span>NEPAL STORE • COMING SOON</span>
                </span>
              </div>
              <p className="text-xs font-semibold text-amber-100/90 mt-1 leading-relaxed">
                {nepalQrData.coming_soon_text || "Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ─── Redesigned Premium Nepali Hero Section ───────────────────────── */}
      <section className="hero-banner relative overflow-hidden border-b border-red-500/20 bg-gradient-to-b from-red-950/40 via-background to-background py-10 md:py-14 shadow-[0_0_50px_rgba(225,29,72,0.1)]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center relative z-10">
          
          {/* 1. Student / Young Developer Initiative Badge */}
          <div className="inline-flex flex-col items-center mb-4">
            <button
              onClick={() => setIsAboutExpanded(!isAboutExpanded)}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-red-500/30 bg-red-500/10 hover:bg-red-500/15 text-red-300 text-[11px] font-semibold transition-all shadow-sm group"
            >
              <span className="px-1.5 py-0.2 rounded bg-red-500/20 text-[9px] font-mono font-bold text-red-300">NPR</span>
              <span>नेपाली युवा प्रविधि उत्साहीहरूको स्वतन्त्र पहल</span>
              <ChevronDown className={`w-3 h-3 text-red-400 transition-transform duration-200 ${isAboutExpanded ? 'rotate-180' : ''}`} />
            </button>
            
            {isAboutExpanded && (
              <div className="mt-2.5 p-3 rounded-2xl bg-secondary/90 border border-red-500/30 text-xs text-muted-foreground max-w-lg animate-in fade-in slide-in-from-top-2 duration-200 text-center leading-relaxed shadow-lg">
                नेपालका विद्यार्थी तथा युवा प्रविधि उत्साहीहरूले विकास तथा सञ्चालन गरेको ग्राहक-केन्द्रित डिजिटल सेवा।
              </div>
            )}
          </div>

          {/* 2. Main Brand Title */}
          <h1 className="hero-title text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-tight mb-2 font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
            KALI DIGITAL STORE NEPAL
          </h1>

          {/* 3. Refined Tagline */}
          <div className="text-base sm:text-xl font-bold text-red-400 mb-4 tracking-wide font-sans">
            छिटो सेवा • भरपर्दो सहयोग • स्पष्ट जानकारी
          </div>

          {/* 4. Natural Nepali Product Intro */}
          <p className="hero-desc text-muted-foreground max-w-2xl mx-auto mb-6 text-xs sm:text-sm font-medium leading-relaxed">
            <span className="text-foreground font-semibold">ChatGPT, Gemini, Claude, Canva, Netflix, VPN</span> तथा अन्य लोकप्रिय डिजिटल सेवाहरू नेपाली रुपैयाँमै सहज रूपमा उपलब्ध। खरिदपछि आवश्यक विवरण तथा सक्रियताका लागि सहयोग प्राप्त गर्नुहोस्।
          </p>

          {/* 5. Trust & Payment Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 text-xs mb-7 font-semibold">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary/60 border border-border/80 text-foreground shadow-sm">
              <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span>छिटो सक्रियता</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary/60 border border-border/80 text-foreground shadow-sm">
              <CreditCard className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>eSewa • Khalti • Fonepay</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary/60 border border-border/80 text-foreground shadow-sm">
              <HeartHandshake className="w-3.5 h-3.5 text-rose-400 shrink-0" />
              <span>नेपाली ग्राहक सहायता</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary/60 border border-border/80 text-foreground shadow-sm">
              <RefreshCw className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              <span>सर्तअनुसार प्रतिस्थापन सुविधा</span>
            </div>
          </div>

          {/* 6. Expandable Transparency & Pricing Info Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mx-auto mb-6 text-left">
            {/* Card 1: महत्वपूर्ण सूचना (Transparency Notice) */}
            <div className="rounded-2xl border border-red-500/20 bg-secondary/30 backdrop-blur-sm overflow-hidden transition-all">
              <button
                type="button"
                onClick={() => setIsDisclaimerExpanded(!isDisclaimerExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between text-xs font-bold text-foreground hover:bg-secondary/50 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Info className="w-3.5 h-3.5 text-red-400 shrink-0" />
                  <span>महत्वपूर्ण सूचना</span>
                </span>
                <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${isDisclaimerExpanded ? 'rotate-180' : ''}`} />
              </button>
              {isDisclaimerExpanded && (
                <div className="px-4 pb-3.5 text-[11px] text-muted-foreground leading-relaxed border-t border-border/40 pt-2.5 animate-in fade-in duration-200 space-y-1.5">
                  <p>
                    <b className="text-foreground">KALI DIGITAL STORE</b> सम्बन्धित सेवा प्रदायकहरूको आधिकारिक प्रतिनिधि वा अधिकृत विक्रेता होइन। हामी स्वतन्त्र रूपमा डिजिटल सेवा तथा सदस्यता उपलब्ध गराउने सेवा प्रदायक हौं।
                  </p>
                  <p>
                    सम्बन्धित ब्रान्ड तथा सेवाका नामहरू तिनका आधिकारिक कम्पनीहरूको ट्रेडमार्क हुन्। हाम्रो उद्देश्य ग्राहकहरूका लागि डिजिटल सेवाको पहुँच, सक्रियता र प्रयोगसम्बन्धी सहयोग सरल र सहज बनाउनु हो।
                  </p>
                </div>
              )}
            </div>

            {/* Card 2: किन मूल्य कम छ? (Why are prices so low?) */}
            <div className="rounded-2xl border border-amber-500/20 bg-secondary/30 backdrop-blur-sm overflow-hidden transition-all">
              <button
                type="button"
                onClick={() => setIsPricingInfoExpanded(!isPricingInfoExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between text-xs font-bold text-foreground hover:bg-secondary/50 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <HelpCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>किन मूल्य कम छ?</span>
                </span>
                <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${isPricingInfoExpanded ? 'rotate-180' : ''}`} />
              </button>
              {isPricingInfoExpanded && (
                <div className="px-4 pb-3.5 text-[11px] text-muted-foreground leading-relaxed border-t border-border/40 pt-2.5 animate-in fade-in duration-200 space-y-1.5">
                  <p>
                    हाम्रा केही डिजिटल उत्पादनहरू प्रचारात्मक अफर, विशेष छुट, क्षेत्रीय मूल्य निर्धारण तथा विभिन्न डिजिटल प्रमोशनमार्फत प्राप्त हुने भएकाले नियमित बजार मूल्यभन्दा कम मूल्यमा उपलब्ध हुन्छन्।
                  </p>
                  <p>
                    त्यसैले प्रत्येक उत्पादनको अवधि, सुविधा, प्रयोगसम्बन्धी सीमा तथा नियमहरू फरक हुन सक्छन्। खरिद गर्नुअघि सम्बन्धित उत्पादनको विवरण ध्यानपूर्वक पढ्नुहोस्। (कम मूल्य हुनुको अर्थ सबै उत्पादनका सर्तहरू आधिकारिक वेबसाइटको नियमित योजनासँग पूर्ण समान हुन्छन् भन्ने होइन।)
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* 7. Clear Terms & Conditions Callout */}
          <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 max-w-2xl mx-auto flex items-start sm:items-center gap-3 text-left">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
            <div className="text-xs">
              <span className="font-bold text-amber-200 block sm:inline">
                ⚠️ खरिद गर्नुअघि उत्पादनको विवरण, अवधि, सीमितता तथा नियम र सर्तहरू ध्यानपूर्वक पढ्नुहोस्।
              </span>
              <span className="text-[11px] text-amber-300/80 block mt-0.5">
                सर्तहरू प्रत्येक उत्पादनअनुसार फरक हुन सक्छन्। खरिदपछि अनभिज्ञ रहनुभन्दा पहिले नै सबै विवरण बुझेर मात्र अर्डर गर्नुहोस्।
              </span>
            </div>
          </div>

          {/* Mobile search */}
          <div className="flex md:hidden relative max-w-md mx-auto mt-6">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search in NPR catalog..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-secondary/60 border border-red-500/30 rounded-full pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-red-500 transition-all font-medium"
            />
          </div>
        </div>
      </section>

      {/* ─── Sticky Frozen Category & Status Bar ────────────────────────── */}
      <div className="sticky top-[62px] z-30 w-full bg-background/95 backdrop-blur-md border-b border-red-500/20 shadow-md shadow-black/10">
        {/* Row 1: Category pills */}
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 pt-3 pb-2">
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
            {/* Tab 1: Featured Picks (Default) */}
            <button
              onClick={() => setSelectedCategory('featured')}
              className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'featured'
                  ? 'bg-amber-500 text-black border-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.5)] font-extrabold'
                  : 'bg-secondary/60 border-amber-500/30 text-amber-300 hover:text-white hover:bg-secondary'
              }`}
            >
              {getCategoryIcon('featured', selectedCategory === 'featured')}
              <span>Featured Picks ({featuredCount})</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-extrabold ${
                selectedCategory === 'featured' ? 'bg-black/20 text-black' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              }`}>
                HOT
              </span>
            </button>

            {/* Tab 2: All Products */}
            <button
              onClick={() => setSelectedCategory('all')}
              className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'all'
                  ? 'bg-red-600 text-white border-red-500 shadow-[0_0_15px_rgba(225,29,72,0.5)] font-extrabold'
                  : 'bg-secondary/60 border-red-500/20 text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              {getCategoryIcon('all', selectedCategory === 'all')}
              <span>All Products ({products.length})</span>
            </button>
            {AUTO_CATEGORIES.map(cat => {
              const count = categoryCounts[cat.id] || 0;
              if (count === 0) return null;
              const isSelected = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all border flex items-center gap-1.5 ${
                    isSelected
                      ? 'bg-red-600 text-white border-red-500 shadow-[0_0_15px_rgba(225,29,72,0.5)] font-extrabold'
                      : 'bg-secondary/60 border-red-500/20 text-muted-foreground hover:text-foreground hover:bg-secondary'
                  }`}
                >
                  {getCategoryIcon(cat.id, isSelected)}
                  <span>{cat.label} ({count})</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-extrabold ${
                    isSelected ? 'bg-white/20 text-white' : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                  }`}>
                    {cat.purchases}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
        {/* Row 2: Stock filter + view mode — also frozen */}
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 pb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center p-1 bg-secondary/60 border border-border/70 rounded-full text-xs font-bold">
            <button
              onClick={() => setStockFilter('all')}
              className={`px-3 py-1.5 rounded-full transition-all ${stockFilter === 'all' ? 'bg-red-500 text-white' : 'text-muted-foreground hover:text-foreground'}`}
            >All</button>
            <button
              onClick={() => setStockFilter('in_stock')}
              className={`px-3 py-1.5 rounded-full transition-all flex items-center gap-1 ${stockFilter === 'in_stock' ? 'bg-emerald-500 text-white' : 'text-emerald-500 hover:bg-emerald-500/10'}`}
            >
              <PackageCheck className="w-3 h-3" /> In Stock ({inStockCount})
            </button>
            <button
              onClick={() => setStockFilter('out_of_stock')}
              className={`px-3 py-1.5 rounded-full transition-all flex items-center gap-1 ${stockFilter === 'out_of_stock' ? 'bg-rose-500 text-white' : 'text-rose-400 hover:bg-rose-500/10'}`}
            >
              <PackageX className="w-3 h-3" /> Out of Stock ({outOfStockCount})
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-medium">{filteredProducts.length} items available in NPR</span>
            <div className="flex items-center p-1 bg-secondary/60 border border-border/70 rounded-lg">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded transition-all ${viewMode === 'grid' ? 'bg-red-500 text-white' : 'text-muted-foreground hover:text-foreground'}`}
              ><LayoutGrid className="w-3.5 h-3.5" /></button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded transition-all ${viewMode === 'list' ? 'bg-red-500 text-white' : 'text-muted-foreground hover:text-foreground'}`}
              ><List className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Main Catalog Content ───────────────────────────────────────── */}
      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">


        {/* Product Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="glass-card rounded-2xl animate-pulse h-72" />
            ))}
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="text-center py-24 glass-card rounded-3xl">
            <div className="text-5xl mb-4">🔍</div>
            <h3 className="text-lg font-bold text-foreground mb-2">No Products Found</h3>
            <p className="text-muted-foreground text-sm">Try adjusting your search or category filter.</p>
            <button
              onClick={() => { setSearchTerm(''); setSelectedCategory('all'); setStockFilter('all'); }}
              className="mt-6 px-6 py-2.5 rounded-full text-sm font-bold text-white bg-red-500 hover:bg-red-600 transition-all"
            >Clear Filters</button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filteredProducts.map(product => {
              const productUpvotes = upvotes[product.id] || { count: 15, has_upvoted: false };
              const { deliveryBadge, accBadge } = getProductBadges(product);
              return (
                <div
                  key={product.id}
                  className="glass-card rounded-2xl overflow-hidden flex flex-col group hover:-translate-y-1 hover:border-red-500/40 hover:shadow-[0_8px_30px_rgba(239,68,68,0.2)] transition-all duration-300 cursor-pointer relative justify-between"
                  onClick={() => handleOpenBuyModal(product)}
                >
                  <div className="relative p-6 pb-4 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/10 via-amber-500/10 to-transparent flex items-center justify-center mb-3 group-hover:scale-110 group-hover:border-red-500/40 transition-all duration-300 shadow-inner">
                      <ProductIcon name={product.name} size="lg" />
                    </div>

                    <div className="absolute top-3 right-3 flex items-center gap-1.5">
                      <button
                        onClick={(e) => handleUpvote(product.id, e)}
                        className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold flex items-center gap-1 transition-all border ${
                          productUpvotes.has_upvoted
                            ? 'bg-red-500 text-white border-red-500'
                            : 'bg-secondary/80 text-muted-foreground hover:text-foreground border-border/60 hover:bg-secondary'
                        }`}
                        title="Upvote item"
                      >
                        <ThumbsUp className="w-3 h-3" />
                        <span>{productUpvotes.count}</span>
                      </button>
                    </div>

                    <div className="absolute top-3 left-3 flex flex-col gap-1 items-start">
                      {product.is_featured && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                          <Star className="w-2.5 h-2.5 fill-amber-400 text-amber-400" />
                          <span>Featured</span>
                        </span>
                      )}
                      <div className="flex items-center gap-1 flex-wrap">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 border ${deliveryBadge.cls}`}>
                          {deliveryBadge.icon}
                          <span>{deliveryBadge.label}</span>
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 border ${accBadge.cls}`}>
                          <span>{accBadge.label}</span>
                        </span>
                      </div>
                    </div>

                    <h3 className="font-bold text-sm text-foreground mb-1 line-clamp-2 text-center group-hover:text-red-400 transition-colors leading-snug mt-6">
                      {product.name}
                    </h3>
                    <p className="text-[11px] text-muted-foreground line-clamp-1 text-center mb-3">
                      {product.description}
                    </p>

                    {/* Review and Social proof trigger */}
                    <div 
                      onClick={(e) => handleOpenReviews(product, e)}
                      className="flex items-center gap-1.5 text-[10px] text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 px-2 py-0.5 rounded-full transition-all"
                    >
                      <div className="flex text-amber-300">
                        {[...Array(5)].map((_, i) => (
                          <Star key={i} className={`w-2.5 h-2.5 ${i < Math.floor(product.rating || 5) ? 'fill-amber-300 text-amber-300' : 'text-amber-300/30'}`} />
                        ))}
                      </div>
                      <span className="font-bold">{product.rating || 4.8} ({product.reviews_count || 24})</span>
                    </div>
                  </div>

                  <div className="p-4 pt-3 border-t border-border/40 bg-secondary/20 flex items-center justify-between gap-3 mt-auto">
                    <div>
                      <div className="text-[10px] text-muted-foreground font-medium uppercase">Price (NPR)</div>
                      <div className="text-lg font-black text-red-400">
                        {formatNpr(product.price)}
                      </div>
                    </div>
                    {product.stock === 0 ? (
                      <span className="px-3 py-1.5 rounded-xl text-xs font-bold text-red-400 bg-red-500/10 border border-red-500/30">
                        Sold Out
                      </span>
                    ) : (
                      <button
                        onClick={() => handleOpenBuyModal(product)}
                        className="px-4 py-2 rounded-xl text-xs font-extrabold text-white bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 shadow-md shadow-red-500/20 flex items-center gap-1.5 transition-all group-hover:scale-105"
                      >
                        Buy Now
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filteredProducts.map(product => {
              const { deliveryBadge, accBadge } = getProductBadges(product);
              return (
                <div
                  key={product.id}
                  className="glass-card rounded-xl px-4 py-3 flex items-center gap-4 hover:border-red-500/40 transition-all group cursor-pointer"
                  onClick={() => handleOpenBuyModal(product)}
                >
                  <div className="w-10 h-10 rounded-xl border border-red-500/20 bg-gradient-to-br from-red-500/10 to-amber-500/10 flex items-center justify-center flex-shrink-0 shadow-inner">
                    <ProductIcon name={product.name} size="sm" />
                  </div>
                  <div className="flex-grow min-w-0">
                    <div className="font-bold text-sm text-foreground group-hover:text-red-400 transition-colors truncate flex items-center gap-2">
                      <span>{product.name}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${deliveryBadge.cls}`}>
                        {deliveryBadge.label}
                      </span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${accBadge.cls}`}>
                        {accBadge.label}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">{product.description}</div>
                  </div>
                  <div className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${product.stock > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                    {product.stock > 0 ? 'In Stock' : 'Sold Out'}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="font-black text-red-400">
                      {formatNpr(product.price)}
                    </div>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); handleOpenBuyModal(product); }}
                    disabled={product.stock === 0}
                    className="flex-shrink-0 px-3 py-1.5 text-white text-xs font-bold rounded-lg bg-red-500 hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >Buy</button>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 mt-16 py-8">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2 font-bold text-foreground">
            <div className="w-6 h-6 rounded-lg bg-red-500 flex items-center justify-center">
              <Bolt className="w-3 h-3 text-white" />
            </div>
            KDS Digital Store • Nepal Official (NPR)
          </div>
          <div>© {new Date().getFullYear()} KDS Digital Store Nepal. All rights reserved.</div>
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="hover:text-foreground transition-colors">Account Dashboard</Link>
            <Link href="/" className="hover:text-foreground transition-colors">Change Region</Link>
          </div>
        </div>
      </footer>

      {/* ─── Nepal Exclusive Checkout Modal ──────────────────────────────── */}
      {activeModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 relative border border-red-500/30 shadow-[0_0_60px_rgba(0,0,0,0.8)] max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setActiveModalProduct(null)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            ><X className="w-4 h-4" /></button>

            {/* Product header */}
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-2xl border border-red-500/30 bg-red-500/10 flex items-center justify-center flex-shrink-0 shadow-inner">
                <ProductIcon name={activeModalProduct.name} size="lg" />
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-1 flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5" />
                  <span>Nepal Order Checkout</span>
                </div>
                <h2 className="text-base font-bold leading-snug">{activeModalProduct.name}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{activeModalProduct.description}</p>
              </div>
            </div>

            {/* Quantity */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-secondary/40 border border-border/50 mb-4">
              <span className="text-xs font-semibold text-muted-foreground">Quantity</span>
              <div className="flex items-center gap-3">
                <button onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  className="w-8 h-8 rounded-lg bg-secondary border border-border text-foreground font-bold flex items-center justify-center hover:bg-accent">−</button>
                <span className="text-sm font-bold w-6 text-center">{quantity}</span>
                <button onClick={() => setQuantity(Math.min(activeModalProduct.stock || 99, quantity + 1))}
                  className="w-8 h-8 rounded-lg bg-secondary border border-border text-foreground font-bold flex items-center justify-center hover:bg-accent">+</button>
              </div>
            </div>

            {/* Promocode */}
            <div className="mb-4">
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Promocode (optional)</label>
              <div className="flex gap-2">
                <div className="relative flex-grow">
                  <Tag className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input type="text" placeholder="e.g. SAVE20"
                    value={promoCodeInput}
                    onChange={e => setPromoCodeInput(e.target.value.toUpperCase())}
                    className="w-full bg-secondary/40 border border-border/60 rounded-xl pl-9 pr-3 py-2 text-xs font-bold uppercase focus:outline-none focus:border-red-500 transition-all" />
                </div>
                <button onClick={handleValidatePromo} disabled={isValidatingPromo || !promoCodeInput.trim()}
                  className="px-4 py-2 bg-secondary text-secondary-foreground text-xs font-bold rounded-xl hover:bg-secondary/80 disabled:opacity-50">
                  {isValidatingPromo ? '...' : 'Apply'}
                </button>
              </div>
              {appliedPromo && (
                <div className="mt-2 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-400 font-medium">
                  <span>✓ Code <b>{appliedPromo.code}</b> applied!</span>
                  <span>−{formatNpr(appliedPromo.discount_amount)}</span>
                </div>
              )}
              {promoError && <p className="text-[11px] text-rose-400 mt-1">{promoError}</p>}
            </div>

            {/* Customer Delivery Email Address */}
            <div className="mb-4">
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block flex items-center justify-between">
                <span>Customer Email Address (for Order Delivery)</span>
                <span className="text-[10px] text-red-400 font-bold">*Required</span>
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="e.g. yourname@gmail.com"
                  value={customerEmail}
                  onChange={e => setCustomerEmail(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/70 rounded-xl pl-10 pr-3 py-2.5 text-xs font-semibold focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
              <p className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
                <Mail className="w-3 h-3 text-red-400" />
                <span>Digital keys and account credentials will be automatically dispatched to this email.</span>
              </p>
            </div>

            {/* Payment Method Selector */}
            <div className="mb-4">
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Payment Method (Nepal)</label>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={() => { setPaymentMethod('nepal_qr'); fetchNepalQrDetails(); }}
                  className={`p-3 rounded-xl border text-left text-xs font-bold transition-all ${paymentMethod === 'nepal_qr' ? 'bg-red-500/20 border-red-500 text-red-300 shadow-sm' : 'bg-secondary/40 border-border/60 hover:bg-secondary text-muted-foreground'}`}>
                  <span className="block font-black text-foreground flex items-center gap-1">
                    <QrCode className="w-3.5 h-3.5 text-red-400" />
                    <span>eSewa / Fonepay</span>
                  </span>
                  <span className="text-[10px] font-normal text-muted-foreground">Scan QR Code directly</span>
                </button>
                <button type="button" onClick={() => setPaymentMethod('balance')}
                  className={`p-3 rounded-xl border text-left text-xs font-bold transition-all ${paymentMethod === 'balance' ? 'bg-red-500/20 border-red-500 text-red-300 shadow-sm' : 'bg-secondary/40 border-border/60 hover:bg-secondary text-muted-foreground'}`}>
                  <span className="block font-black text-foreground flex items-center gap-1">
                    <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                    <span>NPR Wallet</span>
                  </span>
                  <span className="text-[10px] font-normal text-muted-foreground">{user ? `Balance: ${formatNpr(user.balance)}` : 'Instant deduction'}</span>
                </button>
              </div>
            </div>

            {/* QR Details */}
            {paymentMethod === 'nepal_qr' && (
              <div className="mb-4 p-4 rounded-2xl bg-secondary/40 border border-red-500/30 space-y-3">
                <div className="text-center">
                  <div className="text-[11px] font-extrabold uppercase text-red-400 mb-1.5 tracking-wider flex items-center justify-center gap-1.5">
                    <QrCode className="w-3.5 h-3.5" />
                    <span>{nepalQrData?.title || 'Direct eSewa / Khalti / Fonepay QR'}</span>
                  </div>
                  {nepalQrData?.qr_url && (
                    <div className="my-2 p-2 bg-white rounded-2xl inline-block shadow-md">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={nepalQrData.qr_url} alt="Nepal QR" className="w-40 h-40 object-contain mx-auto" />
                    </div>
                  )}
                  <p className="text-xs font-bold text-foreground mt-1">
                    Account: <span className="text-red-400">{nepalQrData?.account_name || 'KDS Digital Store Nepal'}</span>
                  </p>
                  <p className="text-xs font-mono text-muted-foreground">eSewa/Mobile: {nepalQrData?.account_id || '9800000000'}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Pay exact amount: <b className="text-emerald-400 font-extrabold">{formatNpr(getFinalTotalUsd())}</b>
                  </p>
                </div>
                <div>
                  <label className="text-[11px] font-bold text-muted-foreground block mb-1">Enter Transaction Reference / eSewa Code:</label>
                  <input type="text" placeholder="e.g. 000001234567 or eSewa Code"
                    value={nepalTxId} onChange={e => setNepalTxId(e.target.value)}
                    className="w-full bg-secondary/60 border border-border/80 rounded-xl px-3 py-2 text-xs font-mono font-bold focus:outline-none focus:border-red-500" />
                </div>

                {/* Photo / Screenshot Upload */}
                <div>
                  <label className="text-[11px] font-bold text-muted-foreground block mb-1 flex items-center justify-between">
                    <span>Payment Screenshot / Receipt (Optional):</span>
                    <span className="text-[10px] text-muted-foreground">JPG, PNG up to 5MB</span>
                  </label>
                  
                  {!proofImage ? (
                    <label className="flex flex-col items-center justify-center p-3.5 border-2 border-dashed border-border/80 hover:border-red-500/60 rounded-xl cursor-pointer bg-secondary/20 hover:bg-secondary/40 transition-all text-center">
                      <UploadCloud className="w-5 h-5 text-red-400 mb-1" />
                      <span className="text-xs font-bold text-foreground">Click to upload payment screenshot</span>
                      <span className="text-[10px] text-muted-foreground mt-0.5">Attach your eSewa/Khalti transfer receipt for fastest approval</span>
                      <input type="file" accept="image/*" className="hidden" onChange={handleProofImageChange} />
                    </label>
                  ) : (
                    <div className="relative p-2.5 rounded-xl bg-secondary/50 border border-border flex items-center gap-3">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={proofImage} alt="Receipt Preview" className="w-12 h-12 rounded-lg object-cover border border-border flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-foreground truncate">{proofFileName || 'payment_receipt.jpg'}</p>
                        <p className="text-[10px] text-emerald-400 font-semibold">✓ Receipt screenshot attached</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => { setProofImage(null); setProofFileName(''); }}
                        className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors"
                        title="Remove image"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Price breakdown */}
            <div className="p-4 rounded-xl bg-secondary/30 border border-border/40 mb-4 space-y-2 text-xs">
              <div className="flex justify-between text-muted-foreground"><span>Unit Price</span><span>{formatNpr(activeModalProduct.price)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Subtotal ({quantity}×)</span><span>{formatNpr(getSubtotalUsd())}</span></div>
              {appliedPromo && (
                <div className="flex justify-between text-emerald-400 font-semibold"><span>Promocode Discount</span><span>−{formatNpr(appliedPromo.discount_amount)}</span></div>
              )}
              <div className="pt-2 border-t border-border/40 flex justify-between items-center text-sm font-extrabold">
                <span>Total Amount (NPR)</span>
                <span className="text-lg font-black text-red-400">{formatNpr(getFinalTotalUsd())}</span>
              </div>
            </div>

            {orderError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2 font-medium">
                <AlertCircle className="w-4 h-4 shrink-0" /><span>{orderError}</span>
              </div>
            )}

            <button
              onClick={paymentMethod === 'nepal_qr' ? handleNepalQrSubmit : handleBalanceCheckout}
              disabled={isSubmittingOrder}
              className="w-full py-3.5 font-extrabold text-sm rounded-xl text-white bg-red-500 hover:bg-red-600 shadow-red-500/30 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg"
            >
              {isSubmittingOrder ? <><RefreshCw className="w-4 h-4 animate-spin" /> Processing...</>
                : paymentMethod === 'nepal_qr'
                ? <>Submit Reference — {formatNpr(getFinalTotalUsd())} <ArrowRight className="w-4 h-4" /></>
                : <>Confirm & Pay {formatNpr(getFinalTotalUsd())} <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        </div>
      )}

      {/* Delivery Modal */}
      {deliveredContent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 border border-emerald-500/30 shadow-[0_0_60px_rgba(34,197,94,0.2)]">
            <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-xl font-bold text-center mb-1">Order Processed! 🎉</h2>
            <p className="text-xs text-muted-foreground text-center mb-4">Your order details and digital credentials are shown below.</p>
            
            {deliveredEmail && (
              <div className="mb-4 p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-semibold flex items-center gap-2.5">
                <Mail className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>An automated copy with digital credentials was dispatched to <b>{deliveredEmail}</b>.</span>
              </div>
            )}

            <div className="relative mb-5">
              <pre className="w-full p-4 rounded-2xl bg-black/60 border border-border/80 text-xs font-mono text-emerald-300 overflow-x-auto whitespace-pre-wrap max-h-52">
                {deliveredContent}
              </pre>
              <button
                onClick={() => { navigator.clipboard.writeText(deliveredContent); setCopied(true); setTimeout(() => setCopied(false), 2500); }}
                className="absolute top-3 right-3 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-xs font-bold flex items-center gap-1.5"
              >
                {copied ? <><Check className="w-3.5 h-3.5" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy Details</>}
              </button>
            </div>
            <div className="flex gap-3">
              <Link href="/dashboard" className="flex-1 py-3 text-center bg-secondary border border-border hover:bg-accent text-xs font-bold rounded-xl transition-colors">
                View Account Orders
              </Link>
              <button onClick={() => setDeliveredContent(null)}
                className="flex-1 py-3 text-white text-xs font-extrabold rounded-xl transition-all shadow-md bg-red-500 hover:bg-red-600 shadow-red-500/30">
                Continue Shopping
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Nepal Reviews & Ratings Modal ──────────────────────────────────── */}
      {reviewModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 relative border border-red-500/30 shadow-2xl max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setReviewModalProduct(null)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            ><X className="w-4 h-4" /></button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0 shadow-inner">
                <ProductIcon name={reviewModalProduct.name} size="md" />
              </div>
              <div>
                <h3 className="font-extrabold text-base text-foreground leading-tight">{reviewModalProduct.name}</h3>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <div className="flex text-amber-300">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="w-3.5 h-3.5 fill-amber-300 text-amber-300" />
                    ))}
                  </div>
                  <span className="text-xs font-bold text-foreground">{reviewsData.average_rating} ({reviewsData.total_reviews} reviews)</span>
                </div>
              </div>
            </div>

            {/* Add Review Form */}
            <form onSubmit={handleSubmitReview} className="mb-6 p-4 rounded-2xl bg-secondary/40 border border-border/60">
              <h4 className="text-xs font-extrabold text-foreground mb-2 flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-red-400" /> Leave Your Verified Review (Nepal)
              </h4>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs text-muted-foreground">Rating:</span>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setNewRating(star)}
                      className="p-1 text-amber-300 hover:scale-125 transition-transform"
                    >
                      <Star className={`w-4 h-4 ${star <= newRating ? 'fill-amber-300' : 'text-muted-foreground'}`} />
                    </button>
                  ))}
                </div>
              </div>

              <textarea
                placeholder="Share your experience with this item (activation speed, warranty, quality)..."
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                rows={3}
                className="w-full bg-background border border-border/80 rounded-xl p-3 text-xs focus:outline-none focus:border-red-500 transition-all resize-none mb-3"
              />

              <button
                type="submit"
                disabled={isSubmittingReview || !newComment.trim()}
                className="w-full py-2.5 rounded-xl font-bold text-xs bg-red-500 hover:bg-red-600 text-white disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 shadow-md shadow-red-500/20"
              >
                {isSubmittingReview ? "Publishing..." : (
                  <>
                    <span>Submit Verified Review</span>
                    <Star className="w-3 h-3 fill-amber-300 text-amber-300" />
                  </>
                )}
              </button>
            </form>

            {/* Reviews List */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Customer Feedback</h4>
              {isLoadingReviews ? (
                <p className="text-xs text-muted-foreground py-4 text-center">Loading reviews...</p>
              ) : reviewsData.reviews.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">No reviews yet. Be the first to leave feedback!</p>
              ) : (
                reviewsData.reviews.map(r => (
                  <div key={r.id} className="p-3.5 rounded-xl bg-secondary/30 border border-border/40">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-foreground">{r.user_name}</span>
                        {r.is_verified && (
                          <span className="text-[9px] font-extrabold px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                            ✓ Verified Buyer
                          </span>
                        )}
                      </div>
                      <div className="flex text-amber-300">
                        {[...Array(r.rating)].map((_, i) => (
                          <Star key={i} className="w-2.5 h-2.5 fill-amber-300" />
                        ))}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{r.comment}</p>
                    {r.created_at && (
                      <span className="text-[9px] text-muted-foreground/60 block mt-1">
                        {new Date(r.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
