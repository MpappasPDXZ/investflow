/**
 * TypeScript types for API responses
 */

export interface Property {
  id: string;
  user_id: string;
  display_name?: string;
  purchase_price: number;
  purchase_date?: string;
  down_payment?: number;
  cash_invested?: number;
  current_market_value?: number;
  property_status?: 'own' | 'evaluating' | 'rehabbing' | 'listed_for_rent' | 'listed_for_sale' | 'sold' | 'hide';
  vacancy_rate?: number;
  monthly_rent_to_income_ratio?: number;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  property_type?: string;
  bedrooms?: number;
  bathrooms?: number;
  square_feet?: number;
  year_built?: number;
  current_monthly_rent?: number;
  notes?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Expense {
  id: string;
  property_id: string;
  unit_id?: string;
  description: string;
  date: string; // ISO date string
  amount: number;
  vendor?: string;
  expense_type: 'capex' | 'rehab' | 'pandi' | 'utilities' | 'maintenance' | 'insurance' | 'property_management' | 'other';
  expense_category?: 'co_equip' | 'rent_equip' | 'equip_maint' | 'small_tools' | 'bulk_comm' | 'eng_equip' | 'subs' | 'other';
  document_storage_id?: string;
  is_planned: boolean;
  notes?: string;
  created_by_user_id?: string;
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
  user_id: string;
  
  // Personal Information
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  phone_secondary?: string;
  
  // Identification
  date_of_birth?: string;
  ssn_last_four?: string;
  drivers_license?: string;
  drivers_license_state?: string;
  
  // Current Address
  current_address?: string;
  current_city?: string;
  current_state?: string;
  current_zip?: string;
  
  // Employment
  employer_name?: string;
  employer_phone?: string;
  job_title?: string;
  monthly_income?: number;
  employment_start_date?: string;
  
  // Emergency Contact
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relationship?: string;
  
  // Screening Documents
  background_check_document_id?: string;
  application_document_id?: string;
  
  // Status
  status?: 'applicant' | 'approved' | 'current' | 'former' | 'rejected';
  notes?: string;
  
  // Screening Results
  background_check_date?: string;
  background_check_status?: 'pass' | 'fail' | 'pending' | 'not_started';
  credit_score?: number;
  
  // Rental History
  has_evictions?: boolean;
  eviction_details?: string;
  previous_landlord_name?: string;
  previous_landlord_phone?: string;
  previous_landlord_contacted?: boolean;
  previous_landlord_reference?: string;
  
  // Lease Assignment
  property_id?: string;
  unit_id?: string;
  lease_id?: string;
  
  // Metadata
  created_at: string;
  updated_at: string;
  is_deleted: boolean;
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
  property_id: string;
  unit_id?: string;
  client_id?: string;
  amount: number;
  rent_period_month: number;
  rent_period_year: number;
  rent_period_start: string;
  rent_period_end: string;
  payment_date: string;
  payment_method?: 'check' | 'cash' | 'electronic' | 'money_order' | 'other';
  transaction_reference?: string;
  is_late: boolean;
  late_fee?: number;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface RentPaymentCreate {
  property_id: string;
  unit_id?: string;
  client_id?: string;
  amount: number;
  rent_period_month: number;
  rent_period_year: number;
  payment_date: string;
  payment_method?: 'check' | 'cash' | 'electronic' | 'money_order' | 'other';
  transaction_reference?: string;
  is_late?: boolean;
  late_fee?: number;
  notes?: string;
}

export interface RentListResponse {
  items: RentPayment[];
  total: number;
  page: number;
  limit: number;
}

// Financial Performance types
export interface FinancialPerformance {
  property_id: string;
  ytd_rent: number;
  ytd_expenses: number;
  ytd_profit_loss: number;
  ytd_piti: number;
  ytd_utilities: number;
  ytd_maintenance: number;
  ytd_capex: number;
  ytd_insurance: number;
  ytd_property_management: number;
  ytd_other: number;
  cumulative_rent: number;
  cumulative_expenses: number;
  cumulative_profit_loss: number;
  cumulative_piti: number;
  cumulative_utilities: number;
  cumulative_maintenance: number;
  cumulative_capex: number;
  cumulative_insurance: number;
  cumulative_property_management: number;
  cumulative_other: number;
  cash_on_cash: number | null;
  last_calculated_at: string;
}

