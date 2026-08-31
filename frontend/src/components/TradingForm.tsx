'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export default function TradingForm({ symbol, onBack }: { symbol: string; onBack: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [side, setSide] = useState<'LONG' | 'SHORT'>('LONG');
  const [leverage, setLeverage] = useState(1);
  const [sharesStr, setSharesStr] = useState('');
  
  const { data: stock, isLoading: stockLoading } = useQuery({
    queryKey: ['stock', symbol],
    queryFn: async () => {
      const res = await api.get(`/stocks/${symbol}`);
      return res.data;
    },
  });

  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await api.get('/auth/me');
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

  const tradeMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await api.post('/positions/open', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      router.push('/');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Trade failed');
    }
  });

  if (stockLoading || !stock) {
    return <div className="bg-white p-6 rounded-2xl border border-gray-100 h-[500px] animate-pulse"></div>;
  }

  const isMarketClosed = marketStatus?.status !== 'open';
  const shares = parseInt(sharesStr) || 0;
  
  // Simple spread estimation for UI preview (backend uses exact same logic)
  const spreads: any = {
    BLUE_CHIP: 0.0015,
    ESTABLISHED: 0.0035,
    VOLATILE: 0.0075,
    RESTRICTED: 0.0150
  };
  const spread = spreads[stock.liquidity_tier] || 0.015;
  const priceMultiplier = side === 'LONG' ? (1 + spread/2) : (1 - spread/2);
  const estExecutionPrice = Number(stock.current_price) * priceMultiplier;
  
  const notional = shares * estExecutionPrice;
  const marginRequired = notional / leverage;
  const cashBalance = user?.cash_balance || 0;
  const hasInsufficientCash = marginRequired > cashBalance;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (hasInsufficientCash || isMarketClosed || shares <= 0) return;
    
    tradeMutation.mutate({
      symbol: stock.symbol,
      side,
      leverage,
      quantity: shares
    });
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden relative">
      <div className="p-4 border-b border-gray-100 flex items-center relative z-20 bg-white">
        <button onClick={onBack} className="md:hidden mr-3 text-gray-500">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h3 className="font-bold text-lg">{stock.symbol}</h3>
          <p className="text-xs text-gray-500">{stock.name}</p>
        </div>
      </div>

      <div className="p-4 bg-gray-50 flex justify-between items-center text-sm">
        <span className="px-2 py-1 bg-white border border-gray-200 rounded-md font-medium text-gray-700">
          {stock.liquidity_tier.replace('_', ' ')}
        </span>
        <span className="text-gray-500">
          Max {Number(stock.max_leverage).toFixed(2)}x Leverage
        </span>
      </div>

      <form onSubmit={handleSubmit} className={`p-6 space-y-6 ${isMarketClosed ? 'opacity-50 pointer-events-none' : ''}`}>
        
        {/* Side Toggle */}
        <div className="flex bg-gray-100 p-1 rounded-xl">
          <button 
            type="button"
            onClick={() => setSide('LONG')}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${side === 'LONG' ? 'bg-white shadow-sm text-[var(--color-gain)]' : 'text-gray-500'}`}
          >
            Long
          </button>
          <button 
            type="button"
            onClick={() => setSide('SHORT')}
            disabled={!stock.shortable}
            title={!stock.shortable ? "Not shortable in this liquidity tier" : ""}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 ${side === 'SHORT' ? 'bg-white shadow-sm text-[var(--color-loss)]' : 'text-gray-500'}`}
          >
            Short
          </button>
        </div>

        {/* Leverage Slider */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium text-gray-700">Leverage</span>
            <span className="font-bold">{leverage}x</span>
          </div>
          <input 
            type="range"
            min="1"
            max={stock.max_leverage}
            step="0.1"
            value={leverage}
            onChange={(e) => setLeverage(parseFloat(e.target.value))}
            className="w-full accent-[var(--color-brand)]"
          />
        </div>

        {/* Quantity Input */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium text-gray-700">Quantity (Shares)</span>
            <span className="text-gray-500">Avail: {formatCurrency(cashBalance)}</span>
          </div>
          <input 
            type="number"
            min="1"
            step="1"
            placeholder="0"
            value={sharesStr}
            onKeyDown={(e) => ["e", "E", "+", "-", "."].includes(e.key) && e.preventDefault()}
            onChange={(e) => setSharesStr(e.target.value)}
            className={`w-full px-4 py-3 bg-gray-50 border rounded-xl focus:ring-2 focus:ring-[var(--color-brand)] outline-none ${hasInsufficientCash ? 'border-red-300 focus:ring-red-500' : 'border-gray-200 focus:border-transparent'}`}
          />
          {hasInsufficientCash && (
            <p className="text-xs text-red-500 mt-1">Margin required exceeds available cash</p>
          )}
        </div>

        {/* Summary */}
        <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm border border-gray-100">
          <div className="flex justify-between">
            <span className="text-gray-500">Est. Execution Price</span>
            <span className="font-medium">{formatCurrency(estExecutionPrice)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Notional Exposure</span>
            <span className="font-medium">{formatCurrency(notional)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 font-medium">Margin Required</span>
            <span className="font-bold">{formatCurrency(marginRequired)}</span>
          </div>
        </div>

        <button 
          type="submit"
          disabled={tradeMutation.isPending || hasInsufficientCash || shares <= 0}
          className={`w-full py-3.5 rounded-xl font-bold text-white transition-opacity disabled:opacity-50 ${side === 'LONG' ? 'bg-[var(--color-gain)]' : 'bg-[var(--color-loss)]'}`}
        >
          {tradeMutation.isPending ? 'Executing...' : `Open ${side} Position`}
        </button>
      </form>
      
      {isMarketClosed && (
        <div className="absolute inset-0 bg-white/50 backdrop-blur-[1px] flex items-center justify-center p-6 z-10">
          <div className="bg-white p-4 rounded-xl shadow-lg text-center max-w-xs border border-gray-100">
            <p className="font-bold text-gray-800 mb-1">Market is closed</p>
            <p className="text-sm text-gray-500">Trading is only available Monday–Friday, 9:00 AM – 4:00 PM WAT.</p>
          </div>
        </div>
      )}
    </div>
  );
}
