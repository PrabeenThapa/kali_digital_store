"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { 
  Bolt, ArrowRight, ShieldCheck, Zap, Globe, MapPin, 
  Sparkles, CheckCircle2, QrCode, Lock, Flame, Shield,
  Award, Star, HeartHandshake, Eye
} from "lucide-react";

export default function RegionGatewayPage() {
  const router = useRouter();
  const [detectedCountry, setDetectedCountry] = useState<"nepal" | "worldwide">("worldwide");
  const [rememberChoice, setRememberChoice] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user already has a saved region preference
    const savedRegion = localStorage.getItem("region");
    const token = localStorage.getItem("token");

    // Try auto-detecting user's location via timezone
    try {
      const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (timeZone.toLowerCase().includes("kathmandu") || timeZone.toLowerCase().includes("nepal")) {
        setDetectedCountry("nepal");
      }
    } catch {
      // Fallback default
    }

    setLoading(false);
  }, []);

  const selectRegion = (region: "nepal" | "worldwide") => {
    if (rememberChoice) {
      localStorage.setItem("region", region);
    }
    if (region === "nepal") {
      router.push("/nepal");
    } else {
      router.push("/worldwide");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center">
        <div className="w-12 h-12 border-4 border-red-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-bold text-red-400 mt-4 tracking-widest uppercase">॥ ॐ क्रीं कालिकायै नमः ॥</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between relative overflow-hidden selection:bg-red-600 selection:text-white">
      {/* Mystical Vedic background glows & animated fire embers */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full bg-red-600/15 blur-[180px] pointer-events-none -translate-y-1/3 animate-pulse" />
      <div className="fixed bottom-0 right-10 w-[500px] h-[500px] rounded-full bg-amber-600/10 blur-[150px] pointer-events-none translate-y-1/3" />
      <div className="fixed top-1/3 left-10 w-[400px] h-[400px] rounded-full bg-purple-900/10 blur-[140px] pointer-events-none" />

      {/* Top Sacred Mantra Bar */}
      <div className="top-mantra-bar w-full bg-gradient-to-r from-red-950/80 via-red-900/40 to-red-950/80 border-b border-red-500/20 py-1.5 px-4 text-center">
        <p className="text-[11px] font-bold text-red-400 tracking-widest font-vedic uppercase flex items-center justify-center gap-2">
          <span>🔱</span>
          <span>॥ ॐ क्रीं कालिकायै नमः • दिव्य डिजिटल शक्ति एवं अचूक सुरक्षा ॥</span>
          <span>🔱</span>
        </p>
      </div>

      {/* Header */}
      <header className="p-6 flex items-center justify-between max-w-6xl mx-auto w-full relative z-10">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 rounded-full border-2 border-red-500/40 overflow-hidden shadow-lg shadow-red-600/30">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.png" alt="Kali Digital Store" className="w-full h-full object-cover" />
          </div>
          <div>
            <span className="font-black text-lg tracking-tight text-foreground flex items-center gap-1.5 font-vedic">
              KALI <span className="text-red-500">DIGITAL STORE</span>
            </span>
            <span className="text-[10px] text-muted-foreground block -mt-0.5 font-semibold">
              TRUSTED • FAST • RELIABLE
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-xs font-extrabold text-foreground hover:text-white px-5 py-2 rounded-full border border-red-500/40 bg-red-500/10 hover:bg-red-500/30 shadow-md shadow-red-500/20 transition-all flex items-center gap-1.5"
          >
            <Lock className="w-3.5 h-3.5 text-red-400" />
            <span>Sign In / Dashboard</span>
          </Link>
        </div>
      </header>

      {/* Main Hero & Region Gateway */}
      <main className="max-w-4xl mx-auto w-full px-4 py-6 relative z-10 flex flex-col items-center text-center">
        
        {/* Animated Maa Kaali Logo Emblem */}
        <div className="relative mb-6 group cursor-pointer">
          {/* Rotating Celestial Mandala Ring */}
          <div className="absolute inset-0 -m-6 rounded-full border border-red-500/30 border-dashed animate-mandala-slow pointer-events-none opacity-60" />
          <div className="absolute inset-0 -m-12 rounded-full border border-red-500/15 pointer-events-none opacity-40" />
          
          {/* Glowing Aura */}
          <div className="w-36 h-36 sm:w-44 sm:h-44 rounded-full p-1 bg-gradient-to-br from-red-500 via-rose-600 to-amber-600 shadow-[0_0_50px_rgba(225,29,72,0.6)] animate-kaali-pulse relative overflow-hidden flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img 
              src="/logo.png" 
              alt="Maa Kaali Logo" 
              className="w-full h-full object-cover rounded-full group-hover:scale-105 transition-transform duration-500" 
            />
          </div>
        </div>

        {/* Sanskrit Mythological Title & Slogan */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-red-500/40 bg-red-500/10 text-red-400 text-xs font-black mb-3 shadow-md shadow-red-500/10 uppercase tracking-wider">
          <Flame className="w-3.5 h-3.5 text-red-500 animate-pulse" />
          <span>त्रिशूल शक्ति डिजिटल स्टोर • दिव्य गति एवं अचूक सुरक्षा</span>
          <Flame className="w-3.5 h-3.5 text-red-500 animate-pulse" />
        </div>

        <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-tight mb-3 font-vedic text-transparent bg-clip-text bg-gradient-to-r from-white via-red-200 to-red-500">
          KALI DIGITAL STORE
        </h1>
        <p className="text-muted-foreground text-xs sm:text-sm max-w-xl mb-8 leading-relaxed font-medium">
          Instant Automated Dispatch for ChatGPT Plus, Claude 3.7, Gemini Pro, Canva, Capcut, VPNs & Dev APIs. Select your currency region to enter.
        </p>

        {/* 3 Pillars of Kaali Store (From Logo) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl mb-8">
          <div className="p-3 rounded-2xl bg-secondary/40 border border-red-500/20 flex items-center gap-2.5 text-left">
            <div className="w-9 h-9 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center shrink-0">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-black text-foreground">INSTANT DELIVERY</div>
              <div className="text-[10px] text-muted-foreground">क्षणभर में प्राप्ति • Auto 24/7</div>
            </div>
          </div>

          <div className="p-3 rounded-2xl bg-secondary/40 border border-red-500/20 flex items-center gap-2.5 text-left">
            <div className="w-9 h-9 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-black text-foreground">SECURE PAYMENT</div>
              <div className="text-[10px] text-muted-foreground">अभेद्य सुरक्षा • Zero Fraud</div>
            </div>
          </div>

          <div className="p-3 rounded-2xl bg-secondary/40 border border-red-500/20 flex items-center gap-2.5 text-left">
            <div className="w-9 h-9 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center shrink-0">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-black text-foreground">QUALITY GUARANTEED</div>
              <div className="text-[10px] text-muted-foreground">काल-चक्र वॉरंटी • 100% Genuine</div>
            </div>
          </div>
        </div>

        {/* Region Gateway Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-2xl mb-6">
          {/* 🇳🇵 Nepal Store */}
          <button
            onClick={() => selectRegion("nepal")}
            className={`glass-card p-7 rounded-3xl text-left border transition-all duration-300 relative group flex flex-col hover:-translate-y-1 hover:shadow-[0_12px_45px_rgba(225,29,72,0.35)] ${
              detectedCountry === "nepal"
                ? "border-red-500 ring-2 ring-red-500/30 bg-red-500/[0.06]"
                : "border-red-500/30 hover:border-red-500"
            }`}
          >
            {detectedCountry === "nepal" && (
              <span className="absolute top-4 right-4 text-[10px] font-black uppercase px-2.5 py-1 rounded-full bg-red-600 text-white shadow-sm flex items-center gap-1">
                <MapPin className="w-3 h-3" /> Detected Region
              </span>
            )}
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500/20 to-rose-600/20 border border-red-500/40 flex items-center justify-center text-3xl mb-4 group-hover:scale-110 transition-transform">
              🇳🇵
            </div>
            <div className="text-xl font-black text-foreground group-hover:text-red-400 transition-colors flex items-center gap-2 font-vedic">
              Nepal Store (NPR)
            </div>
            <p className="text-xs text-muted-foreground mt-2 mb-4 leading-relaxed flex-grow">
              Direct checkout in <b>Nepali Rupees (NPR)</b> via <b>eSewa, Fonepay, Khalti QR</b> & NPR Wallet. Instant local activation.
            </p>
            <div className="pt-3 border-t border-border/40 flex items-center justify-between text-xs font-black text-red-400">
              <span className="flex items-center gap-1.5"><span>🔱</span> Enter Nepal Portal</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1.5 transition-transform" />
            </div>
          </button>

          {/* 🌐 Worldwide Store */}
          <button
            onClick={() => selectRegion("worldwide")}
            className={`glass-card p-7 rounded-3xl text-left border transition-all duration-300 relative group flex flex-col hover:-translate-y-1 hover:shadow-[0_12px_45px_rgba(225,29,72,0.35)] ${
              detectedCountry === "worldwide"
                ? "border-red-500 ring-2 ring-red-500/30 bg-red-500/[0.06]"
                : "border-red-500/30 hover:border-red-500"
            }`}
          >
            {detectedCountry === "worldwide" && (
              <span className="absolute top-4 right-4 text-[10px] font-black uppercase px-2.5 py-1 rounded-full bg-red-600 text-white shadow-sm flex items-center gap-1">
                <Globe className="w-3 h-3" /> Global Portal
              </span>
            )}
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500/20 to-purple-600/20 border border-red-500/40 flex items-center justify-center text-3xl mb-4 group-hover:scale-110 transition-transform">
              🌐
            </div>
            <div className="text-xl font-black text-foreground group-hover:text-red-400 transition-colors flex items-center gap-2 font-vedic">
              Worldwide Store (USD)
            </div>
            <p className="text-xs text-muted-foreground mt-2 mb-4 leading-relaxed flex-grow">
              International store with global pricing in <b>USD ($)</b>. Multi-chain <b>CryptoPay, Bybit, Binance & USDT</b>.
            </p>
            <div className="pt-3 border-t border-border/40 flex items-center justify-between text-xs font-black text-red-400">
              <span className="flex items-center gap-1.5"><span>🔱</span> Enter Worldwide Portal</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1.5 transition-transform" />
            </div>
          </button>
        </div>

        {/* Remember choice toggle */}
        <label className="flex items-center gap-2.5 cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors font-medium">
          <input
            type="checkbox"
            checked={rememberChoice}
            onChange={(e) => setRememberChoice(e.target.checked)}
            className="w-4 h-4 rounded text-red-600 focus:ring-red-500 bg-secondary border-red-500/40"
          />
          Remember my regional preference for future visits
        </label>
      </main>

      {/* Trust Footer */}
      <footer className="p-6 border-t border-red-500/20 max-w-5xl mx-auto w-full flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground relative z-10">
        <div className="flex items-center gap-6 font-semibold">
          <span className="flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-red-400" /> 100% Verified Accounts</span>
          <span className="flex items-center gap-1.5"><Zap className="w-4 h-4 text-amber-400" /> Instant Telegram Delivery</span>
          <span className="flex items-center gap-1.5"><Lock className="w-4 h-4 text-red-400" /> Multi-Chain Crypto & QR</span>
        </div>
        <div className="font-vedic text-red-400/80">© {new Date().getFullYear()} KALI DIGITAL STORE. ALL RIGHTS RESERVED.</div>
      </footer>
    </div>
  );
}
