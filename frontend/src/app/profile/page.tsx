'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useRouter } from 'next/navigation';
import { User as UserIcon, LogOut } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import MarketStatusBanner from '@/components/MarketStatusBanner';

export default function ProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await api.get('/auth/me');
      return res.data;
    },
  });

  const { data: trades } = useQuery({
    queryKey: ['trades'],
    queryFn: async () => {
      const res = await api.get('/trades');
      return res.data;
    },
  });

  const handleLogout = () => {
    localStorage.removeItem('lever_token');
    queryClient.clear();
    router.push('/login');
  };

  return (
    <div className="flex flex-col min-h-screen pb-16 md:pb-0">
      <MarketStatusBanner />
      
      <div className="p-4 md:p-8 flex-1 max-w-3xl mx-auto w-full">
        {isLoading ? (
          <div className="h-48 bg-white border border-gray-100 rounded-2xl animate-pulse"></div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden mb-8">
            <div className="p-8 text-center border-b border-gray-100">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-gray-100 text-gray-400 rounded-full mb-4">
                <UserIcon size={40} />
              </div>
              <h1 className="text-2xl font-bold">{user?.username}</h1>
              <p className="text-gray-500">{user?.email}</p>
              
              <div className="mt-6 flex justify-center">
                <div className="bg-gray-50 px-6 py-3 rounded-xl border border-gray-100">
                  <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-1">Available Cash</p>
                  <p className="text-xl font-bold text-[var(--color-brand)]">{formatCurrency(user?.cash_balance)}</p>
                </div>
              </div>
            </div>
            
            <div className="p-4">
              <button 
                onClick={handleLogout}
                className="w-full py-3 flex items-center justify-center space-x-2 text-red-500 hover:bg-red-50 rounded-xl font-medium transition-colors"
              >
                <LogOut size={18} />
                <span>Log Out</span>
              </button>
            </div>
          </div>
        )}

        <h2 className="text-xl font-bold mb-4">Trade History</h2>
        
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          {Array.isArray(trades) && trades.length > 0 ? (
            <ul className="divide-y divide-gray-100">
              {trades.map((trade: any) => {
                const isPositiveDelta = trade.cash_delta >= 0;
                return (
                  <li key={trade.id} className="p-4 flex items-center justify-between">
                    <div>
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="font-bold text-sm">{trade.symbol}</span>
                        <span className="text-[10px] px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full font-medium">
                          {trade.action.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">
                        {new Date(trade.executed_at).toLocaleString()} · {trade.quantity.toFixed(2)} shares @ {formatCurrency(trade.price_executed)}
                      </p>
                    </div>
                    <div className={`font-semibold ${isPositiveDelta ? 'text-[var(--color-gain)]' : 'text-gray-900'}`}>
                      {isPositiveDelta ? '+' : ''}{formatCurrency(trade.cash_delta)}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="p-8 text-center text-gray-500">
              No trade history yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
