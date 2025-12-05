/**
 * React Query hooks for properties
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { Property, PropertyListResponse } from '../types';

export function useProperties() {
  return useQuery<PropertyListResponse>({
    queryKey: ['properties'],
    queryFn: () => {
      console.log('📤 [PROPERTIES] GET /api/v1/properties - Request');
      return apiClient.get<PropertyListResponse>('/properties');
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
