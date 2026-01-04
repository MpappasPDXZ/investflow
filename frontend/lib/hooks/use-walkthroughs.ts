import { apiClient } from '../api-client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export interface WalkthroughAreaIssue {
  description: string;
  severity: 'minor' | 'moderate' | 'major';
  estimated_cost?: number;
}

export interface WalkthroughAreaPhoto {
  photo_blob_name: string;
  photo_url?: string;
  notes?: string;
  order: number;
  document_id?: string;  // Document ID from vault table (preferred over blob_name)
}

export interface WalkthroughArea {
  id?: string;
  walkthrough_id?: string;
  floor: string;
  area_name: string;
  area_order?: number;
  inspection_status: 'no_issues' | 'issue_noted_as_is' | 'issue_landlord_to_fix';
  notes?: string;
  landlord_fix_notes?: string;
  issues?: WalkthroughAreaIssue[];
  photos?: WalkthroughAreaPhoto[];
}

// Field order matching backend Iceberg table schema
const WALKTHROUGHS_FIELD_ORDER = [
  "id",
  "property_id",
  "unit_id",
  "property_display_name",
  "unit_number",
  "walkthrough_type",
  "walkthrough_date",
  "status",
  "inspector_name",
  "tenant_name",
  "tenant_signature_date",
  "landlord_signature_date",
  "notes",
  "generated_pdf_blob_name",
  "areas_json",
  "is_active",
  "created_at",
  "updated_at",
];

export interface WalkthroughCreate {
  property_id: string;
  unit_id?: string;
  property_display_name?: string;
  unit_number?: string;
  walkthrough_type: 'move_in' | 'move_out' | 'periodic' | 'maintenance';
  walkthrough_date: string;
  inspector_name?: string;
  tenant_name?: string;
  tenant_signature_date?: string;
  landlord_signature_date?: string;
  notes?: string;
  areas: WalkthroughArea[];
}

export interface Walkthrough extends WalkthroughCreate {
  id: string;
  status: 'draft' | 'pending_signature' | 'completed';
  generated_pdf_blob_name?: string;
  pdf_url?: string;
  created_at: string;
  updated_at: string;
}

export interface WalkthroughListItem {
  id: string;
  property_id: string;
  unit_id?: string;
  property_display_name?: string;
  unit_number?: string;
  walkthrough_type: 'move_in' | 'move_out' | 'periodic' | 'maintenance';
  walkthrough_date: string;
  inspector_name?: string;
  tenant_name?: string;
  status: 'draft' | 'pending_signature' | 'completed';
  generated_pdf_blob_name?: string;
  pdf_url?: string;
  areas_count: number;  // Number of areas (simplified - no full area data)
  created_at: string;
  updated_at: string;
}

export interface WalkthroughListResponse {
  items: WalkthroughListItem[];
  total: number;
}

export function useWalkthroughs() {
  const queryClient = useQueryClient();

  const createWalkthrough = async (walkthroughData: WalkthroughCreate): Promise<Walkthrough> => {
    // Build ordered payload respecting backend field order (like leases)
    const orderedPayload: any = {};
    
    // Add fields in exact backend order
    for (const field of WALKTHROUGHS_FIELD_ORDER) {
      if (walkthroughData.hasOwnProperty(field) && walkthroughData[field as keyof WalkthroughCreate] !== undefined) {
        orderedPayload[field] = walkthroughData[field as keyof WalkthroughCreate];
      }
    }
    
    // Add areas (not in field order, handled separately by backend)
    if (walkthroughData.areas) {
      orderedPayload.areas = walkthroughData.areas;
    }
    
    // Add any remaining fields not in the order list (for backward compatibility)
    for (const key in walkthroughData) {
      if (!WALKTHROUGHS_FIELD_ORDER.includes(key) && key !== 'areas' && !orderedPayload.hasOwnProperty(key)) {
        orderedPayload[key] = walkthroughData[key as keyof WalkthroughCreate];
      }
    }
    
    console.log('📝 [WALKTHROUGH] Creating walkthrough with ordered payload:', orderedPayload);
    console.log('📝 [WALKTHROUGH] Payload field order:', Object.keys(orderedPayload));
    
    try {
      const response = await apiClient.post('/walkthroughs', orderedPayload);
      queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
      return response as Walkthrough;
    } catch (error) {
      console.error('❌ [WALKTHROUGH] Error creating walkthrough:', error);
      console.error('📤 [WALKTHROUGH] Payload that failed:', JSON.stringify(orderedPayload, null, 2));
      throw error;
    }
  };

  const updateWalkthrough = async (walkthroughId: string, walkthroughData: Partial<WalkthroughCreate>): Promise<Walkthrough> => {
    // Build ordered payload respecting backend field order (like leases)
    const orderedPayload: any = {};
    
    // Add fields in exact backend order
    for (const field of WALKTHROUGHS_FIELD_ORDER) {
      if (walkthroughData.hasOwnProperty(field) && walkthroughData[field as keyof WalkthroughCreate] !== undefined) {
        orderedPayload[field] = walkthroughData[field as keyof WalkthroughCreate];
      }
    }
    
    // Add areas (not in field order, handled separately by backend)
    if (walkthroughData.areas) {
      orderedPayload.areas = walkthroughData.areas;
    }
    
    // Add any remaining fields not in the order list (for backward compatibility)
    for (const key in walkthroughData) {
      if (!WALKTHROUGHS_FIELD_ORDER.includes(key) && key !== 'areas' && !orderedPayload.hasOwnProperty(key)) {
        orderedPayload[key] = walkthroughData[key as keyof WalkthroughCreate];
      }
    }
    
    console.log('📝 [WALKTHROUGH] Updating walkthrough with ordered payload:', orderedPayload);
    console.log('📝 [WALKTHROUGH] Payload field order:', Object.keys(orderedPayload));
    
    const response = await apiClient.put(`/walkthroughs/${walkthroughId}`, orderedPayload);
    queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
    queryClient.invalidateQueries({ queryKey: ['walkthrough', walkthroughId] });
    return response as Walkthrough;
  };

  const listWalkthroughs = async (filters: {
    property_id?: string;
    status?: string;
  } = {}): Promise<WalkthroughListResponse> => {
    const params = new URLSearchParams();
    if (filters.property_id) params.append('property_id', filters.property_id);
    if (filters.status && filters.status !== 'all') params.append('status', filters.status);
    
    const response = await apiClient.get(`/walkthroughs?${params}`);
    return response as WalkthroughListResponse;
  };

  const getWalkthrough = async (id: string): Promise<Walkthrough> => {
    const response = await apiClient.get(`/walkthroughs/${id}`);
    return response as Walkthrough;
  };

  const generatePDF = async (id: string, regenerate = false): Promise<{ pdf_url: string; pdf_blob_name: string }> => {
    const params = new URLSearchParams();
    if (regenerate) params.append('regenerate', 'true');
    const response = await apiClient.post(`/walkthroughs/${id}/generate-pdf?${params}`, {});
    queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
    queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
    return response as { pdf_url: string; pdf_blob_name: string };
  };

  const uploadAreaPhoto = async (
    walkthroughId: string,
    areaId: string,
    file: File,
    notes?: string,
    order: number = 1
  ): Promise<WalkthroughAreaPhoto> => {
    const formData = new FormData();
    formData.append('file', file);
    if (notes) formData.append('notes', notes);
    formData.append('order', order.toString());

    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (!token) {
      throw new Error('No authentication token found');
    }

    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/walkthroughs/${walkthroughId}/areas/${areaId}/photos`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        // Don't set Content-Type - browser will set it automatically with boundary for FormData
      },
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = 'Failed to upload photo';
      try {
        const error = await response.json();
        errorMessage = error.detail || error.message || errorMessage;
      } catch {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    queryClient.invalidateQueries({ queryKey: ['walkthrough', walkthroughId] });
    queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
    return result as WalkthroughAreaPhoto;
  };

  const deleteAreaPhoto = async (
    walkthroughId: string,
    areaId: string,
    documentId: string
  ): Promise<void> => {
    await apiClient.delete(`/walkthroughs/${walkthroughId}/areas/${areaId}/photos/${documentId}`);
    queryClient.invalidateQueries({ queryKey: ['walkthrough', walkthroughId] });
    queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
  };

  const deleteWalkthrough = async (id: string) => {
    await apiClient.delete(`/walkthroughs/${id}`);
    queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
  };

  return { 
    createWalkthrough,
    updateWalkthrough,
    listWalkthroughs, 
    getWalkthrough, 
    generatePDF,
    uploadAreaPhoto,
    deleteAreaPhoto,
    deleteWalkthrough 
  };
}

// React Query hooks for walkthroughs
export function useWalkthrough(walkthroughId: string) {
  return useQuery({
    queryKey: ['walkthrough', walkthroughId],
    queryFn: () => {
      return apiClient.get<Walkthrough>(`/walkthroughs/${walkthroughId}`);
    },
    enabled: !!walkthroughId,
  });
}

export function useWalkthroughsList(filters: {
  property_id?: string;
  status?: string;
} = {}) {
  return useQuery({
    queryKey: ['walkthroughs', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.property_id) params.append('property_id', filters.property_id);
      if (filters.status && filters.status !== 'all') params.append('status', filters.status);
      
      return apiClient.get<WalkthroughListResponse>(`/walkthroughs?${params}`);
    },
  });
}

