import { useAuth } from './use-auth';
import { apiClient } from '../api-client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export interface Tenant {
  id?: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
}

export interface MoveOutCostItem {
  item: string;
  description?: string;
  amount: number | string;
  order: number;
}

export interface LeaseCreate {
  property_id: string;
  unit_id?: string;
  state: 'NE' | 'MO';
  commencement_date: string;
  termination_date: string;
  monthly_rent: number;
  security_deposit: number;
  tenants: Tenant[];
  auto_convert_month_to_month?: boolean;
  payment_method?: string;
  max_occupants?: number;
  max_adults?: number;
  max_children?: boolean;
  pets_allowed?: boolean;
  pet_fee_one?: number;
  pet_fee_two?: number;
  max_pets?: number;
  utilities_tenant?: string;
  utilities_landlord?: string;
  parking_spaces?: number;
  parking_small_vehicles?: number;
  parking_large_trucks?: number;
  front_door_keys?: number;
  back_door_keys?: number;
  key_replacement_fee?: number;
  has_shared_driveway?: boolean;
  shared_driveway_with?: string;
  has_garage?: boolean;
  garage_outlets_prohibited?: boolean;
  has_attic?: boolean;
  attic_usage?: string;
  has_basement?: boolean;
  appliances_provided?: string;
  snow_removal_responsibility?: string;
  lead_paint_disclosure?: boolean;
  lead_paint_year_built?: number;
  early_termination_allowed?: boolean;
  early_termination_notice_days?: number;
  early_termination_fee_months?: number;
  moveout_costs?: MoveOutCostItem[];
  methamphetamine_disclosure?: boolean;
  owner_name?: string;
  owner_address?: string;
  manager_name?: string;
  manager_address?: string;
  moveout_inspection_rights?: boolean;
  notes?: string;
}

export interface Lease extends LeaseCreate {
  id: string;
  user_id: string;
  status: 'draft' | 'pending_signature' | 'active' | 'expired' | 'terminated';
  lease_version: number;
  created_at: string;
  updated_at: string;
  pdf_url?: string;
  latex_url?: string;
}

export interface LeaseListResponse {
  leases: Lease[];
  total: number;
}

export function useLeases() {
  const createLease = async (leaseData: LeaseCreate): Promise<Lease> => {
    const response = await apiClient.post('/leases', leaseData);
    return response as Lease;
  };

  const listLeases = async (filters: {
    property_id?: string;
    status?: string;
    state?: string;
    active_only?: boolean;
  } = {}): Promise<LeaseListResponse> => {
    const params = new URLSearchParams();
    if (filters.property_id) params.append('property_id', filters.property_id);
    if (filters.status && filters.status !== 'all') params.append('status', filters.status);
    if (filters.state && filters.state !== 'all') params.append('state', filters.state);
    if (filters.active_only) params.append('active_only', 'true');
    
    const response = await apiClient.get(`/leases?${params}`);
    return response as LeaseListResponse;
  };

  const getLease = async (id: string): Promise<Lease> => {
    const response = await apiClient.get(`/leases/${id}`);
    return response as Lease;
  };

  const generatePDF = async (id: string, regenerate = false): Promise<{ pdf_url: string; latex_url: string }> => {
    const response = await apiClient.post(`/leases/${id}/generate-pdf`, { regenerate });
    return response as { pdf_url: string; latex_url: string };
  };

  const deleteLease = async (id: string) => {
    await apiClient.delete(`/leases/${id}`);
  };

  return { 
    createLease, 
    listLeases, 
    getLease, 
    generatePDF, 
    deleteLease 
  };
}

// React Query hooks for leases
export function useLease(leaseId: string) {
  return useQuery<Lease>({
    queryKey: ['lease', leaseId],
    queryFn: () => {
      console.log(`📤 [LEASE] GET /api/v1/leases/${leaseId} - Request`);
      return apiClient.get<Lease>(`/leases/${leaseId}`);
    },
    enabled: !!leaseId,
  });
}

export function useLeasesList(filters: {
  property_id?: string;
  status?: string;
  state?: string;
  active_only?: boolean;
} = {}) {
  return useQuery<LeaseListResponse>({
    queryKey: ['leases', filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.property_id) params.append('property_id', filters.property_id);
      if (filters.status && filters.status !== 'all') params.append('status', filters.status);
      if (filters.state && filters.state !== 'all') params.append('state', filters.state);
      if (filters.active_only) params.append('active_only', 'true');
      
      console.log(`📤 [LEASES] GET /api/v1/leases?${params} - Request`);
      return apiClient.get<LeaseListResponse>(`/leases?${params}`);
    },
  });
}
