"use client";

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useGeoLocation } from '@/lib/geo';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  Wallet, Package, Clock, LogOut, CreditCard, Send, 
  ShieldCheck, X, CheckCircle2, Copy, RefreshCw, Sparkles,
  Sun, Moon, ArrowLeft, Bolt, QrCode, Check, Globe,
  UploadCloud, Trash2, ExternalLink, Users, MessageCircle,
  Headphones, CheckCheck
} from 'lucide-react';


interface UserProfile {
  id: number;
  email?: string;
  username: string;
  first_name: string;
  balance: number;
  crypto_balance: number;
  referral_balance: number;
  is_admin?: boolean;
  customers_served?: number;
  total_deliveries?: number;
  satisfaction_rate?: string;
}

interface ChatMessage {
  id: number;
  sender: string;
  sender_name?: string;
  message: string;
  created_at: string;
}

interface Purchase {
  id: string | number;
  raw_id?: number;
  date: string | null;
  amount: number;
  description: string;
  status?: string;
  status_label?: string;
  delivered_content: string | null;
  unique_id?: string;
  type?: string;
}

interface CryptoPaymentMethod {
  id: string;
  name: string;
  icon: string;
  badge: string;
  description: string;
  type: 'invoice' | 'onchain' | 'uid_transfer' | 'stars';
  network?: string;
  wallet_address?: string;
  account_id?: string;
  qr_url?: string;
  bot_url?: string;
  enabled?: boolean;
}

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'purchases' | 'support'>('overview');
  
  // Live Chat Support state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [supportLinks, setSupportLinks] = useState<{ bot_url?: string; community_channel?: string }>({});

  // Top Up Modal State
  const [isTopUpOpen, setIsTopUpOpen] = useState(false);
  const [topUpAmount, setTopUpAmount] = useState("10");
  const [nepalDepositNpr, setNepalDepositNpr] = useState("1500");
  const [nepalTxId, setNepalTxId] = useState("");
  const [proofImage, setProofImage] = useState<string | null>(null);
  const [proofFileName, setProofFileName] = useState<string>('');
  const [nepalQrData, setNepalQrData] = useState<any>(null);
  const [nepalDepositSuccess, setNepalDepositSuccess] = useState(false);
  const [invoiceUrl, setInvoiceUrl] = useState<string | null>(null);
  const [isGeneratingInvoice, setIsGeneratingInvoice] = useState(false);
  const [copiedKeyId, setCopiedKeyId] = useState<string | number | null>(null);

  // Worldwide / Crypto Methods matching Telegram Bot
  const [cryptoMethods, setCryptoMethods] = useState<CryptoPaymentMethod[]>([]);
  const [selectedCryptoId, setSelectedCryptoId] = useState<string>('cryptopay');
  const [cryptoTxHash, setCryptoTxHash] = useState<string>('');
  const [cryptoDepositSuccess, setCryptoDepositSuccess] = useState<boolean>(false);
  const [cryptoDepositMsg, setCryptoDepositMsg] = useState<string>('');
  const [copiedAddress, setCopiedAddress] = useState<boolean>(false);

  // CryptoPay invoice polling state
  const [cryptoInvoiceId, setCryptoInvoiceId] = useState<string | null>(null);
  const [isCryptoPolling, setIsCryptoPolling] = useState(false);
  const cryptoPollingRef = typeof window !== 'undefined' ? { current: null as ReturnType<typeof setInterval> | null } : { current: null };

  // Bybit Pay flow state (mirrors Telegram bot exactly)
  const [bybitInit, setBybitInit] = useState<{
    bybit_uid: string; unique_amount: number; credited_amount: number;
    created_at_ms: number; payment_uuid: string; payment_id: number;
  } | null>(null);
  const [bybitStep, setBybitStep] = useState<'idle' | 'showing_details' | 'verifying' | 'success' | 'pending'>('idle');
  const [bybitTxId, setBybitTxId] = useState('');

  // Binance Pay flow state (mirrors Telegram bot exactly)
  const [binanceInit, setBinanceInit] = useState<{
    binance_pay_id: string; unique_amount: number; credited_amount: number;
    remark_code: string; created_at_ms: number; payment_uuid: string; payment_id: number;
  } | null>(null);
  const [binanceStep, setBinanceStep] = useState<'idle' | 'showing_details' | 'verifying' | 'success' | 'pending'>('idle');

  const geo = useGeoLocation();
  // Region state: 'worldwide' | 'nepal'
  const [region, setRegion] = useState<'worldwide' | 'nepal'>('worldwide');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  useEffect(() => {
    fetchDashboardData();
    fetchNepalQrDetails();

    // If geo detects Nepal, strictly lock region to Nepal
    if (geo.is_nepal) {
      setRegion('nepal');
      localStorage.setItem('region', 'nepal');
    } else {
      const savedRegion = (localStorage.getItem('region') as 'worldwide' | 'nepal') || 'worldwide';
      setRegion(savedRegion);
      fetchCryptoMethods();
    }

    // Initialize Theme
    const savedTheme = (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
    setTheme(savedTheme);
    if (savedTheme === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
  }, [geo.is_nepal]);

  // Poll chat messages in real time when support tab is active
  useEffect(() => {
    if (activeTab === 'support') {
      fetchChatMessages();
      fetchSupportLinks();
      const interval = setInterval(fetchChatMessages, 3500);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
    if (next === 'light') document.documentElement.classList.add('light-theme');
    else document.documentElement.classList.remove('light-theme');
  };

  const isNepal = region === 'nepal' || geo.is_nepal;
  const storePath = isNepal ? '/nepal' : '/worldwide';


  const formatPrice = (usdPrice: number = 0) => {
    if (isNepal) {
      const npr = Math.round(usdPrice * 300);
      return `NPR ${npr.toLocaleString()}`;
    }
    return `$${usdPrice.toFixed(2)}`;
  };

  const fetchNepalQrDetails = async () => {
    try {
      const res = await api.get('/payments/nepal-qr');
      setNepalQrData(res.data);
    } catch { /* empty */ }
  };

  const fetchCryptoMethods = async () => {
    try {
      const res = await api.get('/payments/crypto-methods');
      if (res.data) setCryptoMethods(res.data);
    } catch { /* empty */ }
  };

  // Featured Products
  const [featuredProducts, setFeaturedProducts] = useState<any[]>([]);

  const fetchDashboardData = async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }
    
    try {
      const [profileRes, purchasesRes, featuredRes] = await Promise.all([
        api.get('/user/me'),
        api.get('/user/purchases').catch(() => ({ data: [] })),
        api.get('/catalog/featured').catch(() => ({ data: [] })),
      ]);
      
      setProfile(profileRes.data);
      setPurchases(purchasesRes.data || []);
      setFeaturedProducts(featuredRes.data || []);
    } catch (error) {
      console.error("Failed to load dashboard", error);
      router.push('/login');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    router.push('/login');
  };

  const handleProofImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert("Payment screenshot size must be under 5MB.");
      return;
    }
    setProofFileName(file.name);
    const reader = new FileReader();
    reader.onloadend = () => {
      setProofImage(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedAddress(true);
    setTimeout(() => setCopiedAddress(false), 2000);
  };

  const handleCryptoDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const selected = cryptoMethods.find(m => m.id === selectedCryptoId);
    const amount = parseFloat(topUpAmount) || 10;

    if (selected?.type === 'invoice') {
      setIsGeneratingInvoice(true);
      try {
        const res = await api.post('/payments/deposit/cryptopay', { amount, asset: "USDT" });
        if (res.data?.invoice_url) {
          setInvoiceUrl(res.data.invoice_url);
          // Start polling if we have an invoice_id
          if (res.data?.invoice_id) {
            setCryptoInvoiceId(String(res.data.invoice_id));
            startCryptoPolling(String(res.data.invoice_id));
          }
        } else {
          alert("Failed to generate deposit link. Please try again.");
        }
      } catch (err: any) {
        alert(err.response?.data?.detail || "Failed to generate deposit link.");
      } finally {
        setIsGeneratingInvoice(false);
      }
    } else if (selected?.type === 'uid_transfer' && selected.id === 'bybit') {
      // Bybit: call init first
      await handleBybitInit(amount);
    } else if (selected?.type === 'uid_transfer' && selected.id === 'binance') {
      // Binance: call init first
      await handleBinanceInit(amount);
    } else if (selected?.type === 'stars') {
      window.open(selected.bot_url || "https://t.me/kali_digital_store_bot", "_blank");
    } else {
      if (!cryptoTxHash.trim()) {
        alert("Please provide the transaction hash or transfer reference ID.");
        return;
      }
      setIsGeneratingInvoice(true);
      try {
        const res = await api.post('/payments/deposit/onchain-submit', {
          network: selected?.network || selectedCryptoId.toUpperCase(),
          tx_hash: cryptoTxHash.trim(),
          amount_usd: amount,
          proof_image: proofImage,
        });
        if (res.data?.status === 'success') {
          setCryptoDepositSuccess(true);
          setCryptoDepositMsg(res.data.message || "Deposit submitted successfully!");
          setCryptoTxHash('');
          setProofImage(null);
          setProofFileName('');
          setTimeout(() => {
            setCryptoDepositSuccess(false);
            setIsTopUpOpen(false);
            fetchDashboardData();
          }, 3500);
        }
      } catch (err: any) {
        alert(err.response?.data?.detail || "Failed to submit crypto deposit.");
      } finally {
        setIsGeneratingInvoice(false);
      }
    }
  };

  // CryptoPay polling: check every 4s until paid or 15 min elapsed
  const startCryptoPolling = (invoiceId: string) => {
    setIsCryptoPolling(true);
    let attempts = 0;
    const maxAttempts = 225; // 15 min at 4s intervals
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(interval);
        setIsCryptoPolling(false);
        return;
      }
      try {
        const res = await api.get(`/payments/deposit/cryptopay-check?invoice_id=${invoiceId}`);
        if (res.data?.paid) {
          clearInterval(interval);
          setIsCryptoPolling(false);
          setInvoiceUrl(null);
          setCryptoInvoiceId(null);
          setCryptoDepositSuccess(true);
          setCryptoDepositMsg(`✅ Payment confirmed! $${res.data.amount?.toFixed(2)} USDT has been added to your balance.`);
          fetchDashboardData();
          setTimeout(() => {
            setCryptoDepositSuccess(false);
            setIsTopUpOpen(false);
          }, 4000);
        }
      } catch { /* poll silently */ }
    }, 4000);
  };

  // Bybit Pay: Step 1 — Initialize (get UID + unique amount)
  const handleBybitInit = async (amount: number) => {
    setIsGeneratingInvoice(true);
    try {
      const res = await api.post('/payments/deposit/bybit-init', { amount_usd: amount });
      if (res.data?.bybit_uid) {
        setBybitInit(res.data);
        setBybitStep('showing_details');
        setBybitTxId('');
      } else {
        alert("Bybit Pay is not configured yet. Please contact support.");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to initialize Bybit payment.");
    } finally {
      setIsGeneratingInvoice(false);
    }
  };

  // Bybit Pay: Step 2 — Verify (submit Transfer ID + auto-verify)
  const handleBybitVerify = async () => {
    if (!bybitInit) return;
    setBybitStep('verifying');
    try {
      const res = await api.post('/payments/deposit/bybit-verify', {
        payment_uuid: bybitInit.payment_uuid,
        unique_amount: bybitInit.unique_amount,
        credited_amount: bybitInit.credited_amount,
        created_at_ms: bybitInit.created_at_ms,
        tx_id: bybitTxId.trim() || null,
        proof_image: proofImage,
      });
      if (res.data?.verified) {
        setBybitStep('success');
        setCryptoDepositMsg(res.data.message || "Balance credited!");
        fetchDashboardData();
        setTimeout(() => {
          setBybitStep('idle'); setBybitInit(null); setIsTopUpOpen(false);
          setCryptoDepositSuccess(false);
        }, 4000);
      } else {
        setBybitStep('pending');
        setCryptoDepositMsg(res.data?.message || "Submitted for admin review.");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to verify Bybit transfer.");
      setBybitStep('showing_details');
    }
  };

  // Binance Pay: Step 1 — Initialize (get Pay ID + unique amount + remark code)
  const handleBinanceInit = async (amount: number) => {
    setIsGeneratingInvoice(true);
    try {
      const res = await api.post('/payments/deposit/binance-init', { amount_usd: amount });
      if (res.data?.binance_pay_id) {
        setBinanceInit(res.data);
        setBinanceStep('showing_details');
      } else {
        alert("Binance Pay is not configured yet. Please contact support.");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to initialize Binance payment.");
    } finally {
      setIsGeneratingInvoice(false);
    }
  };

  // Binance Pay: Step 2 — Verify (auto-detect via remark code)
  const handleBinanceVerify = async () => {
    if (!binanceInit) return;
    setBinanceStep('verifying');
    try {
      const res = await api.post('/payments/deposit/binance-verify', {
        payment_uuid: binanceInit.payment_uuid,
        unique_amount: binanceInit.unique_amount,
        credited_amount: binanceInit.credited_amount,
        remark_code: binanceInit.remark_code,
        created_at_ms: binanceInit.created_at_ms,
        proof_image: proofImage,
      });
      if (res.data?.verified) {
        setBinanceStep('success');
        setCryptoDepositMsg(res.data.message || "Balance credited!");
        fetchDashboardData();
        setTimeout(() => {
          setBinanceStep('idle'); setBinanceInit(null); setIsTopUpOpen(false);
          setCryptoDepositSuccess(false);
        }, 4000);
      } else {
        setBinanceStep('pending');
        setCryptoDepositMsg(res.data?.message || "Submitted for admin review.");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to verify Binance transfer.");
      setBinanceStep('showing_details');
    }
  };

  const handleNepalDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nepalTxId.trim() || !nepalDepositNpr) {
      alert("Please provide the transaction reference ID and deposit amount.");
      return;
    }
    setIsGeneratingInvoice(true);
    const npr = parseFloat(nepalDepositNpr);
    const usd = npr / 300;
    try {
      const res = await api.post('/payments/nepal-submit', {
        tx_id: nepalTxId.trim(),
        amount_npr: npr,
        amount_usd: usd,
        product_id: null,
        customer_email: profile?.email || null,
        proof_image: proofImage,
        note: `Manual Wallet Deposit: NPR ${npr.toLocaleString()} | Customer: ${profile?.email || 'Registered User'}`,
      });
      if (res.data?.status === 'success') {
        setNepalDepositSuccess(true);
        setNepalTxId('');
        setProofImage(null);
        setProofFileName('');
        setTimeout(() => {
          setNepalDepositSuccess(false);
          setIsTopUpOpen(false);
          fetchDashboardData();
        }, 3500);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to submit deposit transaction.");
    } finally {
      setIsGeneratingInvoice(false);
    }
  };

  const fetchChatMessages = async () => {
    try {
      const res = await api.get('/support/messages');
      if (res.data) setChatMessages(res.data);
    } catch { /* empty */ }
  };

  const fetchSupportLinks = async () => {
    try {
      const res = await api.get('/support/links');
      if (res.data) setSupportLinks(res.data);
    } catch { /* empty */ }
  };

  const sendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isSendingChat) return;
    const msg = chatInput.trim();
    setChatInput("");
    setIsSendingChat(true);

    const tempId = Date.now();
    const optimisticMsg: ChatMessage = {
      id: tempId,
      sender: "user",
      sender_name: "You",
      message: msg,
      created_at: new Date().toISOString(),
    };
    setChatMessages(prev => [...prev, optimisticMsg]);

    try {
      const res = await api.post('/support/send', { message: msg });
      if (res.data?.id) {
        setChatMessages(prev => prev.map(m => m.id === tempId ? res.data : m));
      }
    } catch {
      alert("Failed to send chat message. Please try again.");
    } finally {
      setIsSendingChat(false);
    }
  };

  const copyDeliveredKey = (id: string | number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKeyId(id);
    setTimeout(() => setCopiedKeyId(null), 2500);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row selection:bg-red-600 selection:text-white">
      {/* Sidebar */}
      <aside className="w-full md:w-64 glass border-r border-red-500/20 md:h-screen sticky top-0 flex flex-col z-30">
        <div className="p-6">
          {/* Maa Kaali Logo Branding */}
          <Link href={storePath} className="flex items-center gap-3 mb-2 group">
            <div className="relative w-10 h-10 rounded-full p-0.5 bg-gradient-to-br from-red-500 to-rose-600 shadow-md shadow-red-500/40 overflow-hidden shrink-0 animate-kaali-pulse">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.png" alt="Kali Digital Store" className="w-full h-full object-cover rounded-full" />
            </div>
            <div>
              <span className="font-black text-sm tracking-tight font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
                KALI STORE
              </span>
              <span className="text-[9px] text-red-400 font-bold block -mt-0.5 tracking-wider uppercase">
                ॥ दिव्य शक्ति ॥
              </span>
            </div>
          </Link>
          
          {/* Back to Store */}
          <Link href={storePath} className="flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-red-400 transition-colors mb-4 group">
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            Back to {isNepal ? 'Nepal Store' : 'Store'}
          </Link>

          {/* Region Badge & Switch */}
          <div className="flex items-center justify-between p-2 rounded-2xl bg-card/80 border border-red-500/20 text-xs font-bold mb-5">
            <span className="flex items-center gap-1.5 text-foreground">
              {isNepal ? '🇳🇵 Nepal (NPR)' : '🌐 Worldwide (USD)'}
            </span>
            {!geo.is_nepal && (
              <Link href="/" className="text-[11px] text-red-400 hover:underline">
                Change
              </Link>
            )}
          </div>

          
          <div className="flex items-center gap-3 mb-6 p-3 rounded-2xl bg-card/60 border border-red-500/20">
            <div className={`w-10 h-10 rounded-xl border flex items-center justify-center font-black text-base ${isNepal ? 'bg-red-500/20 border-red-500/30 text-red-400' : 'bg-red-600/20 border-red-600/40 text-red-400'}`}>
              {profile?.first_name?.charAt(0) || profile?.username?.charAt(0) || '🔱'}
            </div>
            <div className="overflow-hidden">
              <p className="font-bold text-xs truncate">{profile?.first_name || profile?.username}</p>
              <p className="text-[10px] text-muted-foreground font-mono mt-0.5">ID: #{profile?.id}</p>
            </div>
          </div>
          
          <nav className="space-y-2">
            <button 
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-xs font-bold ${
                activeTab === 'overview' 
                  ? isNepal ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.35)]' : 'bg-primary text-primary-foreground shadow-[0_0_15px_rgba(99,102,241,0.35)]' 
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              }`}
            >
              <Wallet className="w-4 h-4" /> Wallet & Overview
            </button>

            <button 
              onClick={() => setActiveTab('purchases')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-xs font-bold ${
                activeTab === 'purchases' 
                  ? isNepal ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.35)]' : 'bg-primary text-primary-foreground shadow-[0_0_15px_rgba(99,102,241,0.35)]' 
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              }`}
            >
              <Package className="w-4 h-4" /> My Purchases ({purchases.length})
            </button>

            <button 
              onClick={() => setActiveTab('support')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-xs font-bold ${
                activeTab === 'support' 
                  ? isNepal ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.35)]' : 'bg-primary text-primary-foreground shadow-[0_0_15px_rgba(99,102,241,0.35)]' 
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              }`}
            >
              <Send className="w-4 h-4" /> 24/7 Support
            </button>

            <Link
              href={storePath}
              className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-xs font-bold bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 border border-emerald-500/30 mt-4"
            >
              <Sparkles className="w-4 h-4 text-emerald-400" /> Store Catalog
            </Link>

            {profile?.is_admin && (
              <Link
                href="/admin"
                className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all text-xs font-bold bg-purple-500/15 text-purple-300 hover:bg-purple-500/25 border border-purple-500/30 mt-2"
              >
                <ShieldCheck className="w-4 h-4 text-purple-400" /> Admin Control
              </Link>
            )}
          </nav>
        </div>
        
        <div className="mt-auto p-6 border-t border-border/40 space-y-2">
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-colors text-xs font-bold text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            {theme === 'dark'
              ? <><Sun className="w-4 h-4 text-amber-400" /> Switch to Light Mode</>
              : <><Moon className="w-4 h-4 text-indigo-400" /> Switch to Dark Mode</>}
          </button>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-rose-400 hover:bg-rose-500/10 rounded-xl transition-colors text-xs font-bold"
          >
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 md:p-12 overflow-y-auto max-w-5xl">
        {activeTab === 'overview' && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Top Vedic Mantra Banner */}
            <div className="p-3 rounded-2xl bg-red-950/40 border border-red-500/30 flex items-center justify-between gap-3 text-red-400">
              <div className="flex items-center gap-2 text-xs font-black font-vedic tracking-wider">
                <span className="text-base">🔱</span>
                <span>॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति ॥</span>
              </div>
              <span className="text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 hidden sm:inline-block">
                अभेद्य सुरक्षा
              </span>
            </div>

            <div>
              <span className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border inline-block mb-2 text-red-400 bg-red-500/10 border-red-500/20`}>
                {isNepal ? '🇳🇵 Nepal Store Portal' : '🌐 Worldwide Store Portal'}
              </span>
              <h2 className="text-3xl font-black font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
                KALI DIGITAL STORE DASHBOARD
              </h2>
              <p className="text-muted-foreground text-xs mt-1 font-medium">
                Manage your balance, instant deposits, and track platform metrics in {isNepal ? 'NPR (Nepali Rupees)' : 'USD ($)'}.
              </p>
            </div>

            {/* Customers Served & Trust Stats Banner */}
            <div className={`p-6 rounded-3xl border relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-6 bg-gradient-to-r from-red-600/10 via-secondary/40 to-background border-red-500/30`}>
              <div className="flex items-center gap-4">
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 ${isNepal ? 'bg-red-500/20 text-red-400' : 'bg-primary/20 text-primary'}`}>
                  <Users className="w-7 h-7" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-3xl font-black text-foreground tracking-tight">
                      {(profile?.customers_served || 1450).toLocaleString()}+
                    </h3>
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      ✓ {profile?.satisfaction_rate || '99.8%'} Satisfied
                    </span>
                  </div>
                  <p className="text-xs font-bold text-muted-foreground mt-0.5">
                    Customers Served Worldwide & Nepal
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4 sm:gap-6 text-xs text-muted-foreground">
                <div className="border-l border-border/60 pl-4">
                  <div className="font-extrabold text-foreground text-sm">{(profile?.total_deliveries || 3920).toLocaleString()}+</div>
                  <div className="text-[10px]">Instant Deliveries</div>
                </div>
                <div className="border-l border-border/60 pl-4">
                  <div className="font-extrabold text-foreground text-sm">24/7 Active</div>
                  <div className="text-[10px]">Telegram & Live Chat</div>
                </div>
              </div>
            </div>
            
            {/* Wallet Cards */}
            <div className={`grid grid-cols-1 ${isNepal ? 'md:grid-cols-2' : 'md:grid-cols-3'} gap-6`}>
              {/* Main Wallet Card */}
              <div className={`glass-card p-6 rounded-3xl relative overflow-hidden border ${isNepal ? 'border-red-500/30' : 'border-primary/30'}`}>
                <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 pointer-events-none ${isNepal ? 'bg-red-500/20' : 'bg-primary/20'}`} />
                <div className="flex items-center gap-3 text-muted-foreground mb-4">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isNepal ? 'bg-red-500/20 text-red-400' : 'bg-primary/20 text-primary'}`}>
                    <Wallet className="w-4 h-4" />
                  </div>
                  <span className="font-bold text-xs uppercase tracking-wider">{isNepal ? 'NPR Wallet Balance' : 'USD Store Balance'}</span>
                </div>
                <h3 className={`text-3xl sm:text-4xl font-black ${isNepal ? 'text-red-400' : 'text-foreground'}`}>
                  {formatPrice(profile?.balance)}
                </h3>
                <p className="text-[11px] text-muted-foreground mt-1">Available for instant store purchases</p>
                <button 
                  onClick={() => setIsTopUpOpen(true)}
                  className={`mt-6 w-full py-3 text-white font-extrabold text-xs rounded-xl transition-all shadow-md flex items-center justify-center gap-2 ${isNepal ? 'bg-red-500 hover:bg-red-600 shadow-red-500/30' : 'bg-primary hover:bg-primary/90 shadow-primary/30'}`}
                >
                  <CreditCard className="w-4 h-4" /> {isNepal ? 'Deposit via eSewa / Fonepay' : 'Deposit USD Funds'}
                </button>
              </div>

              {/* In Worldwide mode only: Crypto Balance Card */}
              {!isNepal && (
                <div className="glass-card p-6 rounded-3xl relative overflow-hidden border border-blue-500/30">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
                  <div className="flex items-center gap-3 text-muted-foreground mb-4">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400">
                      <Wallet className="w-4 h-4" />
                    </div>
                    <span className="font-bold text-xs uppercase tracking-wider">Crypto Wallet</span>
                  </div>
                  <h3 className="text-3xl font-extrabold text-foreground">${(profile?.crypto_balance || 0).toFixed(2)}</h3>
                  <p className="text-[11px] text-muted-foreground mt-1">Multi-chain auto-verified USDT</p>
                  <button 
                    onClick={() => setIsTopUpOpen(true)}
                    className="mt-6 w-full py-3 bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 text-blue-400 font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2"
                  >
                    Crypto Top Up
                  </button>
                </div>
              )}

              {/* Referral Balance Card */}
              <div className="glass-card p-6 rounded-3xl relative overflow-hidden border border-purple-500/30">
                <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
                <div className="flex items-center gap-3 text-muted-foreground mb-4">
                  <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400">
                    <Wallet className="w-4 h-4" />
                  </div>
                  <span className="font-bold text-xs uppercase tracking-wider">Referral Earnings</span>
                </div>
                <h3 className="text-3xl font-extrabold text-foreground">{formatPrice(profile?.referral_balance)}</h3>
                <p className="text-[11px] text-muted-foreground mt-1">Earned from affiliate invitations</p>
                <button 
                  onClick={() => alert(`Your referral earnings are automatically merged with your ${isNepal ? 'NPR' : 'USD'} wallet balance!`)}
                  className="mt-6 w-full py-3 bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/30 text-purple-300 font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  Referral Info
                </button>
              </div>
            </div>

            {/* ─── FEATURED ITEMS SHOWCASE (ADMIN FEATURED ITEMS) ─── */}
            {featuredProducts && featuredProducts.length > 0 && (
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-300">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-lg font-black text-foreground flex items-center gap-2">
                        ⭐ Featured & Trending Items
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-primary/10 text-primary border border-primary/20">
                          Curated by Admin
                        </span>
                      </h3>
                      <p className="text-xs text-muted-foreground">Top recommended digital products available for instant automated delivery.</p>
                    </div>
                  </div>

                  <Link 
                    href={storePath}
                    className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
                  >
                    View All Products ↗
                  </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {featuredProducts.slice(0, 6).map((item) => (
                    <div 
                      key={item.id}
                      className="glass-card p-5 rounded-2xl border border-border/60 hover:border-primary/50 transition-all flex flex-col justify-between group relative overflow-hidden"
                    >
                      <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-[24px] pointer-events-none group-hover:bg-primary/10 transition-all" />
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                            ⭐ Featured
                          </span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${item.stock > 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'}`}>
                            {item.stock > 0 ? `✓ ${item.stock} in stock` : '⚡ Auto-Restock'}
                          </span>
                        </div>

                        <h4 className="font-extrabold text-sm text-foreground group-hover:text-primary transition-colors line-clamp-1">
                          {item.name}
                        </h4>
                        <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1 mb-4">
                          {item.description}
                        </p>
                      </div>

                      <div className="flex items-center justify-between gap-3 pt-3 border-t border-border/40 mt-auto">
                        <div>
                          <span className="text-[10px] text-muted-foreground block">Instant Price</span>
                          <span className={`text-base font-black ${isNepal ? 'text-red-400' : 'text-emerald-400'}`}>
                            {formatPrice(item.price)}
                          </span>
                        </div>

                        <Link
                          href={`${storePath}?search=${encodeURIComponent(item.name)}`}
                          className={`px-3.5 py-2 text-white font-extrabold text-xs rounded-xl transition-all shadow-sm flex items-center gap-1.5 ${isNepal ? 'bg-red-500 hover:bg-red-600' : 'bg-primary hover:bg-primary/90'}`}
                        >
                          <Bolt className="w-3.5 h-3.5" /> Buy Now
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'purchases' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 inline-block mb-2">
                Order History
              </span>
              <h2 className="text-3xl font-extrabold">My Purchases</h2>
              <p className="text-muted-foreground text-xs mt-1">Access your delivered digital keys, licenses, and accounts.</p>
            </div>
            
            {purchases.length === 0 ? (
              <div className="glass-card p-12 rounded-3xl text-center border-dashed border-border/80">
                <Package className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-bold mb-2">No Purchases Yet</h3>
                <p className="text-muted-foreground text-xs mb-6 max-w-sm mx-auto">Explore our catalog of premium digital goods.</p>
                <Link href={storePath} className={`inline-flex px-6 py-3 text-white rounded-xl font-extrabold text-xs transition-all shadow-md ${isNepal ? 'bg-red-500 hover:bg-red-600' : 'bg-primary hover:bg-primary/90'}`}>
                  Browse Store Catalog
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {purchases.map(p => (
                  <div key={p.id} className="glass-card p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 border border-border/60 hover:border-primary/40 transition-all">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h4 className="font-extrabold text-base text-foreground">{p.description}</h4>
                        
                        {/* Status Badges */}
                        {p.status === 'delivering' && (
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-amber-500/15 border border-amber-500/30 text-amber-300 animate-pulse flex items-center gap-1">
                            ⏳ Delivering (Pending Verification)
                          </span>
                        )}
                        {p.status === 'delivered' && (
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center gap-1">
                            ✅ Delivered
                          </span>
                        )}
                        {p.status === 'completed' && (
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-blue-500/15 border border-blue-500/30 text-blue-400 flex items-center gap-1">
                            ✓ Payment Verified
                          </span>
                        )}
                        {p.status === 'cancelled' && (
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-rose-500/15 border border-rose-500/30 text-rose-400 flex items-center gap-1">
                            ❌ Cancelled
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="w-3.5 h-3.5 text-primary" /> 
                          {p.date ? new Date(p.date).toLocaleString() : 'Recent'}
                        </span>
                        <span className={`font-black ${isNepal ? 'text-red-400' : 'text-emerald-400'}`}>
                          {formatPrice(p.amount)}
                        </span>
                      </div>

                      {p.status === 'delivering' && (
                        <p className="text-[11px] text-amber-300/80 mt-1">
                          ℹ️ Order is currently in progress. Digital keys/credentials will be delivered here and to your email upon admin verification.
                        </p>
                      )}
                    </div>

                    {p.delivered_content ? (
                      <button 
                        onClick={() => copyDeliveredKey(p.id, p.delivered_content!)}
                        className="px-4 py-2.5 bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 rounded-xl text-xs font-bold hover:bg-emerald-500/25 transition-all flex items-center justify-center gap-2 flex-shrink-0"
                      >
                        {copiedKeyId === p.id ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                        {copiedKeyId === p.id ? "Key Copied!" : "Copy Delivered Key"}
                      </button>
                    ) : p.status === 'delivering' ? (
                      <div className="text-xs font-bold text-amber-400/90 bg-amber-500/10 px-3.5 py-2 rounded-xl border border-amber-500/20 text-center flex-shrink-0 flex items-center gap-1.5">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" /> Delivery In Progress
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── LIVE 24/7 INTERACTIVE CUSTOMER SUPPORT CHAT ─── */}
        {activeTab === 'support' && (
          <div className="max-w-3xl animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border inline-block ${isNepal ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-primary bg-primary/10 border-primary/20'}`}>
                    Live Assistance
                  </span>
                  <span className="text-[10px] font-extrabold text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
                    Support Online
                  </span>
                </div>
                <h2 className="text-3xl font-extrabold mt-1">24/7 Customer Live Support</h2>
                <p className="text-muted-foreground text-xs">Chat live with our dedicated support staff or send order inquiries.</p>
              </div>

              {supportLinks.bot_url && (
                <a
                  href={supportLinks.bot_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3.5 py-2 rounded-xl bg-secondary/80 border border-border/80 hover:bg-secondary text-xs font-bold text-foreground transition-all flex items-center gap-1.5 shadow-sm"
                >
                  <MessageCircle className="w-4 h-4 text-primary" />
                  <span>Chat via Telegram ↗</span>
                </a>
              )}
            </div>

            {/* Chat Box Container */}
            <div className="glass-card rounded-3xl border border-border/70 overflow-hidden flex flex-col h-[520px] shadow-[0_0_50px_rgba(0,0,0,0.5)]">
              {/* Chat Header */}
              <div className="px-6 py-3.5 bg-secondary/40 border-b border-border/60 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${isNepal ? 'bg-red-500/20 text-red-400' : 'bg-primary/20 text-primary'}`}>
                    <Headphones className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="font-extrabold text-xs text-foreground">KDS Official Support Team</div>
                    <div className="text-[10px] text-muted-foreground">Typical reply time: <b>Under 3 minutes</b></div>
                  </div>
                </div>

                <button
                  onClick={fetchChatMessages}
                  className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                  title="Refresh messages"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Message Stream */}
              <div className="flex-1 p-6 overflow-y-auto space-y-4">
                {chatMessages.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground space-y-2">
                    <MessageCircle className="w-10 h-10 mx-auto text-muted-foreground/50" />
                    <p className="text-xs font-bold">No messages yet</p>
                    <p className="text-[11px]">Send a message below to start chatting with our support agents.</p>
                  </div>
                ) : (
                  chatMessages.map((msg, index) => {
                    const isMe = msg.sender === 'user';
                    return (
                      <div 
                        key={msg.id || index}
                        className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
                      >
                        <div className="flex items-center gap-1.5 mb-1 px-1">
                          <span className="text-[10px] font-extrabold text-muted-foreground">
                            {isMe ? 'You' : (msg.sender_name || 'KDS Support Team')}
                          </span>
                          <span className="text-[9px] text-muted-foreground/60 font-mono">
                            {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>

                        <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                          isMe 
                            ? (isNepal 
                                ? 'bg-red-500 text-white rounded-tr-none shadow-[0_0_15px_rgba(239,68,68,0.25)] font-medium' 
                                : 'bg-primary text-primary-foreground rounded-tr-none shadow-[0_0_15px_rgba(99,102,241,0.25)] font-medium')
                            : 'bg-secondary/80 border border-border/80 text-foreground rounded-tl-none font-normal'
                        }`}>
                          <p className="whitespace-pre-wrap">{msg.message}</p>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={sendChatMessage} className="p-3.5 bg-secondary/30 border-t border-border/60 flex items-center gap-2">
                <input 
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Type your question, order issue, or payment reference..."
                  className="flex-1 bg-black/40 border border-border/80 rounded-2xl px-4 py-2.5 text-xs font-medium focus:outline-none focus:border-primary transition-all"
                />
                <button
                  type="submit"
                  disabled={isSendingChat || !chatInput.trim()}
                  className={`px-4 py-2.5 rounded-2xl text-white font-extrabold text-xs disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-md ${
                    isNepal ? 'bg-red-500 hover:bg-red-600' : 'bg-primary hover:bg-primary/90'
                  }`}
                >
                  {isSendingChat ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  <span className="hidden sm:inline">Send</span>
                </button>
              </form>
            </div>
          </div>
        )}
      </main>

      {/* Top-Up Wallet Modal (Completely Separate for Nepal vs Worldwide) */}
      {isTopUpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="glass-card w-full max-w-md rounded-3xl p-6 relative border border-primary/30 shadow-[0_0_60px_rgba(0,0,0,0.8)] max-h-[90vh] overflow-y-auto">
            <button 
              onClick={() => { setIsTopUpOpen(false); setInvoiceUrl(null); }}
              className="absolute top-5 right-5 p-2 rounded-full hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="mb-6">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border inline-block mb-2 ${isNepal ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-primary bg-primary/10 border-primary/20'}`}>
                {isNepal ? '🇳🇵 Nepal NPR Wallet Deposit' : '🌐 USD Wallet Deposit'}
              </span>
              <h2 className="text-xl font-extrabold">{isNepal ? 'Deposit Funds (eSewa / Fonepay)' : 'Top Up USD Balance'}</h2>
              <p className="text-xs text-muted-foreground mt-1">
                {isNepal ? 'Scan the QR code and submit your reference code.' : 'Instant automated deposit via CryptoPay or Telegram.'}
              </p>
            </div>

            {isNepal ? (
              /* Nepal Deposit Flow - 100% Crypto-Free */
              nepalDepositSuccess ? (
                <div className="text-center py-6 space-y-3">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
                    <Check className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-base text-foreground">Deposit Submitted!</h3>
                  <p className="text-xs text-muted-foreground">An admin has been notified and will verify your transaction code and credit your wallet.</p>
                </div>
              ) : (
                <form onSubmit={handleNepalDepositSubmit} className="space-y-4">
                  <div className="text-center p-3 rounded-2xl bg-secondary/40 border border-red-500/20">
                    <div className="text-[11px] font-bold text-red-400 uppercase mb-2">{nepalQrData?.title || 'eSewa / Fonepay Direct QR'}</div>
                    {nepalQrData?.qr_url && (
                      <div className="p-2 bg-white rounded-xl inline-block shadow-md mb-2">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={nepalQrData.qr_url} alt="Nepal QR" className="w-40 h-40 object-contain mx-auto" />
                      </div>
                    )}
                    <p className="text-xs font-bold text-foreground">Account: <span className="text-red-400">{nepalQrData?.account_name || 'KDS Digital Store'}</span></p>
                    <p className="text-xs font-mono text-muted-foreground">ID/Number: {nepalQrData?.account_id || '9800000000'}</p>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-muted-foreground mb-1">Amount to Deposit (NPR)</label>
                    <input 
                      type="number" 
                      min="100" 
                      step="50"
                      value={nepalDepositNpr}
                      onChange={(e) => setNepalDepositNpr(e.target.value)}
                      placeholder="e.g. 1500"
                      className="w-full bg-black/40 border border-border/80 rounded-xl px-4 py-2.5 text-sm font-extrabold focus:outline-none focus:border-red-500 transition-all font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-muted-foreground mb-1">Transaction Reference / eSewa Code</label>
                    <input 
                      type="text" 
                      value={nepalTxId}
                      onChange={(e) => setNepalTxId(e.target.value)}
                      placeholder="e.g. 000001234567"
                      className="w-full bg-black/40 border border-border/80 rounded-xl px-4 py-2.5 text-xs font-mono font-bold focus:outline-none focus:border-red-500 transition-all"
                    />
                  </div>

                  {/* Optional Payment Screenshot Receipt Upload */}
                  <div>
                    <label className="text-[11px] font-bold text-muted-foreground block mb-1 flex items-center justify-between">
                      <span>Payment Screenshot / Receipt:</span>
                      <span className="text-[10px] text-muted-foreground">JPG, PNG up to 5MB</span>
                    </label>
                    
                    {!proofImage ? (
                      <label className="flex flex-col items-center justify-center p-3 border-2 border-dashed border-border/80 hover:border-red-500/60 rounded-xl cursor-pointer bg-secondary/20 hover:bg-secondary/40 transition-all text-center">
                        <UploadCloud className="w-5 h-5 text-red-400 mb-1" />
                        <span className="text-xs font-bold text-foreground">Click to upload deposit screenshot</span>
                        <span className="text-[10px] text-muted-foreground mt-0.5">Attach your transfer receipt for fast balance verification</span>
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

                  <button 
                    type="submit"
                    disabled={isGeneratingInvoice || !nepalTxId.trim()}
                    className="w-full py-3.5 bg-red-500 hover:bg-red-600 text-white font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all shadow-[0_0_20px_rgba(239,68,68,0.35)] flex items-center justify-center gap-2"
                  >
                    {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                    {isGeneratingInvoice ? "Submitting..." : `Submit Deposit (NPR ${parseFloat(nepalDepositNpr || '0').toLocaleString()})`}
                  </button>
                </form>
              )
            ) : (
              /* Worldwide Deposit Flow - Exactly matching Telegram Bot Payment Methods */
              cryptoDepositSuccess ? (
                <div className="text-center py-6 space-y-3">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
                    <Check className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-base text-foreground">Deposit Submitted!</h3>
                  <p className="text-xs text-muted-foreground">{cryptoDepositMsg || "Your deposit has been submitted. It will be credited automatically or upon admin verification."}</p>
                </div>
              ) : (
                <form onSubmit={handleCryptoDepositSubmit} className="space-y-4">
                  {/* Amount Input with Quick Presets */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-xs font-bold text-muted-foreground">Deposit Amount ($ USD)</label>
                      <div className="flex items-center gap-1">
                        {["5", "10", "25", "50", "100"].map((preset) => (
                          <button
                            key={preset}
                            type="button"
                            onClick={() => setTopUpAmount(preset)}
                            className={`px-2 py-0.5 text-[10px] font-bold rounded-lg transition-colors ${
                              topUpAmount === preset 
                                ? 'bg-primary text-primary-foreground' 
                                : 'bg-secondary/60 hover:bg-secondary text-muted-foreground hover:text-foreground'
                            }`}
                          >
                            ${preset}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="relative">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-extrabold text-muted-foreground">$</span>
                      <input 
                        type="number" 
                        min="1" 
                        step="0.5"
                        value={topUpAmount}
                        onChange={(e) => setTopUpAmount(e.target.value)}
                        className="w-full bg-black/40 border border-border/80 rounded-xl pl-8 pr-4 py-2.5 text-sm font-extrabold focus:outline-none focus:border-primary transition-all font-mono"
                      />
                    </div>
                  </div>

                  {/* Payment Method Selector Grid */}
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground mb-2">Choose Payment Method</label>
                    <div className="grid grid-cols-2 gap-2">
                      {cryptoMethods.length > 0 ? (
                        cryptoMethods.map((m) => {
                          const isSelected = selectedCryptoId === m.id;
                          return (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => { setSelectedCryptoId(m.id); setInvoiceUrl(null); }}
                              className={`p-2.5 rounded-2xl border text-left transition-all flex flex-col justify-between ${
                                isSelected
                                  ? 'bg-primary/10 border-primary text-foreground shadow-[0_0_15px_rgba(99,102,241,0.25)]'
                                  : 'bg-secondary/20 border-border/60 hover:border-border hover:bg-secondary/40 text-muted-foreground hover:text-foreground'
                              }`}
                            >
                              <div className="flex items-center justify-between w-full mb-1">
                                <span className="text-base">{m.icon}</span>
                                <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded-full ${
                                  isSelected ? 'bg-primary/20 text-primary border border-primary/30' : 'bg-white/5 text-muted-foreground'
                                }`}>
                                  {m.badge}
                                </span>
                              </div>
                              <div className="font-bold text-xs text-foreground truncate">{m.name}</div>
                            </button>
                          );
                        })
                      ) : (
                        <div className="col-span-2 text-center py-4 text-xs text-muted-foreground animate-pulse">
                          Loading available payment methods...
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Active Method Details Form */}
                  {(() => {
                    const activeMethod = cryptoMethods.find(m => m.id === selectedCryptoId);
                    if (!activeMethod) return null;

                    if (activeMethod.type === 'invoice') {
                      return (
                        <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/80 space-y-3">
                          <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                            <span>{activeMethod.icon}</span>
                            <span>{activeMethod.name}</span>
                            <span className="ml-auto text-[10px] text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">Instant Auto-Credit</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-relaxed">{activeMethod.description}</p>

                          {invoiceUrl ? (
                            <div className="space-y-2.5 pt-1">
                              <a href={invoiceUrl} target="_blank" rel="noreferrer"
                                className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(34,197,94,0.4)]">
                                <span>💎 Pay via CryptoPay Bot</span>
                                <ExternalLink className="w-4 h-4" />
                              </a>
                              {isCryptoPolling && (
                                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/5 border border-emerald-500/20 text-emerald-400">
                                  <RefreshCw className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                                  <span className="text-[11px] font-semibold">Waiting for payment confirmation... Balance will update automatically.</span>
                                </div>
                              )}
                              <button type="button" onClick={() => { setInvoiceUrl(null); setCryptoInvoiceId(null); setIsCryptoPolling(false); }}
                                className="w-full py-2 text-center text-[10px] text-muted-foreground hover:text-foreground font-semibold">
                                ← Choose a different amount / method
                              </button>
                            </div>
                          ) : (
                            <button type="submit" disabled={isGeneratingInvoice || !topUpAmount}
                              className="w-full py-3 bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all shadow-[0_0_20px_rgba(99,102,241,0.35)] flex items-center justify-center gap-2">
                              {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                              {isGeneratingInvoice ? "Generating Invoice..." : `Generate Crypto Invoice ($${topUpAmount})`}
                            </button>
                          )}
                        </div>
                      );
                    }

                    if (activeMethod.type === 'onchain') {
                      return (
                        <div className="space-y-3 p-3.5 rounded-2xl bg-secondary/30 border border-border/80">
                          <div className="text-center">
                            <div className="text-[11px] font-bold text-primary uppercase mb-2">{activeMethod.name} Direct Deposit</div>
                            {activeMethod.qr_url && (
                              <div className="p-2 bg-white rounded-xl inline-block shadow-md mb-2">
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img src={activeMethod.qr_url} alt="Wallet QR" className="w-32 h-32 object-contain mx-auto" />
                              </div>
                            )}
                            <div className="flex items-center justify-center gap-2 bg-black/40 border border-border/80 rounded-xl px-3 py-2">
                              <span className="text-[11px] font-mono text-muted-foreground truncate max-w-[240px]">{activeMethod.wallet_address}</span>
                              <button type="button" onClick={() => handleCopyText(activeMethod.wallet_address || '')}
                                className="p-1 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors flex-shrink-0">
                                {copiedAddress ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                            <p className="text-[10px] text-muted-foreground mt-1.5">
                              Send exactly <b>${topUpAmount} USDT</b> ({activeMethod.network}) to this address. Auto-verified for BEP20.
                            </p>
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold text-muted-foreground mb-1">
                              Transaction Hash ({activeMethod.network === 'BEP20' ? '0x...' : 'TX Hash'})
                            </label>
                            <input type="text" required value={cryptoTxHash} onChange={(e) => setCryptoTxHash(e.target.value)}
                              placeholder={activeMethod.network === 'BEP20' ? '0x...' : '64 hex characters'}
                              className="w-full bg-black/40 border border-border/80 rounded-xl px-4 py-2.5 text-xs font-mono font-bold focus:outline-none focus:border-primary transition-all" />
                          </div>

                          <div>
                            <label className="text-[11px] font-bold text-muted-foreground block mb-1">Payment Screenshot (Optional)</label>
                            {!proofImage ? (
                              <label className="flex flex-col items-center justify-center p-2.5 border border-dashed border-border hover:border-primary rounded-xl cursor-pointer bg-secondary/20 hover:bg-secondary/40 transition-all text-center">
                                <UploadCloud className="w-4 h-4 text-primary mb-1" />
                                <span className="text-[11px] font-bold text-foreground">Click to upload TX receipt</span>
                                <input type="file" accept="image/*" className="hidden" onChange={handleProofImageChange} />
                              </label>
                            ) : (
                              <div className="relative p-2 rounded-xl bg-secondary/50 border border-border flex items-center gap-2.5">
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img src={proofImage} alt="Receipt Preview" className="w-10 h-10 rounded-lg object-cover border border-border flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-[11px] font-bold text-foreground truncate">{proofFileName || 'receipt.jpg'}</p>
                                  <p className="text-[9px] text-emerald-400 font-semibold">✓ Attached</p>
                                </div>
                                <button type="button" onClick={() => { setProofImage(null); setProofFileName(''); }}
                                  className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors">
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            )}
                          </div>

                          <button type="submit" disabled={isGeneratingInvoice || !cryptoTxHash.trim()}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all shadow-[0_0_20px_rgba(99,102,241,0.35)] flex items-center justify-center gap-2">
                            {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                            {isGeneratingInvoice ? "Verifying on-chain..." : `Verify & Submit ($${topUpAmount} USDT)`}
                          </button>
                        </div>
                      );
                    }

                    if (activeMethod.type === 'uid_transfer' && activeMethod.id === 'bybit') {
                      // ── BYBIT: Full step-by-step flow matching Telegram bot ──
                      if (bybitStep === 'success') {
                        return (
                          <div className="text-center py-6 space-y-3">
                            <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400"><Check className="w-6 h-6" /></div>
                            <h3 className="font-bold text-base text-foreground">⚡ Balance Credited!</h3>
                            <p className="text-xs text-muted-foreground">{cryptoDepositMsg}</p>
                          </div>
                        );
                      }
                      if (bybitStep === 'pending') {
                        return (
                          <div className="text-center py-6 space-y-3">
                            <div className="text-3xl">⏳</div>
                            <h3 className="font-bold text-base text-foreground">Under Review</h3>
                            <p className="text-xs text-muted-foreground">{cryptoDepositMsg || "Our team will verify and credit your balance shortly."}</p>
                          </div>
                        );
                      }
                      if (bybitStep === 'verifying') {
                        return (
                          <div className="text-center py-8 space-y-3">
                            <RefreshCw className="w-8 h-8 mx-auto text-primary animate-spin" />
                            <p className="text-xs font-bold text-foreground">Verifying transfer on Bybit...</p>
                            <p className="text-[10px] text-muted-foreground">Checking your internal transfer record.</p>
                          </div>
                        );
                      }
                      if (bybitStep === 'showing_details' && bybitInit) {
                        return (
                          <div className="space-y-3 p-3.5 rounded-2xl bg-secondary/30 border border-border/80">
                            <div className="text-[11px] font-extrabold text-primary uppercase mb-1">⚡ Bybit Pay — UID Transfer</div>
                            <p className="text-[10px] text-muted-foreground mb-2">Instant · No fees · Bybit → Bybit only</p>

                            {/* Step-by-step instructions matching Telegram bot */}
                            <div className="space-y-1.5 text-[11px] font-medium text-foreground bg-black/30 rounded-xl p-3 border border-border/60">
                              <p className="font-bold text-muted-foreground uppercase text-[10px] mb-2">Steps:</p>
                              <p>1. Open <b>Bybit</b> → Assets → Transfer → <b>Send by UID</b></p>
                              <p>2. Coin: <b>USDT</b></p>
                              <p>3. Recipient UID:</p>
                              <div className="flex items-center gap-2 bg-black/40 border border-border/80 rounded-lg px-3 py-2 mt-1">
                                <code className="text-primary font-bold text-xs flex-1">{bybitInit.bybit_uid}</code>
                                <button type="button" onClick={() => handleCopyText(bybitInit.bybit_uid)}
                                  className="p-1 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors flex-shrink-0">
                                  {copiedAddress ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                              <p className="mt-1.5">4. Amount: <b className="text-amber-400">{bybitInit.unique_amount} USDT</b> <span className="text-[10px] text-muted-foreground">(send EXACTLY this amount)</span></p>
                            </div>

                            <div>
                              <label className="block text-[11px] font-bold text-muted-foreground mb-1">Bybit Transfer ID <span className="text-muted-foreground/60 font-normal">(from Assets → Transaction History — optional but helps auto-verify)</span></label>
                              <input type="text" value={bybitTxId} onChange={(e) => setBybitTxId(e.target.value)}
                                placeholder="e.g. 9283748290"
                                className="w-full bg-black/40 border border-border/80 rounded-xl px-4 py-2.5 text-xs font-mono font-bold focus:outline-none focus:border-primary transition-all" />
                            </div>

                            <div>
                              <label className="text-[11px] font-bold text-muted-foreground block mb-1">Transfer Screenshot (Optional)</label>
                              {!proofImage ? (
                                <label className="flex flex-col items-center justify-center p-2.5 border border-dashed border-border hover:border-primary rounded-xl cursor-pointer bg-secondary/20 hover:bg-secondary/40 transition-all text-center">
                                  <UploadCloud className="w-4 h-4 text-primary mb-1" />
                                  <span className="text-[11px] font-bold text-foreground">Upload Bybit transfer screenshot</span>
                                  <input type="file" accept="image/*" className="hidden" onChange={handleProofImageChange} />
                                </label>
                              ) : (
                                <div className="relative p-2 rounded-xl bg-secondary/50 border border-border flex items-center gap-2.5">
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img src={proofImage} alt="Receipt" className="w-10 h-10 rounded-lg object-cover border border-border flex-shrink-0" />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-bold text-foreground truncate">{proofFileName || 'receipt.jpg'}</p>
                                    <p className="text-[9px] text-emerald-400 font-semibold">✓ Attached</p>
                                  </div>
                                  <button type="button" onClick={() => { setProofImage(null); setProofFileName(''); }}
                                    className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>

                            <button type="button" onClick={handleBybitVerify}
                              className="w-full py-3 bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-xs rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.35)] flex items-center justify-center gap-2">
                              <CheckCheck className="w-4 h-4" />
                              I&apos;ve Sent It — Verify Transfer
                            </button>
                            <button type="button" onClick={() => { setBybitStep('idle'); setBybitInit(null); }}
                              className="w-full py-2 text-center text-[10px] text-muted-foreground hover:text-foreground font-semibold">
                              ← Cancel / Choose different method
                            </button>
                          </div>
                        );
                      }
                      // Default: show "Get Instructions" button
                      return (
                        <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/80 space-y-3">
                          <div className="text-[11px] font-bold text-primary uppercase">⚡ Bybit Pay — UID Transfer</div>
                          <p className="text-[10px] text-muted-foreground">{activeMethod.description}</p>
                          <button type="submit" disabled={isGeneratingInvoice}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all flex items-center justify-center gap-2">
                            {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                            {isGeneratingInvoice ? "Initializing..." : `Get Bybit Transfer Instructions ($${topUpAmount})`}
                          </button>
                        </div>
                      );
                    }

                    if (activeMethod.type === 'uid_transfer' && activeMethod.id === 'binance') {
                      // ── BINANCE: Full step-by-step flow with remark code ──
                      if (binanceStep === 'success') {
                        return (
                          <div className="text-center py-6 space-y-3">
                            <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400"><Check className="w-6 h-6" /></div>
                            <h3 className="font-bold text-base text-foreground">🪙 Balance Credited!</h3>
                            <p className="text-xs text-muted-foreground">{cryptoDepositMsg}</p>
                          </div>
                        );
                      }
                      if (binanceStep === 'pending') {
                        return (
                          <div className="text-center py-6 space-y-3">
                            <div className="text-3xl">⏳</div>
                            <h3 className="font-bold text-base text-foreground">Under Review</h3>
                            <p className="text-xs text-muted-foreground">{cryptoDepositMsg || "Our team will verify and credit your balance shortly."}</p>
                          </div>
                        );
                      }
                      if (binanceStep === 'verifying') {
                        return (
                          <div className="text-center py-8 space-y-3">
                            <RefreshCw className="w-8 h-8 mx-auto text-amber-400 animate-spin" />
                            <p className="text-xs font-bold text-foreground">Scanning Binance Pay transactions...</p>
                            <p className="text-[10px] text-muted-foreground">Matching your remark code and amount.</p>
                          </div>
                        );
                      }
                      if (binanceStep === 'showing_details' && binanceInit) {
                        return (
                          <div className="space-y-3 p-3.5 rounded-2xl bg-secondary/30 border border-border/80">
                            <div className="text-[11px] font-extrabold text-amber-400 uppercase mb-1">🪙 Binance Pay</div>
                            <p className="text-[10px] text-muted-foreground mb-2">No fees · Verified via Remark Code &amp; Amount</p>

                            {/* Step-by-step instructions */}
                            <div className="space-y-1.5 text-[11px] font-medium text-foreground bg-black/30 rounded-xl p-3 border border-border/60">
                              <p className="font-bold text-muted-foreground uppercase text-[10px] mb-2">Steps:</p>
                              <p>1. Open <b>Binance</b> → Pay → Send</p>
                              <p>2. Pay ID:</p>
                              <div className="flex items-center gap-2 bg-black/40 border border-border/80 rounded-lg px-3 py-2 mt-1">
                                <code className="text-amber-400 font-bold text-xs flex-1">{binanceInit.binance_pay_id}</code>
                                <button type="button" onClick={() => handleCopyText(binanceInit.binance_pay_id)}
                                  className="p-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 transition-colors flex-shrink-0">
                                  {copiedAddress ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                              <p className="mt-1.5">3. Amount: <b className="text-amber-400">{binanceInit.unique_amount} USDT</b></p>
                              <p>4. Remarks / Note:</p>
                              <div className="flex items-center gap-2 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2 mt-1">
                                <code className="text-rose-400 font-extrabold text-sm flex-1">{binanceInit.remark_code}</code>
                                <button type="button" onClick={() => handleCopyText(binanceInit.remark_code)}
                                  className="p-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 transition-colors flex-shrink-0">
                                  {copiedAddress ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                            </div>

                            {/* Strict verification warning */}
                            <div className="p-2.5 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-1">
                              <p className="text-[10px] font-extrabold text-amber-400">⚠️ Strict Verification Rules:</p>
                              <p className="text-[10px] text-muted-foreground">• Send EXACTLY <b className="text-amber-400">{binanceInit.unique_amount} USDT</b> — no more or less.</p>
                              <p className="text-[10px] text-muted-foreground">• You <b>MUST</b> include remark <code className="text-rose-400 font-bold">{binanceInit.remark_code}</code> in your note.</p>
                            </div>

                            <div>
                              <label className="text-[11px] font-bold text-muted-foreground block mb-1">Transfer Screenshot (Optional)</label>
                              {!proofImage ? (
                                <label className="flex flex-col items-center justify-center p-2.5 border border-dashed border-border hover:border-amber-500/60 rounded-xl cursor-pointer bg-secondary/20 hover:bg-secondary/40 transition-all text-center">
                                  <UploadCloud className="w-4 h-4 text-amber-400 mb-1" />
                                  <span className="text-[11px] font-bold text-foreground">Upload Binance pay screenshot</span>
                                  <input type="file" accept="image/*" className="hidden" onChange={handleProofImageChange} />
                                </label>
                              ) : (
                                <div className="relative p-2 rounded-xl bg-secondary/50 border border-border flex items-center gap-2.5">
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img src={proofImage} alt="Receipt" className="w-10 h-10 rounded-lg object-cover border border-border flex-shrink-0" />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-bold text-foreground truncate">{proofFileName || 'receipt.jpg'}</p>
                                    <p className="text-[9px] text-emerald-400 font-semibold">✓ Attached</p>
                                  </div>
                                  <button type="button" onClick={() => { setProofImage(null); setProofFileName(''); }}
                                    className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>

                            <button type="button" onClick={handleBinanceVerify}
                              className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-black font-extrabold text-xs rounded-xl transition-all shadow-[0_0_20px_rgba(245,158,11,0.35)] flex items-center justify-center gap-2">
                              <CheckCheck className="w-4 h-4" />
                              I&apos;ve Sent It — Verify Transfer
                            </button>
                            <button type="button" onClick={() => { setBinanceStep('idle'); setBinanceInit(null); }}
                              className="w-full py-2 text-center text-[10px] text-muted-foreground hover:text-foreground font-semibold">
                              ← Cancel / Choose different method
                            </button>
                          </div>
                        );
                      }
                      // Default
                      return (
                        <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/80 space-y-3">
                          <div className="text-[11px] font-bold text-amber-400 uppercase">🪙 Binance Pay</div>
                          <p className="text-[10px] text-muted-foreground">{activeMethod.description}</p>
                          <button type="submit" disabled={isGeneratingInvoice}
                            className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-black font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all flex items-center justify-center gap-2">
                            {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                            {isGeneratingInvoice ? "Initializing..." : `Get Binance Pay Instructions ($${topUpAmount})`}
                          </button>
                        </div>
                      );
                    }

                    if (activeMethod.type === 'uid_transfer') {
                      // Fallback for any other uid_transfer type
                      return (
                        <div className="space-y-3 p-3.5 rounded-2xl bg-secondary/30 border border-border/80">
                          <div className="text-center">
                            <div className="text-[11px] font-bold text-primary uppercase mb-1">{activeMethod.name} Internal Transfer</div>
                            <div className="flex items-center justify-center gap-2 bg-black/40 border border-border/80 rounded-xl px-4 py-2">
                              <span className="text-xs font-mono font-bold text-foreground">ID: {activeMethod.account_id}</span>
                              <button type="button" onClick={() => handleCopyText(activeMethod.account_id || '')}
                                className="p-1 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary transition-colors">
                                {copiedAddress ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                          </div>
                          <div>
                            <input type="text" required value={cryptoTxHash} onChange={(e) => setCryptoTxHash(e.target.value)}
                              placeholder="Transfer Order / Reference ID" className="w-full bg-black/40 border border-border/80 rounded-xl px-4 py-2.5 text-xs font-mono font-bold focus:outline-none focus:border-primary transition-all" />
                          </div>
                          <button type="submit" disabled={isGeneratingInvoice || !cryptoTxHash.trim()}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-xs rounded-xl disabled:opacity-50 transition-all flex items-center justify-center gap-2">
                            {isGeneratingInvoice ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                            {isGeneratingInvoice ? "Submitting..." : `Submit Deposit ($${topUpAmount} USD)`}
                          </button>
                        </div>
                      );
                    }

                    if (activeMethod.type === 'stars') {
                      return (
                        <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/80 space-y-3 text-center">
                          <div className="text-2xl">🌟</div>
                          <div className="text-xs font-bold text-foreground">Telegram Stars In-App Payment</div>
                          <p className="text-[11px] text-muted-foreground leading-relaxed">
                            Pay with official Telegram Stars directly inside our Telegram Bot.
                          </p>
                          <a href={activeMethod.bot_url || "https://t.me/kali_digital_store_bot"} target="_blank" rel="noreferrer"
                            className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-black font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(245,158,11,0.35)]">
                            <span>Open Telegram Bot for Stars ↗</span>
                          </a>
                        </div>
                      );
                    }

                    return null;
                  })()}
                </form>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
