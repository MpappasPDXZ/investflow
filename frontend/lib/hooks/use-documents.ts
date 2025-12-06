/**
 * React Query hooks for documents
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { Document, DocumentListResponse, DocumentUploadResponse } from '../types';

export interface DocumentFilters {
  property_id?: string;
  unit_id?: string;
  document_type?: string;
  skip?: number;
  limit?: number;
}

export function useDocuments(filters: DocumentFilters = {}) {
  return useQuery<DocumentListResponse>({
    queryKey: ['documents', filters],
    queryFn: () => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) params.append(key, String(value));
      });
      const queryString = params.toString();
      return apiClient.get<DocumentListResponse>(`/documents${queryString ? `?${queryString}` : ''}`);
    },
    refetchOnMount: 'always', // Always refetch when component mounts
    staleTime: 0, // Consider data stale immediately
  });
}

export function useDocument(documentId: string) {
  return useQuery<Document>({
    queryKey: ['document', documentId],
    queryFn: () => apiClient.get<Document>(`/documents/${documentId}`),
    enabled: !!documentId,
  });
}

export function useDocumentDownloadUrl(documentId: string) {
  return useQuery<{ download_url: string }>({
    queryKey: ['document-download', documentId],
    queryFn: () => apiClient.get<{ download_url: string }>(`/documents/${documentId}/download`),
    enabled: !!documentId,
    staleTime: 1000 * 60 * 60, // 1 hour (SAS tokens valid for 24 hours)
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      documentType,
      propertyId,
      unitId,
    }: {
      file: File;
      documentType: string;
      propertyId?: string;
      unitId?: string;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', documentType);
      if (propertyId) formData.append('property_id', propertyId);
      if (unitId) formData.append('unit_id', unitId);
      
      return apiClient.upload<DocumentUploadResponse>('/documents/upload', formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => apiClient.delete(`/documents/${documentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}






