/**
 * React Query hooks for properties
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { Property, PropertyListResponse } from '../types';

export function useProperties(options?: { enabled?: boolean }) {
  return useQuery<PropertyListResponse>({
    queryKey: ['properties'],
    enabled: options?.enabled !== false, // Default to true for backward compatibility
    queryFn: async () => {
      return await apiClient.get<PropertyListResponse>('/properties');
    },
  });
}

export function useProperty(propertyId: string) {
  return useQuery<Property>({
    queryKey: ['property', propertyId],
    queryFn: () => {
      return apiClient.get<Property>(`/properties/${propertyId}`);
    },
    enabled: !!propertyId,
  });
}

export function useCreateProperty() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Property>) => {
      return apiClient.post<Property>('/properties', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] });
    },
  });
}
