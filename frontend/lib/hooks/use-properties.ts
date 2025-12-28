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
      const startTime = performance.now();
      console.log('📤 [PROPERTIES] GET /api/v1/properties - Request');
      try {
        const result = await apiClient.get<PropertyListResponse>('/properties');
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Properties API call completed in ${elapsed.toFixed(2)}ms`);
        return result;
      } catch (error) {
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Properties API call failed after ${elapsed.toFixed(2)}ms`);
        throw error;
      }
    },
  });
}

export function useProperty(propertyId: string) {
  return useQuery<Property>({
    queryKey: ['property', propertyId],
    queryFn: () => {
      console.log(`📤 [PROPERTY] GET /api/v1/properties/${propertyId} - Request`);
      return apiClient.get<Property>(`/properties/${propertyId}`);
    },
    enabled: !!propertyId,
  });
}

export function useCreateProperty() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Property>) => {
      console.log('📤 [PROPERTY] POST /api/v1/properties - Request:', data);
      return apiClient.post<Property>('/properties', data);
    },
    onSuccess: (data) => {
      console.log('✅ [PROPERTY] POST /api/v1/properties - Response:', data);
      queryClient.invalidateQueries({ queryKey: ['properties'] });
    },
  });
}
