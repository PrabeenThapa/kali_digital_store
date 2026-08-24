"use client";

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Search, CheckCircle2, Copy, Zap, Shield,
  Wallet, Tag, ArrowRight, X, AlertCircle, RefreshCw, Sparkles,
  Sun, Moon, Check, PackageCheck, PackageX, LayoutGrid,
  List, Bolt, HeartHandshake, QrCode, Globe, Mail,
  UploadCloud, ImageIcon, Camera, Trash2, ThumbsUp, Star, MessageSquare,
  Flame, Bot, Film, Palette, Briefcase, ShieldCheck, Code2
} from 'lucide-react';

interface Product {
  id: string;
  raw_id: number;
  name: string;
  description: string;
  price: number;
  stock: number;
  image?: string;
  type: string;
  source?: string;
  category_id?: number;
  is_instant?: boolean;
  is_featured?: boolean;
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
  { id: 'ai',          label: 'AI & ChatBots',    purchases: '1,420+ Purchases', keywords: ['chatgpt','gpt','claude','gemini','grok','cursor','manus','deepseek','kiro','lovable','codex','openai','perplexity','copilot','mistral','llama'] },
  { id: 'streaming',   label: 'Streaming',         purchases: '890+ Purchases',   keywords: ['netflix','spotify','youtube','amazon','prime','disney','hulu','twitch','crunchyroll','peacock'] },
  { id: 'creative',    label: 'Creative Tools',    purchases: '640+ Purchases',   keywords: ['adobe','canva','capcut','meitu','figma','picsart','heygen','pixverse','suno','udio','runway','midjourney','dalle','elevenlabs','gamma','leonardo','openart'] },
  { id: 'productivity',label: 'Productivity',      purchases: '520+ Purchases',   keywords: ['notion','linkedin','microsoft','office','quillbot','grammarly','wispr','supercut','chatprd','n8n','zapier','make'] },
  { id: 'vpn',         label: 'VPN & Security',    purchases: '380+ Purchases',   keywords: ['vpn','nordvpn','surfshark','expressvpn','proton','hma','avira'] },
  { id: 'dev',         label: 'Dev Tools',         purchases: '290+ Purchases',   keywords: ['replit','railway','supabase','warp','posthog','factory','linear','gumloop','granola','magic patterns'] },
  { id: 'email',       label: 'Email & Accounts',  purchases: '410+ Purchases',   keywords: ['gmail','hotmail','mail','email','inbox'] },
  { id: 'other',       label: 'Others',            purchases: '180+ Purchases',   keywords: [] },
];

function getCategoryIcon(id: string, isSelected: boolean = false) {
  const cls = `w-4 h-4 shrink-0 transition-colors ${isSelected ? 'text-white' : 'text-red-500'}`;
  switch (id) {
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

function getProductEmoji(name: string): string {
  const n = name.toLowerCase();
  if (n.includes('chatgpt') || n.includes('gpt')) return '🤖';
  if (n.includes('claude')) return '🧠';
  if (n.includes('gemini')) return '💎';
  if (n.includes('grok')) return '⚡';
  if (n.includes('cursor')) return '🖱️';
  if (n.includes('manus')) return '🦾';
  if (n.includes('deepseek')) return '🔍';
  if (n.includes('netflix')) return '🎬';
  if (n.includes('spotify')) return '🎵';
  if (n.includes('youtube')) return '📺';
  if (n.includes('adobe')) return '🎨';
  if (n.includes('canva')) return '🖌️';
  if (n.includes('capcut')) return '🎞️';
  if (n.includes('vpn')) return '🔒';
  if (n.includes('notion')) return '📝';
  return '✨';
}

export default function NepalStorePage() {
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [stockFilter, setStockFilter] = useState<'all' | 'in_stock' | 'out_of_stock'>('all');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

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
  }, []);

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

  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      const matchSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchCat = selectedCategory === 'all' || getAutoCategory(p.name) === selectedCategory;
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
          <span>🔱</span>
          <span>॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥</span>
          <span>🔱</span>
        </p>
      </div>

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
                🇳🇵 NEPAL PORTAL (NPR)
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
              <span>🇳🇵 Nepal (NPR)</span>
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
        <div className="w-full bg-gradient-to-r from-amber-950/90 via-red-950/80 to-amber-950/90 border-b border-amber-500/40 p-4 sm:p-5 text-center animate-in slide-in-from-top-4 duration-300 relative z-30">
          <div className="max-w-4xl mx-auto flex items-center justify-center gap-3 text-left">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 text-amber-400 font-extrabold text-xl shadow-lg shadow-amber-500/10">
              🚀
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  🇳🇵 NEPAL STORE • COMING SOON
                </span>
              </div>
              <p className="text-xs font-semibold text-amber-100/90 mt-1 leading-relaxed">
                {nepalQrData.coming_soon_text || "🇳🇵 Nepal Store Direct Local Payment Gateway & Catalog Expansion is Coming Soon! Stay tuned as we roll out instant eSewa & Khalti automated API verification."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ─── Nepal Exclusive Hero Banner ───────────────────────────────── */}
      <section className="hero-banner relative overflow-hidden border-b border-red-500/20 bg-gradient-to-r from-red-950/60 via-red-900/30 to-background shadow-[0_0_50px_rgba(225,29,72,0.15)]">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-12 md:py-16 text-center">
          <div className="hero-badge inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-red-500/40 bg-red-500/10 text-red-400 text-xs font-black mb-4 shadow-md uppercase tracking-wider">
            <span>🔱</span>
            <span>नेपाल आधिकारिक डिजिटल स्टोर • eSewa, Fonepay & Khalti Direct</span>
            <span>🔱</span>
          </div>
          <h1 className="hero-title text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-tight mb-4 font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
            KALI DIGITAL STORE NEPAL<br />
            <span className="text-2xl sm:text-4xl text-red-500">⚡ क्षणभर में प्राप्ति • काल-चक्र वॉरंटी</span>
          </h1>
          <p className="hero-desc text-muted-foreground max-w-xl mx-auto mb-7 text-xs sm:text-sm font-medium">
            ChatGPT Plus, Gemini Pro, Claude 3.7, Canva Pro, Netflix, VPNs & Dev API Keys. Pay seamlessly in Nepali Rupees (NPR) with instant credentials dispatch.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground mb-6 font-semibold">
            <div className="flex items-center gap-1.5"><QrCode className="w-3.5 h-3.5 text-red-400" /> eSewa / Fonepay Direct QR</div>
            <div className="flex items-center gap-1.5"><Zap className="w-3.5 h-3.5 text-amber-400" /> Instant Activation</div>
            <div className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-red-400" /> 100% Replacement Warranty</div>
            <div className="flex items-center gap-1.5"><HeartHandshake className="w-3.5 h-3.5 text-emerald-400" /> 24/7 Nepali Live Support</div>
          </div>

          {/* Mobile search */}
          <div className="flex md:hidden relative max-w-md mx-auto">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search in NPR catalog..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-secondary/60 border border-red-500/30 rounded-full pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-red-500 transition-all font-medium"
            />
          </div>
        </div>
      </section>

      {/* ─── Sticky Frozen Category & Status Bar ────────────────────────── */}
      <div className="sticky top-[62px] z-30 w-full bg-background/95 backdrop-blur-md border-b border-red-500/20 py-3 shadow-md shadow-black/10">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
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
      </div>

      {/* ─── Main Catalog Content ───────────────────────────────────────── */}
      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">

        {/* Filters row */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
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
              return (
                <div
                  key={product.id}
                  className="glass-card rounded-2xl overflow-hidden flex flex-col group hover:-translate-y-1 hover:border-red-500/40 hover:shadow-[0_8px_30px_rgba(239,68,68,0.2)] transition-all duration-300 cursor-pointer relative justify-between"
                  onClick={() => handleOpenBuyModal(product)}
                >
                  <div className="relative p-6 pb-4 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/20 to-amber-500/20 flex items-center justify-center text-4xl mb-3 group-hover:scale-110 transition-transform duration-300">
                      {getProductEmoji(product.name)}
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

                    <div className="absolute top-3 left-3 flex items-center gap-1">
                      {product.is_featured && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          ⭐ Featured
                        </span>
                      )}
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${product.is_instant ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25' : 'bg-blue-500/15 text-blue-400 border border-blue-500/25'}`}>
                        {product.is_instant ? '⚡ Instant' : '📋 Manual'}
                      </span>
                    </div>

                    <h3 className="font-bold text-sm text-foreground mb-1 line-clamp-2 text-center group-hover:text-red-400 transition-colors leading-snug mt-3">
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
                        Out of Stock
                      </span>
                    ) : (
                      <button
                        onClick={e => { e.stopPropagation(); handleOpenBuyModal(product); }}
                        className="px-4 py-2 text-white text-xs font-extrabold rounded-xl bg-red-500 hover:bg-red-600 shadow-red-500/20 transition-all flex items-center gap-1 shadow-sm"
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
            {filteredProducts.map(product => (
              <div
                key={product.id}
                className="glass-card rounded-xl px-4 py-3 flex items-center gap-4 hover:border-red-500/40 transition-all group cursor-pointer"
                onClick={() => handleOpenBuyModal(product)}
              >
                <div className="w-10 h-10 rounded-xl border border-red-500/20 bg-gradient-to-br from-red-500/20 to-amber-500/20 flex items-center justify-center text-2xl flex-shrink-0">
                  {getProductEmoji(product.name)}
                </div>
                <div className="flex-grow min-w-0">
                  <div className="font-bold text-sm text-foreground group-hover:text-red-400 transition-colors truncate">{product.name}</div>
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
            ))}
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
              <div className="w-14 h-14 rounded-2xl border border-red-500/30 bg-red-500/20 flex items-center justify-center text-3xl flex-shrink-0">
                {getProductEmoji(activeModalProduct.name)}
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-1">
                  🇳🇵 Nepal Order Checkout
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
              <p className="text-[10px] text-muted-foreground mt-1">
                ✉️ Digital keys and account credentials will be automatically dispatched to this email.
              </p>
            </div>

            {/* Payment Method Selector */}
            <div className="mb-4">
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Payment Method (Nepal)</label>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={() => { setPaymentMethod('nepal_qr'); fetchNepalQrDetails(); }}
                  className={`p-3 rounded-xl border text-left text-xs font-bold transition-all ${paymentMethod === 'nepal_qr' ? 'bg-red-500/20 border-red-500 text-red-300 shadow-sm' : 'bg-secondary/40 border-border/60 hover:bg-secondary text-muted-foreground'}`}>
                  <span className="block font-black text-foreground">🇳🇵 eSewa / Fonepay</span>
                  <span className="text-[10px] font-normal text-muted-foreground">Scan QR Code directly</span>
                </button>
                <button type="button" onClick={() => setPaymentMethod('balance')}
                  className={`p-3 rounded-xl border text-left text-xs font-bold transition-all ${paymentMethod === 'balance' ? 'bg-red-500/20 border-red-500 text-red-300 shadow-sm' : 'bg-secondary/40 border-border/60 hover:bg-secondary text-muted-foreground'}`}>
                  <span className="block font-black text-foreground">💰 NPR Wallet</span>
                  <span className="text-[10px] font-normal text-muted-foreground">{user ? `Balance: ${formatNpr(user.balance)}` : 'Instant deduction'}</span>
                </button>
              </div>
            </div>

            {/* QR Details */}
            {paymentMethod === 'nepal_qr' && (
              <div className="mb-4 p-4 rounded-2xl bg-secondary/40 border border-red-500/30 space-y-3">
                <div className="text-center">
                  <div className="text-[11px] font-extrabold uppercase text-red-400 mb-1.5 tracking-wider">
                    {nepalQrData?.title || '🇳🇵 Direct eSewa / Khalti / Fonepay QR'}
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
              <div className="w-12 h-12 rounded-xl bg-red-500/20 flex items-center justify-center text-2xl">
                {getProductEmoji(reviewModalProduct.name)}
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
                className="w-full py-2 bg-red-500 hover:bg-red-600 text-white font-extrabold text-xs rounded-xl shadow transition-all disabled:opacity-50"
              >
                {isSubmittingReview ? "Publishing..." : "Submit Review ⭐"}
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
