import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api-client';

export interface FinancialPerformance {
  property_id: string;
  ytd_rent: number;
  ytd_expenses: number;
  ytd_profit_loss: number;
  cumulative_rent: number;
  cumulative_expenses: number;
  cumulative_profit_loss: number;
  cash_on_cash: number | null;
  units: Array<{
    unit_id: string;
    ytd_profit_loss: number;
    cumulative_profit_loss: number;
  }> | null;
  last_calculated_at: string;
}

export function useFinancialPerformance(propertyId: string, unitId?: string) {
  return useQuery({
    queryKey: ['financial-performance', propertyId, unitId],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (unitId) {
        params.append('unit_id', unitId);
      }
      
      const response = await apiClient.get<FinancialPerformance>(
        `/financial-performance/${propertyId}?${params.toString()}`
      );
      return response;
    },
    staleTime: 30000, // Cache for 30 seconds
    gcTime: 60000,
  });
}

