import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { Tenant, TenantListResponse } from '../types';

// Query key factory
export const tenantKeys = {
  all: ['tenants'] as const,
  lists: () => [...tenantKeys.all, 'list'] as const,
  list: (filters?: { property_id?: string; unit_id?: string; status?: string }) => 
    [...tenantKeys.lists(), filters] as const,
  details: () => [...tenantKeys.all, 'detail'] as const,
  detail: (id: string) => [...tenantKeys.details(), id] as const,
};

// Fetch all tenants
export function useTenants(filters?: { property_id?: string; unit_id?: string; status?: string; enabled?: boolean }) {
  const { enabled, ...filterParams } = filters || {}
  return useQuery<TenantListResponse>({
    queryKey: tenantKeys.list(filterParams),
    enabled: enabled !== false && !!filters?.property_id, // Require property_id
    queryFn: async () => {
      if (!filters?.property_id) {
        throw new Error('property_id is required');
      }
      const startTime = performance.now();
      console.log(`📤 [TENANT] GET /api/v1/tenants - Request`, filters);
      const params = new URLSearchParams();
      params.append('property_id', filters.property_id);  // Required
      if (filters?.unit_id) params.append('unit_id', filters.unit_id);
      if (filters?.status) params.append('status', filters.status);
      
      const url = `/tenants?${params.toString()}`;
      try {
        const result = await apiClient.get<TenantListResponse>(url);
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Tenants API call completed in ${elapsed.toFixed(2)}ms`);
        return result;
      } catch (error) {
        const elapsed = performance.now() - startTime;
        console.log(`⏱️ [PERF] Tenants API call failed after ${elapsed.toFixed(2)}ms`);
        throw error;
      }
    },
  });
}

// Fetch single tenant
export function useTenant(tenantId: string) {
  return useQuery<Tenant>({
    queryKey: tenantKeys.detail(tenantId),
    queryFn: () => {
      console.log(`📤 [TENANT] GET /api/v1/tenants/${tenantId} - Request`);
      return apiClient.get<Tenant>(`/tenants/${tenantId}`);
    },
    enabled: !!tenantId,
  });
}

// Create tenant
export function useCreateTenant() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Tenant>) => {
      console.log('📝 [TENANT] Creating tenant with payload:', data);
      return apiClient.post<Tenant>('/tenants', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() });
      console.log('✅ [TENANT] Created tenant');
    },
    onError: (error) => {
      console.error('❌ [TENANT] Error creating tenant:', error);
    },
  });
}

// Update tenant
export function useUpdateTenant() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Tenant> }) => {
      console.log(`📝 [TENANT] Updating tenant ${id} with payload:`, data);
      return apiClient.put<Tenant>(`/tenants/${id}`, data);
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() });
      queryClient.invalidateQueries({ queryKey: tenantKeys.detail(variables.id) });
      console.log(`✅ [TENANT] Updated tenant ${variables.id}`);
    },
    onError: (error) => {
      console.error('❌ [TENANT] Error updating tenant:', error);
    },
  });
}

// Delete tenant
export function useDeleteTenant() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => {
      console.log(`🗑️ [TENANT] Deleting tenant ${id}`);
      return apiClient.delete(`/tenants/${id}`);
    },
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: tenantKeys.lists() });
      queryClient.invalidateQueries({ queryKey: tenantKeys.detail(id) });
      console.log(`✅ [TENANT] Deleted tenant ${id}`);
    },
    onError: (error) => {
      console.error('❌ [TENANT] Error deleting tenant:', error);
    },
  });
}

