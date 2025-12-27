/**
 * React Query hooks for units
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';

export interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  current_monthly_rent: number | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UnitListResponse {
  items: Unit[];
  total: number;
}

export function useUnits(propertyId?: string) {
  return useQuery<UnitListResponse>({
    queryKey: propertyId ? ['units', propertyId] : ['units'],
    queryFn: async () => {
      if (!propertyId) {
        // Return empty response if no propertyId provided
        return Promise.resolve({ items: [], total: 0 });
      }
      const startTime = performance.now();
      const url = `/units?property_id=${propertyId}`;
      console.log(`📤 [UNITS] GET /api/v1${url} - Request`);
      try {
        const result = await apiClient.get<UnitListResponse>(url);
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Units API call completed in ${elapsed.toFixed(2)}ms`);
        return result;
      } catch (error) {
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Units API call failed after ${elapsed.toFixed(2)}ms`);
        throw error;
      }
    },
    enabled: !!propertyId, // Only run query if propertyId is provided
  });
}

export function useUnit(unitId: string) {
  return useQuery<Unit>({
    queryKey: ['unit', unitId],
    queryFn: () => {
      console.log(`📤 [UNIT] GET /api/v1/units/${unitId} - Request`);
      return apiClient.get<Unit>(`/units/${unitId}`);
    },
    enabled: !!unitId,
  });
}

export function useCreateUnit() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Unit>) => {
      console.log('📤 [UNIT] POST /api/v1/units - Request', data);
      return apiClient.post<Unit>('/units', data);
    },
    onSuccess: (_, variables) => {
      console.log('✅ [UNIT] Created unit');
      queryClient.invalidateQueries({ queryKey: ['units', variables.property_id] });
    },
    onError: (error) => {
      console.error('❌ [UNIT] Error creating unit:', error);
    },
  });
}

export function useUpdateUnit() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Unit> & { id: string }) => {
      console.log(`📤 [UNIT] PUT /api/v1/units/${id} - Request`, data);
      return apiClient.put<Unit>(`/units/${id}`, data);
    },
    onSuccess: (data) => {
      console.log('✅ [UNIT] Updated unit');
      queryClient.invalidateQueries({ queryKey: ['unit', data.id] });
      queryClient.invalidateQueries({ queryKey: ['units', data.property_id] });
    },
    onError: (error) => {
      console.error('❌ [UNIT] Error updating unit:', error);
    },
  });
}

export function useDeleteUnit() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, property_id }: { id: string; property_id: string }) => {
      console.log(`📤 [UNIT] DELETE /api/v1/units/${id} - Request`);
      return apiClient.delete(`/units/${id}`);
    },
    onSuccess: (_, variables) => {
      console.log('✅ [UNIT] Deleted unit');
      queryClient.invalidateQueries({ queryKey: ['units', variables.property_id] });
    },
    onError: (error) => {
      console.error('❌ [UNIT] Error deleting unit:', error);
    },
  });
}

