'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { X } from 'lucide-react';

export default function ClosePositionModal({ position, onClose }: { position: any; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [quantityStr, setQuantityStr] = useState(String(position.quantity));

  const closeMutation = useMutation({
    mutationFn: async (quantity: number) => {
      await api.post(`/positions/${position.id}/close`, { quantity_to_close: quantity });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      onClose();
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Failed to close position');
    }
  });

  const quantityToClose = parseInt(quantityStr) || 0;
  
  // Estimate realized PnL
  // NOTE: This uses current_price without spread for simplicity on the client side preview.
  const priceDiff = position.side === 'LONG' 
    ? (position.current_price - position.entry_price)
    : (position.entry_price - position.current_price);
  const estimatedRealized = priceDiff * quantityToClose;
  
  // Margin returned is proportional to the fraction of position being closed
  const closeFraction = position.quantity > 0 ? (quantityToClose / position.quantity) : 0;
  const marginReturned = position.margin_used * closeFraction;
  
  const isInvalidQuantity = quantityToClose <= 0 || quantityToClose > position.quantity;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl w-full max-w-md overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b border-gray-100">
          <h3 className="font-semibold text-lg">Close {position.symbol}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full text-gray-500">
            <X size={20} />
          </button>
        </div>
        
        <div className="p-6 space-y-6">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-500">Quantity (Shares) to Close</span>
              <span className="font-medium text-gray-500">Max: {position.quantity}</span>
            </div>
            <input 
              type="number"
              min="1"
              max={position.quantity}
              step="1"
              value={quantityStr}
              onKeyDown={(e) => ["e", "E", "+", "-", "."].includes(e.key) && e.preventDefault()}
              onChange={(e) => setQuantityStr(e.target.value)}
              className={`w-full px-4 py-3 bg-gray-50 border rounded-xl focus:ring-2 focus:ring-[var(--color-brand)] outline-none ${isInvalidQuantity ? 'border-red-300 focus:ring-red-500' : 'border-gray-200 focus:border-transparent'}`}
            />
            {isInvalidQuantity && quantityToClose > 0 && (
              <p className="text-xs text-red-500 mt-1">Quantity cannot exceed {position.quantity}</p>
            )}
            <div className="flex justify-between mt-3">
              {[0.25, 0.5, 0.75, 1].map(frac => {
                const amount = Math.round(position.quantity * frac);
                return (
                  <button 
                    key={frac}
                    onClick={() => setQuantityStr(String(amount))}
                    className={`text-xs px-2 py-1 rounded ${quantityToClose === amount ? 'bg-[var(--color-brand)] text-white' : 'bg-gray-100 text-gray-600'}`}
                  >
                    {frac === 1 ? 'MAX' : `${frac * 100}%`}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="bg-gray-50 p-4 rounded-xl space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Margin Returned</span>
              <span className="font-medium">{formatCurrency(marginReturned)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Est. Realized PnL</span>
              <span className={`font-medium ${estimatedRealized >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                {estimatedRealized >= 0 ? '+' : ''}{formatCurrency(estimatedRealized)}
              </span>
            </div>
            <div className="pt-2 border-t border-gray-200 flex justify-between font-bold">
              <span>Total Credit</span>
              <span>{formatCurrency(marginReturned + estimatedRealized)}</span>
            </div>
          </div>

          <button 
            onClick={() => closeMutation.mutate(quantityToClose)}
            disabled={closeMutation.isPending || isInvalidQuantity}
            className="w-full py-3 bg-[var(--color-brand)] hover:opacity-90 disabled:opacity-50 text-white rounded-xl font-semibold"
          >
            {closeMutation.isPending ? 'Closing...' : 'Confirm Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
