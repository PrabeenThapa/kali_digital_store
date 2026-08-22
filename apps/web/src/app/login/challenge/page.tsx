"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  ShieldCheck,
  Copy,
  Check,
  Send,
  RefreshCw,
  ExternalLink,
  Lock,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

function ChallengeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const initialCode = searchParams.get("code") || "";
  const initialC = searchParams.get("c") || "";

  const [code, setCode] = useState<string>(initialCode);
  const [cToken, setCToken] = useState<string>(initialC);
  const [botUsername, setBotUsername] = useState<string>("kali_store_bot");
  const [status, setStatus] = useState<"loading" | "waiting" | "approved" | "expired" | "denied">("loading");
  const [copied, setCopied] = useState(false);
  const [countdown, setCountdown] = useState(300);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize or fetch challenge
  const initChallenge = async () => {
    setStatus("loading");
    try {
      if (initialCode && initialC) {
        setCode(initialCode);
        setCToken(initialC);
        setStatus("waiting");
      } else {
        const res = await api.post("/auth/challenge/create");
        setCode(res.data.code);
        setCToken(res.data.c);
        if (res.data.bot_username) {
          setBotUsername(res.data.bot_username);
        }
        setCountdown(res.data.expires_in || 300);
        setStatus("waiting");

        // Update URL query parameters seamlessly
        const newUrl = `/login/challenge?c=${encodeURIComponent(res.data.c)}&code=${encodeURIComponent(res.data.code)}`;
        window.history.replaceState(null, "", newUrl);
      }
    } catch (err) {
      console.error("Failed to create challenge", err);
      setStatus("expired");
    }
  };

  useEffect(() => {
    initChallenge();
  }, [initialCode, initialC]);

  // Polling loop
  useEffect(() => {
    if (status !== "waiting" || !code || !cToken) {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      return;
    }

    const checkStatus = async () => {
      try {
        const res = await api.get("/auth/challenge/poll", {
          params: { code, c: cToken },
        });

        if (res.data.status === "approved" && res.data.access_token) {
          setStatus("approved");
          localStorage.setItem("token", res.data.access_token);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

          // Check if admin to decide redirect target
          setTimeout(async () => {
            try {
              const meRes = await api.get("/user/me");
              if (meRes.data?.is_admin) {
                router.push("/admin");
              } else {
                router.push("/dashboard");
              }
            } catch {
              router.push("/dashboard");
            }
          }, 800);
        } else if (res.data.status === "expired") {
          setStatus("expired");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        } else if (res.data.status === "denied") {
          setStatus("denied");
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      } catch (err) {
        console.error("Poll error:", err);
      }
    };

    pollIntervalRef.current = setInterval(checkStatus, 1800);
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [status, code, cToken, router]);

  // Countdown timer
  useEffect(() => {
    if (status !== "waiting") return;
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setStatus("expired");
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [status]);

  const copyCode = () => {
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formattedCode = code.length === 8 ? `${code.slice(0, 4)} ${code.slice(4)}` : code;
  const botDeepLink = `https://t.me/${botUsername}?start=login_${code}`;

  return (
    <div className="min-h-screen bg-[#0c0d14] text-white flex flex-col items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-primary/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[300px] h-[300px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Top Brand / Nav */}
      <div className="w-full max-w-md flex items-center justify-between mb-8 z-10">
        <Link href="/" className="flex items-center gap-2.5 font-bold text-lg tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-primary flex items-center justify-center text-white shadow-lg shadow-primary/25">
            ⚡
          </div>
          <span>KALI<span className="text-primary font-black">STORE</span></span>
        </Link>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold tracking-wider uppercase px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-muted-foreground">
            CONFIRM LOGIN
          </span>
          <span className="text-xs text-muted-foreground hover:text-white cursor-pointer transition-colors px-2 py-1">
            English
          </span>
        </div>
      </div>

      {/* Main Challenge Card */}
      <div className="w-full max-w-md bg-[#13141f]/90 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl shadow-black/60 z-10 space-y-6">
        
        {/* Status: Approved */}
        {status === "approved" ? (
          <div className="text-center py-8 space-y-4 animate-in fade-in zoom-in-95 duration-300">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/20">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold">Login Confirmed!</h2>
            <p className="text-sm text-muted-foreground">
              Your Telegram identity has been verified. Redirecting to your dashboard...
            </p>
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mt-4" />
          </div>
        ) : status === "expired" ? (
          /* Status: Expired */
          <div className="text-center py-6 space-y-5 animate-in fade-in duration-300">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
              <AlertCircle className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Challenge Expired</h2>
              <p className="text-sm text-muted-foreground mt-1.5">
                This verification code has timed out for security.
              </p>
            </div>
            <button
              onClick={initChallenge}
              className="w-full py-3.5 bg-primary hover:bg-primary/90 text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/25 transition-all flex items-center justify-center gap-2 text-sm"
            >
              <RefreshCw className="w-4 h-4" /> Generate New Code
            </button>
          </div>
        ) : status === "denied" ? (
          /* Status: Denied */
          <div className="text-center py-6 space-y-5 animate-in fade-in duration-300">
            <div className="w-14 h-14 rounded-2xl bg-destructive/15 text-destructive border border-destructive/30 flex items-center justify-center mx-auto">
              <Lock className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Login Denied</h2>
              <p className="text-sm text-muted-foreground mt-1.5">
                The login request was denied in Telegram.
              </p>
            </div>
            <button
              onClick={initChallenge}
              className="w-full py-3.5 bg-secondary hover:bg-secondary/80 text-foreground font-bold rounded-xl transition-all flex items-center justify-center gap-2 text-sm"
            >
              <RefreshCw className="w-4 h-4" /> Try Again
            </button>
          </div>
        ) : (
          /* Status: Waiting for Confirmation */
          <div className="space-y-6 animate-in fade-in duration-300">
            <div>
              <div className="text-xs font-bold uppercase tracking-widest text-primary mb-1 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> Direct Telegram Auth
              </div>
              <h1 className="text-2xl font-extrabold tracking-tight">Confirm login</h1>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Open <span className="text-white font-semibold">@{botUsername}</span> and tap{" "}
                <span className="text-primary font-semibold">Confirm login</span>. This page updates automatically.
              </p>
            </div>

            {/* Stylized Code Box */}
            <div className="relative bg-[#0c0d14]/90 border-2 border-primary/40 rounded-2xl p-6 text-center shadow-inner group hover:border-primary transition-all">
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground block mb-1">
                Your Confirmation Code
              </span>
              <div className="font-mono text-3xl sm:text-4xl font-black tracking-wider text-white select-all">
                {formattedCode || "••••••••"}
              </div>

              {/* Copy button */}
              <button
                onClick={copyCode}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-semibold text-muted-foreground hover:text-white transition-colors border border-white/5"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" /> Copy code
                  </>
                )}
              </button>
            </div>

            {/* Direct Open Telegram Bot CTA */}
            <div className="space-y-3">
              <a
                href={botDeepLink}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3.5 bg-gradient-to-r from-indigo-500 to-primary hover:opacity-95 text-white font-bold rounded-xl shadow-lg shadow-primary/25 transition-all flex items-center justify-center gap-2.5 text-sm"
              >
                <Send className="w-4 h-4" /> Open Telegram Bot
              </a>

              {/* Live Polling Status bar */}
              <div className="flex items-center justify-between text-xs text-muted-foreground px-2 pt-1">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                  <span>Waiting for confirmation...</span>
                </div>
                <span className="font-mono text-[11px] text-muted-foreground">
                  Expires in {Math.floor(countdown / 60)}:{(countdown % 60).toString().padStart(2, "0")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Alternative Fallback Options */}
        <div className="pt-4 border-t border-white/10 flex flex-col items-center gap-2.5 text-xs text-muted-foreground">
          <Link
            href="/login?tab=telegram"
            className="hover:text-white transition-colors flex items-center gap-1.5 font-medium"
          >
            <Lock className="w-3.5 h-3.5" /> Use Telegram ID and password
          </Link>
          <Link
            href="/login?tab=signin"
            className="hover:text-white transition-colors flex items-center gap-1.5 font-medium text-[11px]"
          >
            Sign in with email instead →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ChallengePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#0c0d14] flex items-center justify-center">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <ChallengeContent />
    </Suspense>
  );
}
