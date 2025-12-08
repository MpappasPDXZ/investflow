/**
 * React Query hooks for rent payments
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { RentPayment, RentPaymentCreate, RentListResponse } from '../types';

export interface RentFilters {
  property_id?: string;
  unit_id?: string;
  year?: number;
  skip?: number;
  limit?: number;
}

export function useRents(filters: RentFilters = {}) {
  return useQuery<RentListResponse>({
    queryKey: ['rents', filters],
    queryFn: () => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) params.append(key, String(value));
      });
      const queryString = params.toString();
      return apiClient.get<RentListResponse>(`/rent${queryString ? `?${queryString}` : ''}`);
    },
  });
}

export function useRent(rentId: string) {
  return useQuery<RentPayment>({
    queryKey: ['rent', rentId],
    queryFn: () => apiClient.get<RentPayment>(`/rent/${rentId}`),
    enabled: !!rentId,
  });
}

export function useCreateRent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: RentPaymentCreate) => 
      apiClient.post<RentPayment>('/rent', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rents'] });
    },
  });
}

export function useUpdateRent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RentPaymentCreate> }) =>
      apiClient.put<RentPayment>(`/rent/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['rents'] });
      queryClient.invalidateQueries({ queryKey: ['rent', variables.id] });
    },
  });
}

export function useDeleteRent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (rentId: string) => apiClient.delete(`/rent/${rentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rents'] });
    },
  });
}










