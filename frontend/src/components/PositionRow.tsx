'use client';

import { useState } from 'react';
import { formatCurrency, formatPercent } from '@/lib/utils';
import ClosePositionModal from './ClosePositionModal';

export default function PositionRow({ position }: { position: any }) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const isGain = position.unrealized_pnl >= 0;

  return (
    <>
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h4 className="font-bold">{position.symbol}</h4>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${position.side === 'LONG' ? 'bg-[var(--color-brand-light)] text-[var(--color-brand)]' : 'bg-[var(--color-loss-light)] text-[var(--color-loss)]'}`}>
              {position.side} {position.leverage}x
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Entry: {formatCurrency(position.entry_price)} · Curr: {formatCurrency(position.current_price)}
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <p className={`font-semibold ${isGain ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
              {isGain ? '+' : ''}{formatCurrency(position.unrealized_pnl)}
            </p>
            <p className={`text-xs ${isGain ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
              {isGain ? '+' : ''}{formatPercent(position.unrealized_pnl_percent)}
            </p>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200"
          >
            Close
          </button>
        </div>
      </div>

      {isModalOpen && (
        <ClosePositionModal 
          position={position} 
          onClose={() => setIsModalOpen(false)} 
        />
      )}
    </>
  );
}
