import React from 'react';
import {
  Bot,
  Brain,
  Sparkles,
  Zap,
  Film,
  Music,
  Tv,
  Palette,
  Scissors,
  Briefcase,
  ShieldCheck,
  Code2,
  Mail,
  KeyRound,
  Cpu,
  Package
} from 'lucide-react';

interface ProductIconProps {
  name: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export function ProductIcon({ name, size = 'md', className = '' }: ProductIconProps) {
  const n = (name || '').toLowerCase();

  const iconCls = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : size === 'xl' ? 'w-10 h-10' : 'w-6 h-6';

  // AI & Chatbots
  if (n.includes('claude')) {
    return <Brain className={`${iconCls} text-amber-400 ${className}`} />;
  }
  if (n.includes('gemini')) {
    return <Sparkles className={`${iconCls} text-sky-400 ${className}`} />;
  }
  if (n.includes('grok')) {
    return <Zap className={`${iconCls} text-yellow-400 ${className}`} />;
  }
  if (n.includes('deepseek')) {
    return <Cpu className={`${iconCls} text-cyan-400 ${className}`} />;
  }
  if (n.includes('chatgpt') || n.includes('gpt') || n.includes('openai') || n.includes('perplexity') || n.includes('copilot') || n.includes('mistral') || n.includes('manus') || n.includes('kiro')) {
    return <Bot className={`${iconCls} text-emerald-400 ${className}`} />;
  }

  // Streaming & Media
  if (n.includes('spotify') || n.includes('music') || n.includes('suno') || n.includes('udio')) {
    return <Music className={`${iconCls} text-emerald-400 ${className}`} />;
  }
  if (n.includes('youtube')) {
    return <Tv className={`${iconCls} text-rose-500 ${className}`} />;
  }
  if (n.includes('netflix') || n.includes('prime') || n.includes('disney') || n.includes('hulu') || n.includes('hbo') || n.includes('twitch') || n.includes('crunchyroll') || n.includes('peacock') || n.includes('streaming')) {
    return <Film className={`${iconCls} text-rose-400 ${className}`} />;
  }

  // Creative & Design
  if (n.includes('canva') || n.includes('adobe') || n.includes('figma') || n.includes('midjourney') || n.includes('runway') || n.includes('leonardo') || n.includes('dalle') || n.includes('picsart') || n.includes('meitu') || n.includes('gamma') || n.includes('heygen')) {
    return <Palette className={`${iconCls} text-pink-400 ${className}`} />;
  }
  if (n.includes('capcut') || n.includes('video') || n.includes('pixverse') || n.includes('editor')) {
    return <Scissors className={`${iconCls} text-sky-400 ${className}`} />;
  }

  // Dev & Code Tools
  if (n.includes('cursor') || n.includes('replit') || n.includes('railway') || n.includes('supabase') || n.includes('codex') || n.includes('lovable') || n.includes('posthog') || n.includes('warp') || n.includes('linear')) {
    return <Code2 className={`${iconCls} text-indigo-400 ${className}`} />;
  }

  // VPN & Security
  if (n.includes('vpn') || n.includes('nord') || n.includes('surfshark') || n.includes('proton') || n.includes('express') || n.includes('avira') || n.includes('hma')) {
    return <ShieldCheck className={`${iconCls} text-emerald-400 ${className}`} />;
  }

  // Productivity & Office
  if (n.includes('notion') || n.includes('office') || n.includes('microsoft') || n.includes('linkedin') || n.includes('quillbot') || n.includes('grammarly') || n.includes('zapier') || n.includes('n8n') || n.includes('chatprd')) {
    return <Briefcase className={`${iconCls} text-purple-400 ${className}`} />;
  }

  // Email & Accounts
  if (n.includes('mail') || n.includes('gmail') || n.includes('email') || n.includes('inbox') || n.includes('hotmail')) {
    return <Mail className={`${iconCls} text-blue-400 ${className}`} />;
  }

  // Keys & Licenses
  if (n.includes('key') || n.includes('license') || n.includes('token') || n.includes('api')) {
    return <KeyRound className={`${iconCls} text-amber-400 ${className}`} />;
  }

  return <Package className={`${iconCls} text-purple-400 ${className}`} />;
}
