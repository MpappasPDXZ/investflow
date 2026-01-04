/**
 * TypeScript types for API responses
 */

export interface Property {
  id: string; // Iceberg: string (UUID)
  user_id: string; // Iceberg: string (UUID)
  display_name?: string; // Iceberg: string
  purchase_price: number; // Iceberg: int64 (no decimals allowed)
  purchase_date?: string; // Iceberg: date32 (ISO date string)
  down_payment?: number; // Iceberg: int64 (no decimals allowed)
  cash_invested?: number; // Iceberg: int64 (no decimals allowed)
  current_market_value?: number; // Iceberg: int64 (no decimals allowed)
  property_status?: 'own' | 'evaluating' | 'rehabbing' | 'listed_for_rent' | 'listed_for_sale' | 'sold' | 'rented' | 'hide'; // Iceberg: string
  vacancy_rate?: number; // Iceberg: float64 (decimals allowed)
  monthly_rent_to_income_ratio?: number; // Iceberg: decimal128(4, 2) (decimals allowed)
  address_line1?: string; // Iceberg: string
  address_line2?: string; // Iceberg: string
  city?: string; // Iceberg: string
  state?: string; // Iceberg: string
  zip_code?: string; // Iceberg: string
  property_type?: string; // Iceberg: string
  unit_count?: number; // Iceberg: int64 (no decimals allowed)
  bedrooms?: number; // Iceberg: int64 (no decimals allowed)
  bathrooms?: number; // Iceberg: float64 (decimals allowed, e.g., 1.5, 2.5)
  square_feet?: number; // Iceberg: int64 (no decimals allowed)
  year_built?: number; // Iceberg: int64 (no decimals allowed)
  current_monthly_rent?: number; // Iceberg: float64 (decimals allowed)
  notes?: string; // Iceberg: string
  has_units?: boolean; // Iceberg: bool
  is_active: boolean; // Iceberg: bool
  created_at: string; // Iceberg: timestamp (ISO datetime string)
  updated_at: string; // Iceberg: timestamp (ISO datetime string)
}

export interface Expense {
  id: string;
  property_id: string;
  unit_id?: string;
  description: string;
  date: string; // ISO date string
  amount: number;
  vendor?: string;
  expense_type: 'capex' | 'rehab' | 'pandi' | 'tax' | 'utilities' | 'maintenance' | 'insurance' | 'property_management' | 'other';
  expense_category?: 'co_equip' | 'rent_equip' | 'equip_maint' | 'small_tools' | 'bulk_comm' | 'eng_equip' | 'subs' | 'other';
  document_storage_id?: string;
  notes?: string;
  has_receipt?: boolean; // Iceberg: bool (nullable)
  created_at: string;
  updated_at: string;
}

export interface ExpenseListResponse {
  items: Expense[];
  total: number;
  page: number;
  limit: number;
}

export interface PropertyListResponse {
  items: Property[];
  total: number;
  page: number;
  limit: number;
}

export interface UserShare {
  id: string;
  user_id: string;
  shared_email: string;
  created_at: string;
  updated_at: string;
}

export interface SharedUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

// Document types
export interface Document {
  id: string;
  blob_location: string;
  blob_name?: string;
  file_name: string;
  file_type?: string;
  file_size?: number;
  document_type: 'receipt' | 'lease' | 'screening' | 'invoice' | 'other' | 'rental_application' | 'credit_report' | 'criminal_check' | 'eviction_report' | 'income_verification' | 'employment_verification' | 'reference_check' | 'eviction_history' | 'screening_other';
  display_name?: string;
  property_id?: string;
  unit_id?: string;
  tenant_id?: string;
  uploaded_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  limit: number;
}

// Tenant types
export interface Tenant {
  id: string;
  user_id?: string;  // Optional, kept for audit
  
  // Property assignment (required)
  property_id: string;  // Required
  unit_id?: string;  // Optional, for multi-family
  
  // Personal Information
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  
  // Current Address
  current_address?: string;
  current_city?: string;
  current_state?: string;
  current_zip?: string;
  
  // Employment
  employer_name?: string;
  monthly_income?: number;
  
  // Status
  status?: 'applicant' | 'approved' | 'current' | 'former' | 'rejected';
  notes?: string;
  
    // Screening Results
    background_check_status?: 'pass' | 'fail' | 'pending' | 'not_started';
    credit_score?: number;
    
    // Landlord References (JSON array)
    landlord_references?: Array<{
      landlord_name: string;
      landlord_phone?: string;
      landlord_email?: string;
      property_address?: string;
      contact_date?: string;
      status?: 'pass' | 'fail' | 'no_info';
      notes?: string;
    }>;
    
    // Identification
    date_of_birth?: string;  // Under background check and screening
  
  // Metadata
  created_at: string;
  updated_at: string;
  landlord_references_passed?: number;
}

export interface TenantListResponse {
  tenants: Tenant[];
  total: number;
}

export interface DocumentUploadResponse {
  document: Document;
  download_url: string;
}

// Expense Summary types (for CPA reporting)
export interface YearlyExpenseTotal {
  year: number;
  total: number;
  count: number;
  by_type: Record<string, number>;
}

export interface ExpenseSummary {
  yearly_totals: YearlyExpenseTotal[];
  type_totals: Record<string, number>;
  grand_total: number;
  total_count: number;
}

// Rent types
export interface RentPayment {
  id: string;
  // Denormalized fields
  user_id: string;
  user_name?: string;
  property_id: string;
  property_name?: string;
  unit_id?: string;
  unit_name?: string;
  tenant_id?: string;
  tenant_name?: string;
  // Revenue classification
  revenue_description?: string;
  is_non_irs_revenue: boolean;
  // Rent period
  is_one_time_fee: boolean;
  rent_period_month?: number;
  rent_period_year?: number;
  rent_period_start: string;
  rent_period_end: string;
  // Payment details
  amount: number;
  payment_date: string;
  payment_method?: 'check' | 'cash' | 'electronic' | 'money_order' | 'other';
  transaction_reference?: string;
  is_late: boolean;
  late_fee?: number;
  notes?: string;
  document_storage_id?: string;
  created_at?: string;
  updated_at?: string;
  // Legacy field (deprecated, use tenant_id)
  client_id?: string;
}

export interface RentPaymentCreate {
  property_id: string;
  unit_id?: string;
  tenant_id?: string;
  amount: number;
  revenue_description?: string;
  is_non_irs_revenue?: boolean;
  is_one_time_fee?: boolean;
  rent_period_month?: number;
  rent_period_year?: number;
  rent_period_start?: string;
  rent_period_end?: string;
  payment_date: string;
  payment_method?: 'check' | 'cash' | 'electronic' | 'money_order' | 'other';
  transaction_reference?: string;
  is_late?: boolean;
  late_fee?: number;
  notes?: string;
  document_storage_id?: string;
  // Legacy field (deprecated, use tenant_id)
  client_id?: string;
}

export interface RentListResponse {
  items: RentPayment[];
  total: number;
  page: number;
  limit: number;
}

// Financial Performance types - exported from use-financial-performance.ts hook
// Re-exported here for convenience
export type { FinancialPerformance } from '@/lib/hooks/use-financial-performance';

