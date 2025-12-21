import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface LandlordReference {
  id: string;
  tenant_id: string;
  user_id: string;
  landlord_name: string;
  landlord_phone?: string;
  landlord_email?: string;
  property_address?: string;
  contact_date: string;
  status: 'pass' | 'fail' | 'no_info';
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface LandlordReferenceListResponse {
  references: LandlordReference[];
  total: number;
  passed_count: number;
}

export function useLandlordReferences(params?: { tenant_id?: string }) {
  const queryParams = new URLSearchParams();
  if (params?.tenant_id) {
    queryParams.append('tenant_id', params.tenant_id);
  }
  
  const queryString = queryParams.toString();
  const url = `/landlord-references${queryString ? `?${queryString}` : ''}`;
  
  return useQuery<LandlordReferenceListResponse>({
    queryKey: ['landlord-references', params?.tenant_id],
    queryFn: () => {
      console.log(`📤 [LANDLORD_REF] GET ${url} - Request`);
      return apiClient.get<LandlordReferenceListResponse>(url);
    },
  });
}

export function useLandlordReference(referenceId: string) {
  return useQuery<LandlordReference>({
    queryKey: ['landlord-reference', referenceId],
    queryFn: () => {
      console.log(`📤 [LANDLORD_REF] GET /api/v1/landlord-references/${referenceId} - Request`);
      return apiClient.get<LandlordReference>(`/landlord-references/${referenceId}`);
    },
    enabled: !!referenceId,
  });
}

export function useCreateLandlordReference() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: Partial<LandlordReference>) => {
      console.log('📤 [LANDLORD_REF] Creating landlord reference:', data);
      return apiClient.post<LandlordReference>('/landlord-references', data);
    },
    onSuccess: (_, variables) => {
      console.log('✅ [LANDLORD_REF] Landlord reference created');
      queryClient.invalidateQueries({ queryKey: ['landlord-references'] });
      if (variables.tenant_id) {
        queryClient.invalidateQueries({ queryKey: ['tenants'] });
        queryClient.invalidateQueries({ queryKey: ['tenant', variables.tenant_id] });
      }
    },
    onError: (error) => {
      console.error('❌ [LANDLORD_REF] Error creating landlord reference:', error);
    },
  });
}

export function useUpdateLandlordReference() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, ...data }: Partial<LandlordReference> & { id: string }) => {
      console.log(`📤 [LANDLORD_REF] Updating landlord reference ${id}`);
      return apiClient.put<LandlordReference>(`/landlord-references/${id}`, data);
    },
    onSuccess: (data) => {
      console.log('✅ [LANDLORD_REF] Landlord reference updated');
      queryClient.invalidateQueries({ queryKey: ['landlord-references'] });
      queryClient.invalidateQueries({ queryKey: ['landlord-reference', data.id] });
      if (data.tenant_id) {
        queryClient.invalidateQueries({ queryKey: ['tenants'] });
        queryClient.invalidateQueries({ queryKey: ['tenant', data.tenant_id] });
      }
    },
    onError: (error) => {
      console.error('❌ [LANDLORD_REF] Error updating landlord reference:', error);
    },
  });
}

export function useDeleteLandlordReference() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id: string) => {
      console.log(`📤 [LANDLORD_REF] Deleting landlord reference ${id}`);
      return apiClient.delete(`/landlord-references/${id}`);
    },
    onSuccess: () => {
      console.log('✅ [LANDLORD_REF] Landlord reference deleted');
      queryClient.invalidateQueries({ queryKey: ['landlord-references'] });
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
    onError: (error) => {
      console.error('❌ [LANDLORD_REF] Error deleting landlord reference:', error);
    },
  });
}

