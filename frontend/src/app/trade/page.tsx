'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Search } from 'lucide-react';
import MarketStatusBanner from '@/components/MarketStatusBanner';
import TradingForm from '@/components/TradingForm';
import { formatCurrency, formatPercent } from '@/lib/utils';

export default function TradePage() {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  // Simple debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const { data: stocks, isLoading } = useQuery({
    queryKey: ['stocks', debouncedSearch],
    queryFn: async () => {
      const res = await api.get(`/stocks${debouncedSearch ? `?search=${debouncedSearch}` : ''}`);
      return res.data;
    },
  });

  return (
    <div className="flex flex-col min-h-screen relative pb-16 md:pb-0">
      <MarketStatusBanner />
      
      <div className="p-4 md:p-8 flex-1 max-w-5xl mx-auto w-full flex flex-col md:flex-row gap-8">
        
        {/* Left column: Search and List */}
        <div className={`flex-1 ${selectedSymbol ? 'hidden md:block' : 'block'}`}>
          <div className="mb-6 relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search size={20} className="text-gray-400" />
            </div>
            <input 
              type="text" 
              placeholder="Search stocks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-[var(--color-brand)] focus:border-transparent outline-none"
            />
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="h-16 bg-white border border-gray-100 animate-pulse rounded-xl"></div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {stocks?.map((stock: any) => (
                <div 
                  key={stock.symbol}
                  onClick={() => setSelectedSymbol(stock.symbol)}
                  className={`bg-white p-4 rounded-xl shadow-sm border border-gray-100 cursor-pointer hover:border-[var(--color-brand)] transition-colors flex items-center justify-between ${selectedSymbol === stock.symbol ? 'ring-2 ring-[var(--color-brand)] border-transparent' : ''}`}
                >
                  <div>
                    <h4 className="font-bold">{stock.symbol}</h4>
                    <p className="text-xs text-gray-500">{stock.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatCurrency(stock.current_price || 0)}</p>
                    <p className={`text-xs ${(stock.change_percent || 0) >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                      {(stock.change_percent || 0) >= 0 ? '+' : ''}{formatPercent(stock.change_percent || 0)}
                    </p>
                  </div>
                </div>
              ))}
              {stocks?.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  No stocks found.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right column: Trade Form */}
        {selectedSymbol && (
          <div className="w-full md:w-[400px] shrink-0 md:sticky md:top-8 self-start">
            <TradingForm 
              symbol={selectedSymbol} 
              onBack={() => setSelectedSymbol(null)} 
            />
          </div>
        )}
      </div>
    </div>
  );
}
