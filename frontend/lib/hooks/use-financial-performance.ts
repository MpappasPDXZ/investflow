import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api-client';

export interface FinancialPerformance {
  property_id: string;
  ytd_total_revenue?: number;  // Total revenue including deposits
  ytd_rent: number;  // IRS revenue only (excludes deposits)
  ytd_expenses: number;
  ytd_profit_loss: number;
  ytd_piti: number;
  ytd_tax: number;
  ytd_utilities: number;
  ytd_maintenance: number;
  ytd_capex: number;
  ytd_insurance: number;
  ytd_property_management: number;
  ytd_other: number;
  cumulative_rent: number;
  cumulative_expenses: number;
  cumulative_profit_loss: number;
  cumulative_piti: number;
  cumulative_tax: number;
  cumulative_utilities: number;
  cumulative_maintenance: number;
  cumulative_capex: number;
  cumulative_insurance: number;
  cumulative_property_management: number;
  cumulative_other: number;
  cash_invested: number | null;
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

