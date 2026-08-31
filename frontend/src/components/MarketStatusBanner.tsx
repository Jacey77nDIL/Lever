'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export default function MarketStatusBanner() {
  const { data: statusData } = useQuery({
    queryKey: ['market-status'],
    queryFn: async () => {
      const res = await api.get('/market/status');
      return res.data;
    },
    staleTime: 60 * 1000, // 1 min check
  });

  const isOpen = statusData?.status === 'open';

  return (
    <div className={`w-full py-2 px-4 text-center text-sm font-medium ${isOpen ? 'bg-[var(--color-brand-light)] text-[var(--color-brand)]' : 'bg-gray-100 text-gray-500'}`}>
      {isOpen ? 'Market Open · closes 4:00 PM WAT' : 'Market Closed · opens Monday 9:00 AM WAT'}
    </div>
  );
}
