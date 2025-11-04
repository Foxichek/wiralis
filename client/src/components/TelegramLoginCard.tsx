import { Bot } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramUser) => void;
  }
}

export default function TelegramLoginCard({ delay = 0 }: { delay?: number }) {
  const [user, setUser] = useState<TelegramUser | null>(null);
  const loginContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.onTelegramAuth = (user: TelegramUser) => {
      setUser(user);
      localStorage.setItem('telegram_user', JSON.stringify(user));
    };

    const savedUser = localStorage.getItem('telegram_user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {
        console.error('Failed to parse saved user', e);
      }
    }

    return () => {
      delete window.onTelegramAuth;
    };
  }, []);

  useEffect(() => {
    if (loginContainerRef.current && !user && typeof window !== 'undefined') {
      const script = document.createElement('script');
      script.async = true;
      script.src = 'https://telegram.org/js/telegram-widget.js?22';
      script.setAttribute('data-telegram-login', 'wiralis_bot');
      script.setAttribute('data-size', 'large');
      script.setAttribute('data-onauth', 'onTelegramAuth(user)');
      script.setAttribute('data-request-access', 'write');
      
      loginContainerRef.current.appendChild(script);
    }
  }, [user]);

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('telegram_user');
    window.location.reload();
  };

  return (
    <div
      className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-5 md:p-6 hover-elevate transition-all duration-300"
      style={{ animationDelay: `${delay}ms` }}
      data-testid="card-benefit-telegram-login"
    >
      <div className="flex flex-col items-center text-center space-y-3 md:space-y-4">
        <div className="w-12 h-12 md:w-14 md:h-14 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
          <Bot className="w-6 h-6 md:w-7 md:h-7 text-white" />
        </div>
        <h3 className="text-base md:text-lg font-semibold text-white">
          Вход через WIRALIS-бот
        </h3>
        <p className="text-white/70 text-sm leading-relaxed">
          Быстрая авторизация через Telegram без лишних действий
        </p>
        
        {user ? (
          <div className="w-full space-y-3 pt-2">
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
              {user.photo_url && (
                <img 
                  src={user.photo_url} 
                  alt={user.first_name}
                  className="w-12 h-12 rounded-full mx-auto mb-2"
                />
              )}
              <p className="text-white font-medium text-sm">
                Привет, {user.first_name}!
              </p>
              {user.username && (
                <p className="text-white/60 text-xs mt-1">
                  @{user.username}
                </p>
              )}
            </div>
            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white text-sm font-medium transition-all duration-300"
              data-testid="button-logout"
            >
              Выйти
            </button>
          </div>
        ) : (
          <div className="pt-2 flex flex-col items-center gap-3 w-full">
            <div 
              ref={loginContainerRef}
              className="flex justify-center w-full"
              data-testid="container-telegram-login"
            />
            <p className="text-white/50 text-xs">
              Войдите заранее для доступа к функциям
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
