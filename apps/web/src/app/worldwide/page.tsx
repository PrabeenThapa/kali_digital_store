"use client";

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/lib/api';
import { detectGeoLocation } from '@/lib/geo';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Search, CheckCircle2, Copy, Zap, Shield,
  Wallet, Tag, ArrowRight, X, AlertCircle, RefreshCw, Sparkles,
  Sun, Moon, Check, PackageCheck, PackageX, LayoutGrid,
  List, Bolt, Globe, Lock, HeartHandshake, ThumbsUp, Star,
  MessageSquare, ExternalLink, QrCode, CreditCard, FileText,
  Flame, Bot, Film, Palette, Briefcase, ShieldCheck, Code2, Mail
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
  balance: number;
}

interface PromoDiscount {
  code: string;
  discount_type: string;
  discount_value: number;
  discount_amount: number;
  final_price: number;
}

interface Review {
  id: string | number;
  user_name: string;
  rating: number;
  comment: string;
  created_at: string | null;
  is_verified?: boolean;
}

interface CryptoPaymentMethod {
  id: string;
  name: string;
  icon: string;
  badge: string;
  speed: string;
  address?: string;
  qr_url?: string;
  bot_url?: string;
  enabled?: boolean;
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

function getCategoryIcon(id: string, isSelected: boolean = false) {
  const cls = `w-4 h-4 shrink-0 transition-colors ${isSelected ? 'text-white' : 'text-red-400'}`;
  switch (id) {
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


export default function WorldwideStorePage() {
  const router = useRouter();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('featured');
  const [stockFilter, setStockFilter] = useState<'all' | 'in_stock' | 'out_of_stock'>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  // Checkout modal
  const [activeModalProduct, setActiveModalProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [promoCodeInput, setPromoCodeInput] = useState('');
  const [appliedPromo, setAppliedPromo] = useState<PromoDiscount | null>(null);
  const [isValidatingPromo, setIsValidatingPromo] = useState(false);
  const [promoError, setPromoError] = useState('');
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [orderError, setOrderError] = useState('');
  const [deliveredContent, setDeliveredContent] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);

  // Reviews & Upvotes State
  const [upvotes, setUpvotes] = useState<Record<string, { count: number; has_upvoted: boolean }>>({});
  const [reviewModalProduct, setReviewModalProduct] = useState<Product | null>(null);
  const [reviewsData, setReviewsData] = useState<{ average_rating: number; total_reviews: number; reviews: Review[] }>({
    average_rating: 5.0,
    total_reviews: 0,
    reviews: []
  });
  const [isLoadingReviews, setIsLoadingReviews] = useState(false);
  const [newRating, setNewRating] = useState(5);
  const [newComment, setNewComment] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Direct Checkout Top-Up State
  const [isDirectTopUpMode, setIsDirectTopUpMode] = useState(false);
  const [cryptoMethods, setCryptoMethods] = useState<CryptoPaymentMethod[]>([]);
  const [selectedCryptoMethod, setSelectedCryptoMethod] = useState<string>('cryptopay');
  const [directTxId, setDirectTxId] = useState('');
  const [isProcessingDirectPay, setIsProcessingDirectPay] = useState(false);
  const [directPaySuccessMsg, setDirectPaySuccessMsg] = useState('');
  const [copiedCryptoAddress, setCopiedCryptoAddress] = useState(false);

  const [isBlockedNepal, setIsBlockedNepal] = useState(false);

  useEffect(() => {
    // Check if visitor is from Nepal - if so, immediately redirect to /nepal
    detectGeoLocation().then(geo => {
      if (geo.is_nepal) {
        setIsBlockedNepal(true);
        localStorage.setItem('region', 'nepal');
        router.replace('/nepal');
      }
    });

    const savedTheme = (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
    if (savedTheme === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
    setTheme(savedTheme);

    fetchCatalog();
    fetchUser();
    fetchCryptoPaymentMethods();
  }, [router]);


  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
    if (next === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
  };

  const formatUsd = (usd: number = 0) => `$${usd.toFixed(2)}`;

  const fetchCatalog = async () => {
    setLoading(true);
    try {
      const res = await api.get('/catalog/products');
      const prods = res.data || [];
      setProducts(prods);

      // Fetch upvotes for each product in background
      prods.forEach(async (p: Product) => {
        try {
          const upRes = await api.get(`/catalog/products/${p.id}/upvotes`);
          setUpvotes(prev => ({
            ...prev,
            [p.id]: { count: upRes.data.upvotes_count, has_upvoted: upRes.data.has_upvoted }
          }));
        } catch { /* empty */ }
      });
    } catch { /* empty */ } finally { setLoading(false); }
  };

  const fetchUser = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return;
      const res = await api.get('/auth/me');
      setUser(res.data);
    } catch {
      localStorage.removeItem('token');
      setUser(null);
    }
  };

  const fetchCryptoPaymentMethods = async () => {
    try {
      const res = await api.get('/payments/crypto-methods');
      setCryptoMethods(res.data?.methods || []);
    } catch { /* empty */ }
  };

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
        const current = prev[productId] || { count: 10, has_upvoted: false };
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
    setIsDirectTopUpMode(false);
    setDirectTxId('');
    setDirectPaySuccessMsg('');
  };

  const getSubtotal = () => (activeModalProduct?.price ?? 0) * quantity;
  const getFinalTotal = () => {
    const sub = getSubtotal();
    if (!appliedPromo) return sub;
    return Math.max(0, sub - appliedPromo.discount_amount);
  };

  const handleValidatePromo = async () => {
    if (!promoCodeInput.trim()) return;
    setIsValidatingPromo(true);
    setPromoError('');
    try {
      const res = await api.post('/catalog/promocode/validate', {
        code: promoCodeInput.trim().toUpperCase(),
        amount: getSubtotal(),
        product_id: activeModalProduct?.id,
      });
      setAppliedPromo(res.data);
    } catch (err: any) {
      setAppliedPromo(null);
      setPromoError(err.response?.data?.detail || "Invalid promocode");
    } finally { setIsValidatingPromo(false); }
  };

  const handleCheckout = async () => {
    if (!activeModalProduct) return;
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }

    const finalCost = getFinalTotal();
    if (user && user.balance < finalCost) {
      setIsDirectTopUpMode(true);
      setOrderError(`Insufficient balance ($${user.balance.toFixed(2)}). Select a direct deposit method below to complete your purchase.`);
      return;
    }

    setIsSubmittingOrder(true);
    setOrderError('');
    try {
      const res = await api.post('/payments/purchase', {
        product_id: activeModalProduct.id,
        quantity,
        promocode: appliedPromo ? appliedPromo.code : null,
      });
      setDeliveredContent(res.data.delivered_content || res.data.message || "Order successful! Credentials sent to dashboard.");
      setActiveModalProduct(null);
      fetchUser();
      fetchCatalog();
    } catch (err: any) {
      const detail = err.response?.data?.detail || "Order failed. Please try again.";
      setOrderError(detail);
      if (detail.toLowerCase().includes('balance')) {
        setIsDirectTopUpMode(true);
      }
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  const handleDirectCryptoDeposit = async () => {
    const neededAmount = Math.max(1, getFinalTotal() - (user?.balance || 0));
    setIsProcessingDirectPay(true);
    try {
      if (selectedCryptoMethod === 'cryptopay') {
        const res = await api.post('/payments/deposit/cryptopay-init', {
          amount_usd: neededAmount
        });
        if (res.data.bot_pay_url) {
          window.open(res.data.bot_pay_url, '_blank');
          setDirectPaySuccessMsg("Opened CryptoPay invoice! Please complete payment in Telegram/Browser. Polling for confirmation...");
          
          // Poll for payment
          const checkInterval = setInterval(async () => {
            try {
              const chk = await api.post('/payments/deposit/cryptopay-check', {
                invoice_id: res.data.invoice_id
              });
              if (chk.data.status === 'paid') {
                clearInterval(checkInterval);
                setDirectPaySuccessMsg("Payment Confirmed! Processing your order now...");
                await fetchUser();
                setTimeout(() => handleCheckout(), 1000);
              }
            } catch { /* empty */ }
          }, 3000);
          setTimeout(() => clearInterval(checkInterval), 60000);
        }
      } else {
        if (!directTxId.trim()) {
          alert("Please enter the Transaction Hash / TxID after transferring funds.");
          setIsProcessingDirectPay(false);
          return;
        }
        await api.post('/payments/deposit/crypto-proof', {
          amount: neededAmount,
          currency: 'USDT',
          chain: selectedCryptoMethod.toUpperCase(),
          tx_hash: directTxId.trim(),
        });
        setDirectPaySuccessMsg("Deposit submission received! Admin & Bot relay are verifying your transaction.");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Deposit submission failed.");
    } finally {
      setIsProcessingDirectPay(false);
    }
  };

  const selectedMethodObj = cryptoMethods.find(m => m.id === selectedCryptoMethod) || cryptoMethods[0];
  const inStockCount = useMemo(() => products.filter(p => p.stock > 0).length, [products]);
  const outOfStockCount = useMemo(() => products.filter(p => p.stock === 0).length, [products]);

  if (isBlockedNepal) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center">
        <div className="w-12 h-12 border-4 border-red-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-bold text-red-400 mt-4 tracking-widest uppercase">॥ ॐ क्रीं कालिकायै नमः • REDIRECTING TO NEPAL STORE... ॥</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-red-600 selection:text-white">

      {/* Top Sacred Mantra Bar */}
      <div className="top-mantra-bar w-full bg-gradient-to-r from-red-950/80 via-red-900/40 to-red-950/80 border-b border-red-500/20 py-1.5 px-4 text-center">
        <p className="text-[10px] font-bold text-red-400 tracking-widest font-vedic uppercase flex items-center justify-center gap-2">
          <Shield className="w-3.5 h-3.5 text-red-400 shrink-0" />
          <span>॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥</span>
          <Shield className="w-3.5 h-3.5 text-red-400 shrink-0" />
        </p>
      </div>

      {/* Header */}
      <header className="sticky top-0 z-40 w-full glass border-b border-red-500/20 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="relative w-10 h-10 rounded-full p-0.5 bg-gradient-to-br from-red-500 to-rose-600 shadow-md shadow-red-500/40 overflow-hidden shrink-0 animate-kaali-pulse">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo.png" alt="Kali Digital Store" className="w-full h-full object-cover rounded-full" />
              </div>
              <div>
                <span className="font-black text-sm tracking-tight flex items-center gap-1.5 font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
                  KALI DIGITAL STORE
                  <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 font-bold">
                    GLOBAL
                  </span>
                </span>
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 -mt-0.5 font-semibold">
                  <Zap className="w-2.5 h-2.5 text-amber-400" />
                  <span>INSTANT DISPATCH • USD ($)</span>
                </span>
              </div>
            </Link>
          </div>

          <div className="flex-1 max-w-md hidden md:block">
            <div className="relative">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search AI, streaming, accounts, licenses..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full bg-secondary/50 border border-red-500/30 rounded-full pl-10 pr-4 py-2 text-xs focus:outline-none focus:border-red-500 transition-all font-medium"
              />
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Link
              href="/nepal"
              className="hidden sm:flex items-center gap-1.5 text-xs font-bold px-3.5 py-1.5 rounded-full border border-red-500/40 bg-red-500/10 text-red-400 hover:bg-red-500/25 transition-all shadow-sm"
            >
              <span className="px-1 py-0.2 rounded bg-red-500/20 text-[9px] font-mono font-bold text-red-300">NPR</span>
              <span>Nepal Store</span>
            </Link>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl bg-secondary/60 hover:bg-secondary border border-red-500/20 transition-colors"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </button>
            {user ? (
              <Link
                href="/dashboard"
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/30 text-xs font-bold transition-all shadow-sm"
              >
                <Wallet className="w-3.5 h-3.5" />
                <span>{formatUsd(user.balance)}</span>
              </Link>
            ) : (
              <Link
                href="/login"
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-extrabold text-xs shadow-md shadow-red-600/30 transition-all"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full">
        {/* Vedic Hero Banner */}
        <div className="hero-banner relative rounded-3xl overflow-hidden p-6 sm:p-10 mb-6 border border-red-500/30 bg-gradient-to-r from-red-950/60 via-red-900/30 to-background shadow-[0_0_50px_rgba(225,29,72,0.15)]">
          <div className="max-w-2xl">
            <span className="hero-badge text-[10px] font-black uppercase tracking-widest text-red-400 px-3 py-1 rounded-full bg-red-500/15 border border-red-500/30 inline-flex items-center gap-1.5 mb-3">
              <Shield className="w-3 h-3 text-red-400" />
              <span>दिव्य गति एवं अचूक सुरक्षा • 100% Automated Instant Delivery</span>
            </span>
            <h1 className="hero-title text-2xl sm:text-4xl lg:text-5xl font-black tracking-tight mb-2 font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
              KALI DIGITAL STORE
            </h1>
            <p className="hero-desc text-xs sm:text-sm text-muted-foreground leading-relaxed font-medium">
              Genuine ChatGPT Plus, Claude, Gemini, Canva Pro, JetBrains, VPNs, and Dev API tokens with instant cryptographic delivery and eternal warranty.
            </p>
          </div>
        </div>

        {/* ─── Sticky Frozen Category & Status Bar (Below Hero Banner) ─────────── */}
        <div className="sticky top-[62px] z-30 w-full bg-background/95 backdrop-blur-md border-b border-red-500/20 py-3 shadow-md shadow-black/10 -mx-4 sm:-mx-6 px-4 sm:px-6 mb-6">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
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

            {/* Tab 2: All Items */}
            <button
              onClick={() => setSelectedCategory('all')}
              className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all border flex items-center gap-1.5 ${
                selectedCategory === 'all'
                  ? 'bg-red-600 text-white border-red-500 shadow-[0_0_15px_rgba(225,29,72,0.5)] font-extrabold'
                  : 'bg-secondary/60 border-red-500/20 text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              {getCategoryIcon('all', selectedCategory === 'all')}
              <span>All Items ({products.length})</span>
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
                    isSelected ? 'bg-white/20 text-white' : 'bg-red-500/20 text-red-400 border border-red-500/30'
                  }`}>
                    {cat.purchases}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div className="flex items-center p-1 bg-secondary/60 border border-border/70 rounded-full text-xs font-bold">
            <button
              onClick={() => setStockFilter('all')}
              className={`px-3 py-1.5 rounded-full transition-all ${stockFilter === 'all' ? 'bg-red-600 text-white' : 'text-muted-foreground hover:text-foreground'}`}
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
            <span className="text-xs text-muted-foreground font-medium">{filteredProducts.length} items available in USD</span>
            <div className="flex items-center p-1 bg-secondary/60 border border-border/70 rounded-lg">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded transition-all ${viewMode === 'grid' ? 'bg-red-600 text-white' : 'text-muted-foreground hover:text-foreground'}`}
              ><LayoutGrid className="w-3.5 h-3.5" /></button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded transition-all ${viewMode === 'list' ? 'bg-red-600 text-white' : 'text-muted-foreground hover:text-foreground'}`}
              ><List className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        </div>

        {/* Product Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="glass-card rounded-2xl animate-pulse h-72" />
            ))}
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="text-center py-24 glass-card rounded-3xl">
            <div className="w-16 h-16 rounded-full bg-secondary/80 border border-border flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-bold text-foreground mb-2">No Products Found</h3>
            <p className="text-muted-foreground text-sm">Try adjusting your search or category filter.</p>
            <button
              onClick={() => { setSearchTerm(''); setSelectedCategory('all'); setStockFilter('all'); }}
              className="mt-6 px-6 py-2.5 rounded-full text-sm font-bold text-white bg-red-600 hover:bg-red-700 transition-all"
            >Clear Filters</button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filteredProducts.map(product => {
              const productUpvotes = upvotes[product.id] || { count: 18, has_upvoted: false };
              const { deliveryBadge, accBadge } = getProductBadges(product);
              return (
                <div
                  key={product.id}
                  className="glass-card rounded-2xl overflow-hidden flex flex-col group hover:-translate-y-1 hover:border-red-500/40 hover:shadow-[0_8px_30px_rgba(239,68,68,0.2)] transition-all duration-300 cursor-pointer relative justify-between"
                  onClick={() => handleOpenBuyModal(product)}
                >
                  <div className="relative p-6 pb-4 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/10 via-purple-600/10 to-transparent flex items-center justify-center mb-3 group-hover:scale-110 group-hover:border-red-500/40 transition-all duration-300 shadow-inner">
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

                    <h3 className="font-extrabold text-sm text-foreground line-clamp-2 mt-6 mb-1 group-hover:text-red-400 transition-colors">
                      {product.name}
                    </h3>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mb-3">
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
                      <span className="text-[10px] text-muted-foreground block">Global Price</span>
                      <span className="text-base font-black text-red-400">{formatUsd(product.price)}</span>
                    </div>
                    {product.stock === 0 ? (
                      <span className="px-3 py-1.5 rounded-xl text-xs font-bold text-red-400 bg-red-500/10 border border-red-500/30">
                        Out of Stock
                      </span>
                    ) : (
                      <button
                        onClick={() => handleOpenBuyModal(product)}
                        className="px-3.5 py-2 rounded-xl text-xs font-extrabold text-white bg-red-600 hover:bg-red-500 shadow-md shadow-red-600/20 flex items-center gap-1.5 transition-all group-hover:scale-105"
                      >
                        <Bolt className="w-3.5 h-3.5" /> Buy Now
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
                      {formatUsd(product.price)}
                    </div>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); handleOpenBuyModal(product); }}
                    disabled={product.stock === 0}
                    className="flex-shrink-0 px-3 py-1.5 text-white text-xs font-bold rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >Buy</button>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* ─── Worldwide Checkout & Direct Deposit Modal ───────────────────────── */}
      {activeModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 relative border border-primary/30 shadow-[0_0_60px_rgba(0,0,0,0.8)] max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setActiveModalProduct(null)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            ><X className="w-4 h-4" /></button>

            {/* Product header */}
            <div className="flex items-center gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl border border-primary/30 bg-primary/10 flex items-center justify-center flex-shrink-0 shadow-inner">
                <ProductIcon name={activeModalProduct.name} size="lg" />
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-primary mb-1 flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5" />
                  <span>Global Order Checkout</span>
                </div>
                <h2 className="text-base font-bold leading-snug">{activeModalProduct.name}</h2>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{activeModalProduct.description}</p>
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
                    className="w-full bg-secondary/40 border border-border/60 rounded-xl pl-9 pr-3 py-2 text-xs font-bold uppercase focus:outline-none focus:border-primary transition-all" />
                </div>
                <button onClick={handleValidatePromo} disabled={isValidatingPromo || !promoCodeInput.trim()}
                  className="px-4 py-2 bg-secondary text-secondary-foreground text-xs font-bold rounded-xl hover:bg-secondary/80 disabled:opacity-50">
                  {isValidatingPromo ? '...' : 'Apply'}
                </button>
              </div>
              {appliedPromo && (
                <div className="mt-2 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-400 font-medium">
                  <span>✓ Code <b>{appliedPromo.code}</b> applied!</span>
                  <span>−{formatUsd(appliedPromo.discount_amount)}</span>
                </div>
              )}
              {promoError && <p className="text-[11px] text-rose-400 mt-1">{promoError}</p>}
            </div>

            {/* Payment Method Selector & Toggle */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Payment Method</label>
                <button 
                  onClick={() => setIsDirectTopUpMode(!isDirectTopUpMode)}
                  className="text-[11px] font-bold text-primary hover:underline flex items-center gap-1"
                >
                  {isDirectTopUpMode ? '← Use Wallet Balance' : (
                    <span className="flex items-center gap-1">
                      <Zap className="w-3 h-3 text-amber-400" />
                      <span>Direct Crypto Deposit</span>
                    </span>
                  )}
                </button>
              </div>

              {!isDirectTopUpMode ? (
                <div className="p-3.5 rounded-xl border bg-primary/15 border-primary text-primary">
                  <div className="flex items-center justify-between">
                    <span className="font-black text-foreground text-xs flex items-center gap-1.5">
                      <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                      <span>USD Wallet Balance</span>
                    </span>
                    <span className="text-xs font-bold text-primary">{user ? formatUsd(user.balance) : '$0.00'}</span>
                  </div>
                  <span className="text-[11px] text-muted-foreground block mt-0.5">
                    {user && user.balance >= getFinalTotal() 
                      ? '✓ Sufficient balance for 1-click instant delivery' 
                      : `Needs +${formatUsd(Math.max(0, getFinalTotal() - (user?.balance || 0)))} — Top up below to complete.`}
                  </span>
                </div>
              ) : (
                /* DIRECT DEPOSIT TILES */
                <div className="space-y-3 p-4 rounded-2xl bg-secondary/40 border border-primary/30">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold text-foreground flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-primary" /> Direct Top-Up Needed: {formatUsd(Math.max(1, getFinalTotal() - (user?.balance || 0)))}
                    </span>
                    <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full">
                      Zero Fees
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {cryptoMethods.map(m => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setSelectedCryptoMethod(m.id)}
                        className={`p-2.5 rounded-xl border text-left transition-all ${
                          selectedCryptoMethod === m.id
                            ? 'bg-primary/20 border-primary text-foreground font-bold shadow-sm'
                            : 'bg-secondary/40 border-border/60 text-muted-foreground hover:bg-secondary'
                        }`}
                      >
                        <div className="text-xs font-bold text-foreground">{m.name}</div>
                        <div className="text-[10px] text-muted-foreground">{m.speed}</div>
                      </button>
                    ))}
                  </div>

                  {selectedMethodObj?.address && (
                    <div className="p-3 rounded-xl bg-background/60 border border-border/80 text-xs">
                      <div className="text-[10px] text-muted-foreground mb-1">Transfer Address ({selectedMethodObj.name}):</div>
                      <div className="font-mono text-[11px] text-primary break-all bg-black/40 p-2 rounded-lg flex items-center justify-between gap-2">
                        <span>{selectedMethodObj.address}</span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(selectedMethodObj.address || '');
                            setCopiedCryptoAddress(true);
                            setTimeout(() => setCopiedCryptoAddress(false), 2000);
                          }}
                          className="px-2 py-1 bg-primary/20 text-primary rounded hover:bg-primary/30 text-[10px] font-bold flex-shrink-0"
                        >
                          {copiedCryptoAddress ? 'Copied!' : 'Copy'}
                        </button>
                      </div>

                      <div className="mt-2.5">
                        <label className="text-[10px] text-muted-foreground block mb-1">Transaction Hash / TxID:</label>
                        <input
                          type="text"
                          placeholder="Paste blockchain TxID / Hash here..."
                          value={directTxId}
                          onChange={e => setDirectTxId(e.target.value)}
                          className="w-full bg-secondary/60 border border-border/60 rounded-lg px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
                        />
                      </div>
                    </div>
                  )}

                  {directPaySuccessMsg && (
                    <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-[11px] text-emerald-400 font-medium">
                      {directPaySuccessMsg}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={handleDirectCryptoDeposit}
                    disabled={isProcessingDirectPay}
                    className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs rounded-xl shadow-md transition-all flex items-center justify-center gap-1.5"
                  >
                    {isProcessingDirectPay ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CreditCard className="w-3.5 h-3.5" />}
                    {selectedCryptoMethod === 'cryptopay' ? 'Open CryptoPay & Auto-Verify' : 'Submit Proof & Credit Order'}
                  </button>
                </div>
              )}
            </div>

            {/* Price breakdown */}
            <div className="p-4 rounded-xl bg-secondary/30 border border-border/40 mb-4 space-y-2 text-xs">
              <div className="flex justify-between text-muted-foreground"><span>Unit Price</span><span>{formatUsd(activeModalProduct.price)}</span></div>
              <div className="flex justify-between text-muted-foreground"><span>Subtotal ({quantity}×)</span><span>{formatUsd(getSubtotal())}</span></div>
              {appliedPromo && (
                <div className="flex justify-between text-emerald-400 font-semibold"><span>Promocode Discount</span><span>−{formatUsd(appliedPromo.discount_amount)}</span></div>
              )}
              <div className="pt-2 border-t border-border/40 flex justify-between items-center text-sm font-extrabold">
                <span>Total Amount (USD)</span>
                <span className="text-lg font-black text-primary">{formatUsd(getFinalTotal())}</span>
              </div>
            </div>

            {orderError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2 font-medium">
                <AlertCircle className="w-4 h-4 shrink-0" /><span>{orderError}</span>
              </div>
            )}

            <button
              onClick={handleCheckout}
              disabled={isSubmittingOrder}
              className="w-full py-3.5 font-extrabold text-sm rounded-xl text-white bg-primary hover:bg-primary/90 shadow-primary/30 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg"
            >
              {isSubmittingOrder ? <><RefreshCw className="w-4 h-4 animate-spin" /> Processing Order...</>
                : <>Confirm & Complete Purchase {formatUsd(getFinalTotal())} <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        </div>
      )}

      {/* ─── Reviews & Ratings Modal ────────────────────────────────────────── */}
      {reviewModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 relative border border-primary/30 shadow-2xl max-h-[85vh] overflow-y-auto">
            <button
              onClick={() => setReviewModalProduct(null)}
              className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            ><X className="w-4 h-4" /></button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0 shadow-inner">
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
                <MessageSquare className="w-3.5 h-3.5 text-primary" /> Leave Your Verified Review
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
                className="w-full bg-background border border-border/80 rounded-xl p-3 text-xs focus:outline-none focus:border-primary transition-all resize-none mb-3"
              />

              <button
                type="submit"
                disabled={isSubmittingReview || !newComment.trim()}
                className="w-full py-2.5 rounded-xl font-bold text-xs bg-primary hover:bg-primary/90 text-white disabled:opacity-50 transition-all flex items-center justify-center gap-1.5"
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

      {/* Delivery Modal */}
      {deliveredContent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-lg rounded-3xl p-6 border border-emerald-500/30 shadow-[0_0_60px_rgba(34,197,94,0.2)]">
            <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h2 className="text-xl font-bold text-center mb-1">Order Processed! 🎉</h2>
            <p className="text-xs text-muted-foreground text-center mb-5">Your digital credentials have been generated.</p>
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
                className="flex-1 py-3 text-white text-xs font-extrabold rounded-xl transition-all shadow-md bg-primary hover:bg-primary/90 shadow-primary/30">
                Continue Shopping
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
