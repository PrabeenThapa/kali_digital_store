"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useGeoLocation } from "@/lib/geo";
import { 
  Flame, Lock, Mail, Send, ShieldCheck, Zap, 
  ArrowRight, RefreshCw, AlertCircle, Globe
} from "lucide-react";

type Tab = "signin" | "signup" | "telegram";

export default function LoginPage() {
  const router = useRouter();
  const geo = useGeoLocation();
  const [tab, setTab] = useState<Tab>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [telegramId, setTelegramId] = useState("");
  const [tgPassword, setTgPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [region, setRegion] = useState<'worldwide' | 'nepal'>('worldwide');

  useEffect(() => {
    if (geo.is_nepal) {
      setRegion('nepal');
      localStorage.setItem('region', 'nepal');
    } else {
      const saved = (localStorage.getItem('region') as 'worldwide' | 'nepal') || 'worldwide';
      setRegion(saved);
    }
  }, [geo.is_nepal]);

  function handleRegionChange(r: 'worldwide' | 'nepal') {
    if (geo.is_nepal && r === 'worldwide') return;
    setRegion(r);
    localStorage.setItem('region', r);
  }

  function switchTab(t: Tab) {
    setTab(t);
    setError("");
  }

  function getRedirectPath() {
    if (geo.is_nepal) return '/nepal';
    const saved = localStorage.getItem('region');
    if (saved === 'nepal') return '/nepal';
    if (saved === 'worldwide') return '/worldwide';
    return '/dashboard';
  }


  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login_email", { email, password });
      localStorage.setItem("token", res.data.access_token);
      router.push(getRedirectPath());
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/register", { email, password });
      localStorage.setItem("token", res.data.access_token);
      router.push(getRedirectPath());
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not create account.");
    } finally {
      setLoading(false);
    }
  }

  async function handleTelegramLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login_telegram_id", {
        telegram_id: parseInt(telegramId, 10),
        password: tgPassword,
      });
      localStorage.setItem("token", res.data.access_token);
      router.push(getRedirectPath());
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Invalid Telegram ID or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-4 relative overflow-hidden selection:bg-red-600 selection:text-white">
      {/* Background glowing celestial aura */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-red-600/15 blur-[160px] pointer-events-none -translate-y-1/2 animate-pulse" />
      <div className="fixed bottom-0 right-1/4 w-[450px] h-[450px] rounded-full bg-amber-600/10 blur-[140px] pointer-events-none translate-y-1/3" />

      {/* Top Sacred Mantra */}
      <div className="mb-6 text-center">
        <p className="text-[10px] font-extrabold text-red-400 tracking-widest uppercase font-vedic flex items-center justify-center gap-1.5">
          <span>🔱</span>
          <span>॥ ॐ क्रीं कालिकायै नमः ॥</span>
          <span>🔱</span>
        </p>
      </div>

      {/* Region Switcher */}
      <div className="mb-6 flex items-center gap-2 p-1.5 rounded-full bg-secondary/80 border border-red-500/30 text-xs font-bold shadow-lg">
        <span className="text-muted-foreground pl-3 text-[11px]">Region:</span>
        {!geo.is_nepal && (
          <button
            type="button"
            onClick={() => handleRegionChange('worldwide')}
            className={`px-3.5 py-1.5 rounded-full transition-all flex items-center gap-1.5 ${
              region === 'worldwide'
                ? 'bg-red-600 text-white font-extrabold shadow-md shadow-red-600/30'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Globe className="w-3.5 h-3.5" /> Worldwide (USD)
          </button>
        )}
        <button
          type="button"
          onClick={() => handleRegionChange('nepal')}
          className={`px-3.5 py-1.5 rounded-full transition-all flex items-center gap-1.5 ${
            region === 'nepal'
              ? 'bg-red-600 text-white font-extrabold shadow-md shadow-red-600/30'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <span>🇳🇵</span> Nepal (NPR)
        </button>
      </div>


      {/* Login Card */}
      <div className="glass-card w-full max-w-md rounded-3xl p-8 border border-red-500/30 shadow-[0_0_50px_rgba(225,29,72,0.25)] relative z-10">
        {/* Animated Maa Kaali Brand Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="relative mb-3 group">
            <div className="w-20 h-20 rounded-full p-0.5 bg-gradient-to-br from-red-500 via-rose-600 to-amber-600 shadow-[0_0_25px_rgba(225,29,72,0.6)] animate-kaali-pulse overflow-hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.png" alt="Maa Kaali" className="w-full h-full object-cover rounded-full" />
            </div>
          </div>
          <h1 className="text-2xl font-black tracking-tight font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
            KALI DIGITAL STORE
          </h1>
          <p className="text-[11px] text-muted-foreground font-medium mt-0.5">
            दिव्य डिजिटल शक्ति • Instant Automated Access
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex rounded-2xl bg-secondary/60 p-1 mb-6 border border-border/60">
          <button
            type="button"
            onClick={() => switchTab("signin")}
            className={`flex-1 py-2 rounded-xl text-xs font-extrabold transition-all ${
              tab === "signin"
                ? "bg-red-600 text-white shadow-md shadow-red-600/30"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => switchTab("signup")}
            className={`flex-1 py-2 rounded-xl text-xs font-extrabold transition-all ${
              tab === "signup"
                ? "bg-red-600 text-white shadow-md shadow-red-600/30"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Register
          </button>
          <button
            type="button"
            onClick={() => switchTab("telegram")}
            className={`flex-1 py-2 rounded-xl text-xs font-extrabold transition-all flex items-center justify-center gap-1 ${
              tab === "telegram"
                ? "bg-red-600 text-white shadow-md shadow-red-600/30"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Send className="w-3 h-3" /> Telegram
          </button>
        </div>

        {error && (
          <div className="mb-5 p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2 font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Sign In Form */}
        {tab === "signin" && (
          <form onSubmit={handleSignIn} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="yourname@gmail.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 mt-2 bg-red-600 hover:bg-red-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-red-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <>Sign In to Dashboard <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>
        )}

        {/* Register Form */}
        {tab === "signup" && (
          <form onSubmit={handleSignUp} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="yourname@gmail.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Create Secure Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 mt-2 bg-red-600 hover:bg-red-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-red-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <>Create Free Account <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>
        )}

        {/* Telegram ID Login */}
        {tab === "telegram" && (
          <form onSubmit={handleTelegramLogin} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Your Telegram User ID</label>
              <div className="relative">
                <Send className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="number"
                  required
                  placeholder="e.g. 7159009666"
                  value={telegramId}
                  onChange={e => setTelegramId(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">Get your Telegram ID from @userinfobot</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">Account Password (Optional / Default)</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  placeholder="Leave empty if first time login"
                  value={tgPassword}
                  onChange={e => setTgPassword(e.target.value)}
                  className="w-full bg-secondary/40 border border-border/80 rounded-xl pl-10 pr-3 py-2.5 text-xs font-medium focus:outline-none focus:border-red-500 transition-all font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 mt-2 bg-red-600 hover:bg-red-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-red-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <>Instant Telegram Auth <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>
        )}

        <div className="mt-6 pt-4 border-t border-border/40 text-center">
          <Link href="/" className="text-xs text-muted-foreground hover:text-red-400 font-bold transition-colors">
            ← Back to Region Selection
          </Link>
        </div>
      </div>
    </div>
  );
}
