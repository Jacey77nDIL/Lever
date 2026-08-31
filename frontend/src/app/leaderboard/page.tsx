'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Trophy } from 'lucide-react';
import { formatCurrency, formatPercent } from '@/lib/utils';
import MarketStatusBanner from '@/components/MarketStatusBanner';

export default function LeaderboardPage() {
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await api.get('/auth/me');
      return res.data;
    },
  });

  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: async () => {
      const res = await api.get('/leaderboard?window=all');
      return res.data;
    },
  });

  return (
    <div className="flex flex-col min-h-screen pb-16 md:pb-0">
      <MarketStatusBanner />
      
      <div className="p-4 md:p-8 flex-1 max-w-3xl mx-auto w-full">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[var(--color-brand-light)] text-[var(--color-brand)] rounded-full mb-4">
            <Trophy size={32} />
          </div>
          <h1 className="text-2xl font-bold">Top Traders</h1>
          <p className="text-gray-500">Ranked by total portfolio equity</p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-16 bg-white rounded-xl border border-gray-100 animate-pulse"></div>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
                  <th className="px-6 py-4 font-medium">Rank</th>
                  <th className="px-6 py-4 font-medium">Trader</th>
                  <th className="px-6 py-4 font-medium text-right">Total Equity</th>
                  <th className="px-6 py-4 font-medium text-right">Return</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {leaderboard?.map((entry: any) => {
                  const isMe = user?.username === entry.username;
                  const ret = ((entry.total_equity - 10000) / 10000) * 100;
                  
                  return (
                    <tr key={entry.username} className={`transition-colors hover:bg-gray-50 ${isMe ? 'bg-[var(--color-brand-light)]/30' : ''}`}>
                      <td className="px-6 py-4">
                        <span className={`font-bold ${entry.rank <= 3 ? 'text-[var(--color-brand)]' : 'text-gray-500'}`}>
                          #{entry.rank}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900">{entry.username}</span>
                          {isMe && <span className="text-[10px] bg-[var(--color-brand)] text-white px-2 py-0.5 rounded-full">You</span>}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right font-semibold">
                        {formatCurrency(entry.total_equity)}
                      </td>
                      <td className={`px-6 py-4 text-right font-medium ${ret >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                        {ret >= 0 ? '+' : ''}{formatPercent(ret)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            
            {leaderboard?.length === 0 && (
              <div className="p-8 text-center text-gray-500">
                Leaderboard is empty. Be the first to trade!
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
