"use client";

import { useEffect, useRef } from 'react';

interface TelegramAuthProps {
  botName: string;
  onAuth: (user: any) => void;
}

export default function TelegramLoginWidget({ botName, onAuth }: TelegramAuthProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    
    // Only load if it hasn't been loaded in this container yet
    if (containerRef.current.children.length === 0) {
      // Setup global callback
      (window as any).onTelegramAuth = (user: any) => {
        onAuth(user);
      };

      const script = document.createElement('script');
      script.src = 'https://telegram.org/js/telegram-widget.js?22';
      script.async = true;
      script.setAttribute('data-telegram-login', botName);
      script.setAttribute('data-size', 'large');
      script.setAttribute('data-radius', '12');
      script.setAttribute('data-request-access', 'write');
      script.setAttribute('data-userpic', 'false');
      script.setAttribute('data-onauth', 'onTelegramAuth(user)');
      
      containerRef.current.appendChild(script);
    }
  }, [botName, onAuth]);

  return <div ref={containerRef} className="telegram-login-container min-h-[40px] flex justify-center" />;
}
