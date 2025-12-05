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
  document_type: 'receipt' | 'lease' | 'screening' | 'invoice' | 'other';
  property_id?: string;
  unit_id?: string;
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

