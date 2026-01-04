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
    enabled: !!filters.property_id, // Only fetch when property_id is provided
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
    onSuccess: async (response, variables) => {
      // Invalidate and refetch to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['rents'] });
      await queryClient.refetchQueries({ queryKey: ['rents'] });
      // Invalidate financial performance cache since revenue changed
      if (variables.property_id) {
        await queryClient.invalidateQueries({ queryKey: ['financial-performance', variables.property_id] });
      }
    },
  });
}

export function useCreateRentWithReceipt() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (formData: FormData) => 
      apiClient.upload<RentPayment>('/rent/with-receipt', formData),
    onSuccess: async (response) => {
      // Invalidate and refetch to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['rents'] });
      await queryClient.refetchQueries({ queryKey: ['rents'] });
      // Invalidate financial performance cache since revenue changed
      if (response?.property_id) {
        await queryClient.invalidateQueries({ queryKey: ['financial-performance', response.property_id] });
      }
    },
  });
}

export function useUpdateRent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RentPaymentCreate> }) =>
      apiClient.put<RentPayment>(`/rent/${id}`, data),
    onSuccess: async (response, variables) => {
      // Invalidate and refetch to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['rents'] });
      await queryClient.invalidateQueries({ queryKey: ['rent', variables.id] });
      await queryClient.refetchQueries({ queryKey: ['rents'] });
      // Invalidate financial performance cache since revenue changed
      const propertyId = response?.property_id || variables.data?.property_id;
      if (propertyId) {
        await queryClient.invalidateQueries({ queryKey: ['financial-performance', propertyId] });
      }
    },
  });
}

export function useDeleteRent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (rentId: string) => apiClient.delete(`/rent/${rentId}`),
    onSuccess: async () => {
      // Invalidate and refetch to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['rents'] });
      await queryClient.refetchQueries({ queryKey: ['rents'] });
      // Invalidate all financial performance caches since revenue changed
      // (We don't know which property without fetching the rent first)
      await queryClient.invalidateQueries({ queryKey: ['financial-performance'] });
    },
  });
}










