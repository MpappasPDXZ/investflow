import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface DocumentFilters {
  property_id: string; // Required
  unit_id?: string;
  tenant_id?: string;
  document_type?: string;
}

export interface Document {
  id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  document_type: string;
  property_id?: string;
  unit_id?: string;
  tenant_id?: string;
  display_name?: string;
  uploaded_at: string;
  created_at: string;
  blob_location: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  limit: number;
}

export function useDocuments(filters: DocumentFilters) {
  return useQuery<DocumentListResponse>({
    queryKey: ['documents', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append('property_id', filters.property_id);
      if (filters.unit_id) params.append('unit_id', filters.unit_id);
      if (filters.tenant_id) params.append('tenant_id', filters.tenant_id);
      if (filters.document_type) params.append('document_type', filters.document_type);

      const response = await apiClient.get(`/documents?${params.toString()}`);
      return response as DocumentListResponse;
    },
    enabled: !!filters.property_id, // Only fetch when property_id is provided
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      await apiClient.delete(`/documents/${documentId}`);
    },
    onSuccess: async () => {
      // Invalidate all document queries to ensure UI updates regardless of filters
      await queryClient.invalidateQueries({
        queryKey: ['documents'],
        exact: false // Match all queries that start with 'documents'
      });
    },
  });
}

export interface UploadDocumentParams {
  file: File;
  documentType: string;
  propertyId?: string;
  unitId?: string;
  tenantId?: string;
  displayName?: string;
}

export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: UploadDocumentParams) => {
      const formData = new FormData();
      formData.append('file', params.file);
      formData.append('document_type', params.documentType);

      if (params.propertyId) {
        formData.append('property_id', params.propertyId);
      }
      if (params.unitId) {
        formData.append('unit_id', params.unitId);
      }
      if (params.tenantId) {
        formData.append('tenant_id', params.tenantId);
      }
      if (params.displayName) {
        formData.append('display_name', params.displayName);
      }

      const response = await apiClient.upload<{ document: Document }>('/documents/upload', formData);
      return response;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      await queryClient.refetchQueries({ queryKey: ['documents'] });
    },
  });
}
