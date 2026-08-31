'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import MarketStatusBanner from '@/components/MarketStatusBanner';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useRouter } from 'next/navigation';
import { Plus } from 'lucide-react';
import Link from 'next/link';
import { formatCurrency } from '@/lib/utils';
import PositionRow from '@/components/PositionRow';

export default function Dashboard() {
  const router = useRouter();

  const { data: portfolio, isLoading: portLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: async () => {
      const res = await api.get('/portfolio');
      return res.data;
    },
  });

  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: async () => {
      const res = await api.get('/positions?status=OPEN');
      return res.data;
    },
  });

  const { data: marketStatus } = useQuery({
    queryKey: ['market-status'],
    queryFn: async () => {
      const res = await api.get('/market/status');
      return res.data;
    },
  });

  return (
    <div className="flex flex-col min-h-screen relative pb-16 md:pb-0">
      <MarketStatusBanner />
      
      <div className="p-4 md:p-8 flex-1 space-y-8 max-w-5xl mx-auto w-full">
        {/* Portfolio Overview */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Portfolio</h2>
          {portLoading ? (
            <div className="h-64 bg-gray-100 animate-pulse rounded-xl"></div>
          ) : (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
              <div className="mb-6">
                <p className="text-sm text-gray-500">Total Equity</p>
                <h3 className="text-3xl font-bold">{formatCurrency(portfolio?.total_equity || 0)}</h3>
                <div className="flex space-x-4 mt-2 text-sm">
                  <p><span className="text-gray-500">Cash:</span> {formatCurrency(portfolio?.cash_balance || 0)}</p>
                  <p><span className="text-gray-500">Positions:</span> {formatCurrency(portfolio?.positions_value || 0)}</p>
                </div>
              </div>
              
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={portfolio?.history || []}>
                    <XAxis 
                      dataKey="captured_at" 
                      hide 
                    />
                    <YAxis 
                      domain={['auto', 'auto']} 
                      hide 
                    />
                    <Tooltip 
                      formatter={(value: any) => formatCurrency(value)}
                      labelFormatter={() => ''}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="total_equity" 
                      stroke="var(--color-brand)" 
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </section>

        {/* Positions */}
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Open Positions</h2>
          {posLoading ? (
            <div className="space-y-2">
              <div className="h-16 bg-gray-100 animate-pulse rounded-lg"></div>
              <div className="h-16 bg-gray-100 animate-pulse rounded-lg"></div>
            </div>
          ) : positions?.length > 0 ? (
            <div className="space-y-3">
              {positions.map((pos: any) => (
                <PositionRow key={pos.id} position={pos} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-white rounded-2xl border border-gray-100 border-dashed">
              <p className="text-gray-500 mb-4">No open positions</p>
              <Link href="/trade" className="inline-flex items-center px-4 py-2 bg-[var(--color-brand)] text-white rounded-full text-sm font-medium hover:opacity-90">
                Explore Market
              </Link>
            </div>
          )}
        </section>
      </div>

      {/* Floating Action Button */}
      <button 
        onClick={() => router.push('/trade')}
        disabled={marketStatus?.status === 'closed'}
        title={marketStatus?.status === 'closed' ? "Market is closed" : "New Trade"}
        className="fixed bottom-20 md:bottom-8 right-4 md:right-8 w-14 h-14 bg-[var(--color-brand)] disabled:bg-gray-400 text-white rounded-full flex items-center justify-center shadow-lg hover:shadow-xl transition-all z-40"
      >
        <Plus size={24} />
      </button>
    </div>
  );
}
