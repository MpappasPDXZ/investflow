'use client';

import { useParams, useRouter } from 'next/navigation';
import { useProperty } from '@/lib/hooks/use-properties';
import { useFinancialPerformance } from '@/lib/hooks/use-financial-performance';
import { useExpenses } from '@/lib/hooks/use-expenses';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Building2, Plus, Edit2, Trash2, X, Check, FileText, DollarSign, Home, Eye, TrendingUp, Hammer, ListChecks, Tag, Archive, ShoppingCart, Calendar, LayoutGrid, Key } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import ScheduledFinancialsTab from '@/components/ScheduledFinancialsTab';
import RentManagementTab from '@/components/RentManagementTab';
import RentAnalysisTab from '@/components/RentAnalysisTab';
import SetRentAnalysisTab from '@/components/SetRentAnalysisTab';
import FinancialPerformanceTab from '@/components/FinancialPerformanceTab';
import ComparablesTab from '@/components/ComparablesTab';

interface Unit {
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

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { data: property, isLoading, refetch } = useProperty(id);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(false);
  const [showAddUnit, setShowAddUnit] = useState(false);
  const [editingUnit, setEditingUnit] = useState<string | null>(null);
  const [deletingUnit, setDeletingUnit] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'details' | 'performance' | 'financials' | 'down-payment' | 'rent' | 'comps'>('details');
  const [editingProperty, setEditingProperty] = useState(false);

  // Fetch financial performance for YTD P/L display
  const { data: financialPerformance } = useFinancialPerformance(id);
  const { data: expensesData } = useExpenses(id);
  
  // Fetch scheduled expenses for principal & interest calculation
  const [scheduledExpenses, setScheduledExpenses] = useState<any[]>([]);
  const [loadingScheduledExpenses, setLoadingScheduledExpenses] = useState(false);

  // Calculate total rehab expenses - exclude deleted/inactive expenses
  const totalRehabExpenses = expensesData?.items
    ?.filter((exp: any) => {
      // Only include active rehab expenses
      // Check if expense has is_deleted or is_active field (some expenses might not have these)
      const isDeleted = exp.is_deleted === true;
      const isInactive = exp.is_active === false;
      const isRehab = exp.expense_type === 'rehab';
      return isRehab && !isDeleted && !isInactive;
    })
    ?.reduce((sum: number, exp: any) => sum + Number(exp.amount), 0) || 0;


  // Find Principal & Interest expense from scheduled expenses
  const piExpense = scheduledExpenses.find((exp: any) => exp.expense_type === 'pi' && exp.is_active);
  const principalAmount = piExpense?.principal ? Number(piExpense.principal) : 0;

  // Fetch scheduled expenses
  useEffect(() => {
    if (id) {
      fetchScheduledExpenses();
    }
  }, [id]);

  const fetchScheduledExpenses = async () => {
    try {
      setLoadingScheduledExpenses(true);
      const response = await apiClient.get<{ items: any[]; total: number }>(
        `/scheduled-expenses?property_id=${id}`
      );
      setScheduledExpenses(response.items || []);
    } catch (err) {
      console.error('❌ [SCHEDULED_EXPENSES] Error fetching scheduled expenses:', err);
      setScheduledExpenses([]);
    } finally {
      setLoadingScheduledExpenses(false);
    }
  };

  // Form state for adding/editing units
  const [unitForm, setUnitForm] = useState({
    unit_number: '',
    bedrooms: '',
    bathrooms: '',
    square_feet: '',
    current_monthly_rent: '',
  });

  // PropertyUpdate schema fields - EXACT match to backend PropertyUpdate (24 fields total)
  // Ordered by Iceberg dtype: STRING, INT64, FLOAT64, DATE32, DECIMAL128, BOOL
  // Source: backend/app/schemas/property.py PropertyUpdate class
  // ORDERED TO MATCH EXACT ICEBERG SCHEMA ORDER (excluding id, user_id, created_at, updated_at)
  const PROPERTY_UPDATE_FIELDS = [
    // Order matches Iceberg schema exactly:
    { name: 'display_name', type: 'string', label: 'Display Name', required: true },
    { name: 'property_status', type: 'string', label: 'Property Status', required: true, isSelect: true },
    { name: 'purchase_date', type: 'date32', label: 'Purchase Date', required: true },
    { name: 'monthly_rent_to_income_ratio', type: 'decimal128', label: 'Monthly Rent to Income Ratio', required: true },
    { name: 'address_line1', type: 'string', label: 'Address Line 1', required: true },
    { name: 'address_line2', type: 'string', label: 'Address Line 2', required: false },
    { name: 'city', type: 'string', label: 'City', required: true },
    { name: 'state', type: 'string', label: 'State', required: true },
    { name: 'zip_code', type: 'string', label: 'Zip Code', required: true },
    { name: 'property_type', type: 'string', label: 'Property Type', required: true, isSelect: true },
    { name: 'has_units', type: 'bool', label: 'Has Units', required: false },
    { name: 'notes', type: 'string', label: 'Notes', required: false, isTextarea: true },
    { name: 'is_active', type: 'bool', label: 'Is Active', required: false },
    { name: 'purchase_price', type: 'int64', label: 'Purchase Price', required: true },
    { name: 'square_feet', type: 'int64', label: 'Square Feet', required: false }, // Conditional: required for single family
    { name: 'down_payment', type: 'int64', label: 'Down Payment', required: true },
    { name: 'cash_invested', type: 'int64', label: 'Cash Invested (for CoC)', required: true },
    { name: 'current_market_value', type: 'int64', label: 'Current Market Value', required: true },
    { name: 'vacancy_rate', type: 'float64', label: 'Vacancy Rate', required: false },
    { name: 'unit_count', type: 'int64', label: 'Unit Count', required: false },
    { name: 'bedrooms', type: 'int64', label: 'Bedrooms', required: false }, // Conditional: required for single family
    { name: 'bathrooms', type: 'float64', label: 'Bathrooms', required: false }, // Conditional: required for single family
    { name: 'year_built', type: 'int64', label: 'Year Built', required: true },
    { name: 'current_monthly_rent', type: 'float64', label: 'Monthly Rent', required: true },
  ] as const;

  // Form state for editing property - ALL 24 fields from PropertyUpdate, no duplicates
  // ORDERED TO MATCH EXACT ICEBERG SCHEMA ORDER (excluding id, user_id, created_at, updated_at)
  const [propertyForm, setPropertyForm] = useState({
    // Order matches Iceberg schema exactly:
    display_name: '',
    property_status: '',
    purchase_date: '',
    monthly_rent_to_income_ratio: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    zip_code: '',
    property_type: '',
    has_units: false,
    notes: '',
    is_active: true, // Default to true
    purchase_price: '',
    square_feet: '',
    down_payment: '',
    cash_invested: '',
    current_market_value: '',
    vacancy_rate: '',
    unit_count: '',
    bedrooms: '',
    bathrooms: '',
    year_built: '',
    current_monthly_rent: '',
  });

  // Check if property is multi-unit
  const isMultiUnit = property?.property_type === 'multi_family' || property?.property_type === 'duplex';

  // Clean any decimals from int64 fields in form state (safety check)
  useEffect(() => {
    if (editingProperty) {
      const cleanedForm = { ...propertyForm };
      let needsUpdate = false;
      
      // List of int64 field names
      const int64Fields: (keyof typeof propertyForm)[] = [
        'purchase_price', 'down_payment', 'cash_invested', 'current_market_value',
        'unit_count', 'bedrooms', 'square_feet', 'year_built'
      ];
      
      int64Fields.forEach(field => {
        const value = cleanedForm[field];
        if (value && typeof value === 'string' && value.includes('.')) {
          // Remove decimal point and everything after it
          const cleaned = value.split('.')[0];
          (cleanedForm as any)[field] = cleaned;
          needsUpdate = true;
          console.warn(`⚠️ [PROPERTY] Cleaned decimal from int64 field ${field}: "${value}" → "${cleaned}"`);
        }
      });
      
      if (needsUpdate) {
        setPropertyForm(cleanedForm);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingProperty]);

  // Handler for int64 fields - prevents decimal input
  // CRITICAL: This ensures no decimals can be entered for int64 fields
  const handleInt64Change = (fieldName: keyof typeof propertyForm, value: string) => {
    // Remove ALL non-numeric characters (including decimal points, commas, etc.)
    // This is the first line of defense against decimals
    const cleaned = value.replace(/[^\d]/g, '');
    
    // Additional validation: if somehow a decimal got through, log a warning
    if (value.includes('.') && cleaned !== value.replace(/\./g, '')) {
      console.warn(`⚠️ [PROPERTY] Decimal detected in int64 field ${fieldName}: "${value}". Stripped to: "${cleaned}"`);
    }
    
    setPropertyForm({ ...propertyForm, [fieldName]: cleaned });
  };

  // Handler for float64 fields - allows decimals
  const handleFloat64Change = (fieldName: keyof typeof propertyForm, value: string) => {
    // Allow numbers and one decimal point
    const cleaned = value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1');
    setPropertyForm({ ...propertyForm, [fieldName]: cleaned });
  };

  // Fetch units if multi-unit property
  useEffect(() => {
    if (property?.id && isMultiUnit) {
      fetchUnits();
    }
  }, [property?.id, isMultiUnit]);

  const fetchUnits = async () => {
    try {
      setLoadingUnits(true);
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${property?.id}`);
      setUnits(response.items);
      console.log('✅ [UNITS] Fetched units:', response);
    } catch (err) {
      console.error('❌ [UNITS] Error fetching units:', err);
    } finally {
      setLoadingUnits(false);
    }
  };

  const handleAddUnit = async () => {
    try {
      const payload = {
        property_id: id,
        unit_number: unitForm.unit_number,
        bedrooms: unitForm.bedrooms ? parseInt(unitForm.bedrooms) : null,
        bathrooms: unitForm.bathrooms ? parseFloat(unitForm.bathrooms) : null,
        square_feet: unitForm.square_feet ? parseInt(unitForm.square_feet) : null,
        current_monthly_rent: unitForm.current_monthly_rent ? parseFloat(unitForm.current_monthly_rent) : null,
      };

      await apiClient.post('/units', payload);
      console.log('✅ [UNIT] Created unit');
      
      // Reset form and hide
      setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
      setShowAddUnit(false);
      
      // Refresh units list
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error creating unit:', err);
      alert(`Failed to create unit: ${(err as Error).message}`);
    }
  };

  const handleEditUnit = async (unitId: string) => {
    try {
      const payload = {
        unit_number: unitForm.unit_number,
        bedrooms: unitForm.bedrooms ? parseInt(unitForm.bedrooms) : null,
        bathrooms: unitForm.bathrooms ? parseFloat(unitForm.bathrooms) : null,
        square_feet: unitForm.square_feet ? parseInt(unitForm.square_feet) : null,
        current_monthly_rent: unitForm.current_monthly_rent ? parseFloat(unitForm.current_monthly_rent) : null,
      };

      await apiClient.put(`/units/${unitId}`, payload);
      console.log('✅ [UNIT] Updated unit');
      
      // Reset form and editing state
      setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
      setEditingUnit(null);
      
      // Refresh units list
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error updating unit:', err);
      alert(`Failed to update unit: ${(err as Error).message}`);
    }
  };

  const handleDeleteUnit = async (unitId: string, unitNumber: string) => {
    if (!confirm(`Are you sure you want to delete ${unitNumber}?`)) {
      return;
    }

    setDeletingUnit(unitId);
    try {
      await apiClient.delete(`/units/${unitId}`);
      console.log('✅ [UNIT] Deleted unit');
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error deleting unit:', err);
      alert(`Failed to delete unit: ${(err as Error).message}`);
    } finally {
      setDeletingUnit(null);
    }
  };

  const startEditUnit = (unit: Unit) => {
    setEditingUnit(unit.id);
    setUnitForm({
      unit_number: unit.unit_number,
      bedrooms: unit.bedrooms?.toString() || '',
      bathrooms: unit.bathrooms?.toString() || '',
      square_feet: unit.square_feet?.toString() || '',
      current_monthly_rent: unit.current_monthly_rent?.toString() || '',
    });
    setShowAddUnit(false);
  };

  const cancelEdit = () => {
    setEditingUnit(null);
    setShowAddUnit(false);
    setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
  };

  const startEditProperty = () => {
    if (!property) return;
    setEditingProperty(true);
    
    // Helper to safely convert int64 values to string without decimals
    // Handles both number and string inputs, strips any decimals
    const int64ToString = (value: number | null | undefined): string => {
      if (value == null) return '';
      // Convert to number, round to integer, then to string
      // This ensures no ".0" appears even if value comes as float or string with decimals
      const numValue = typeof value === 'string' ? parseFloat(value) : value;
      const intValue = Math.round(numValue);
      return String(intValue);
    };
    
    // Initialize form in exact Iceberg schema order (excluding id, user_id, created_at, updated_at)
    setPropertyForm({
      // Order matches Iceberg schema exactly:
      display_name: property.display_name || '',
      property_status: property.property_status || 'evaluating',
      purchase_date: property.purchase_date?.split('T')[0] || '2024-10-23',
      monthly_rent_to_income_ratio: property.monthly_rent_to_income_ratio?.toString() || '2.75',
      address_line1: property.address_line1 || '',
      address_line2: property.address_line2 || '',
      city: property.city || '',
      state: property.state || '',
      zip_code: property.zip_code || '',
      property_type: property.property_type || '',
      has_units: property.has_units || false,
      notes: property.notes || '',
      is_active: property.is_active !== undefined ? property.is_active : true,
      purchase_price: int64ToString(property.purchase_price),
      square_feet: int64ToString(property.square_feet),
      down_payment: int64ToString(property.down_payment),
      cash_invested: int64ToString(property.cash_invested),
      current_market_value: int64ToString(property.current_market_value),
      vacancy_rate: property.vacancy_rate?.toString() || '0.07',
      unit_count: int64ToString(property.unit_count),
      bedrooms: int64ToString(property.bedrooms),
      bathrooms: property.bathrooms?.toString() || '',
      year_built: int64ToString(property.year_built),
      current_monthly_rent: property.current_monthly_rent?.toString() || '',
    });
  };

  const handleSaveProperty = async () => {
    try {
      // Validate required fields
      const isMultiUnit = propertyForm.property_type === 'multi_family' || propertyForm.property_type === 'duplex';
      const missingRequiredFields: string[] = [];
      
      // Check all required fields
      for (const field of PROPERTY_UPDATE_FIELDS) {
        if (field.required) {
          const fieldName = field.name as keyof typeof propertyForm;
          const value = propertyForm[fieldName];
          
          // Special handling for conditional fields
          const fieldNameStr = String(fieldName);
          if (fieldNameStr === 'bedrooms' || fieldNameStr === 'bathrooms' || fieldNameStr === 'square_feet') {
            // These are only required for single family
            if (!isMultiUnit) {
              if (value === '' || value === null || value === undefined) {
                missingRequiredFields.push(field.label);
              }
            }
          } else {
            // Standard required field check
            if (value === '' || value === null || value === undefined) {
              missingRequiredFields.push(field.label);
            }
          }
        }
      }
      
      // Check monthly_rent_to_income_ratio (required but has default)
      if (!propertyForm.monthly_rent_to_income_ratio || propertyForm.monthly_rent_to_income_ratio.trim() === '') {
        // Set default if empty
        propertyForm.monthly_rent_to_income_ratio = '2.75';
      }
      
      if (missingRequiredFields.length > 0) {
        alert(`Please fill in all required fields:\n${missingRequiredFields.join('\n')}`);
        return;
      }
      
      // Validate: ensure exactly one field per storage field with no extras
      const expectedFieldNames = PROPERTY_UPDATE_FIELDS.map(f => f.name) as string[];
      const formFields = Object.keys(propertyForm) as string[];
      
      // Check for missing fields
      const missingFields = expectedFieldNames.filter(field => !formFields.includes(field));
      if (missingFields.length > 0) {
        console.error('❌ [PROPERTY] Missing form fields:', missingFields);
        alert(`Form validation error: Missing fields: ${missingFields.join(', ')}`);
        return;
      }
      
      // Check for extra fields
      const extraFields = formFields.filter((field: string) => !expectedFieldNames.includes(field));
      if (extraFields.length > 0) {
        console.error('❌ [PROPERTY] Extra form fields:', extraFields);
        alert(`Form validation error: Extra fields: ${extraFields.join(', ')}`);
        return;
      }

      // Build payload in EXACT Iceberg schema column order, converting types correctly
      const payload: any = {};
      
      // Process fields in exact storage order
      for (const field of PROPERTY_UPDATE_FIELDS) {
        const value = propertyForm[field.name as keyof typeof propertyForm] as string | boolean | undefined;
        
        // Skip empty strings and undefined values
        if (value === '' || value === undefined) continue;
        
        // Convert based on type
        if (field.type === 'int64') {
          // For int64, ensure we parse as integer (no decimals allowed)
          const numValue = value as string;
          // Skip if empty or whitespace only
          if (!numValue || numValue.trim() === '') continue;
          
          // CRITICAL: Remove any decimal point and everything after it
          // This prevents decimals from being sent to int64 fields
          const integerPart = numValue.split('.')[0].trim();
          
          // Validate: must be a valid integer string (only digits, optionally with minus sign)
          if (!/^-?\d+$/.test(integerPart)) {
            console.warn(`⚠️ [PROPERTY] Invalid int64 value for ${field.name}: "${numValue}". Expected integer only.`);
            continue;
          }
          
          // Parse as integer (base 10)
          const intValue = parseInt(integerPart, 10);
          
          // Validate: must be a valid number and not NaN
          if (isNaN(intValue)) {
            console.warn(`⚠️ [PROPERTY] Failed to parse int64 value for ${field.name}: "${numValue}"`);
            continue;
          }
          
          // Check if original value had decimals (warn but still use integer part)
          if (numValue.includes('.')) {
            console.warn(`⚠️ [PROPERTY] Decimal value detected for int64 field ${field.name}: "${numValue}". Using integer part: ${intValue}`);
          }
          
          payload[field.name] = intValue;
        } else if (field.type === 'float64') {
          const numValue = value as string;
          // Skip if empty or whitespace only
          if (!numValue || numValue.trim() === '') continue;
          const floatValue = parseFloat(numValue);
          if (!isNaN(floatValue)) {
            payload[field.name] = floatValue;
          }
        } else if (field.type === 'decimal128') {
          const numValue = value as string;
          // Skip if empty or whitespace only
          if (!numValue || numValue.trim() === '') continue;
          const decimalValue = parseFloat(numValue);
          if (!isNaN(decimalValue)) {
            payload[field.name] = decimalValue;
          }
        } else if (field.type === 'date32') {
          const dateValue = value as string;
          // Skip if empty
          if (!dateValue || dateValue.trim() === '') continue;
          payload[field.name] = dateValue;
        } else if (field.type === 'bool') {
          // For bool, only skip if undefined, but allow false values
          if (value === undefined) continue;
          payload[field.name] = value as boolean;
        } else {
          // string type - skip if empty
          const strValue = value as string;
          if (!strValue || strValue.trim() === '') continue;
          payload[field.name] = strValue;
        }
      }

      // Define the exact backend field order (from Iceberg schema)
      const BACKEND_FIELD_ORDER = [
        "id", "user_id", "display_name", "property_status", "purchase_date",
        "monthly_rent_to_income_ratio", "address_line1", "address_line2", "city", "state",
        "zip_code", "property_type", "has_units", "notes", "is_active",
        "purchase_price", "square_feet", "down_payment", "cash_invested", "current_market_value",
        "vacancy_rate", "unit_count", "bedrooms", "bathrooms", "year_built",
        "current_monthly_rent", "created_at", "updated_at"
      ];

      // Build ordered payload respecting backend field order
      const orderedPayload: any = {};
      for (const field of BACKEND_FIELD_ORDER) {
        if (field in payload) {
          orderedPayload[field] = payload[field];
        }
      }
      // Add any extra fields that might not be in the order list
      for (const key of Object.keys(payload)) {
        if (!BACKEND_FIELD_ORDER.includes(key) && !orderedPayload.hasOwnProperty(key)) {
          orderedPayload[key] = payload[key];
        }
      }

      // Log field order compliance
      const payloadKeys = Object.keys(orderedPayload);
      const orderedKeys = BACKEND_FIELD_ORDER.filter(f => payloadKeys.includes(f));
      console.log('📋 [PROPERTY] Field order compliance check (UPDATE):');
      console.log('   Expected order:', orderedKeys);
      console.log('   Actual payload keys:', payloadKeys);
      console.log('   ✅ Order matches:', JSON.stringify(orderedKeys) === JSON.stringify(payloadKeys.slice(0, orderedKeys.length)));
      console.log('📝 [PROPERTY] Updating property with ordered payload:', JSON.stringify(orderedPayload, null, 2));
      
      await apiClient.put(`/properties/${id}`, orderedPayload);
      console.log('✅ [PROPERTY] Updated property');
      
      setEditingProperty(false);
      refetch();
    } catch (err) {
      console.error('❌ [PROPERTY] Error updating property:', err);
      alert(`Failed to update property: ${(err as Error).message}`);
    }
  };

  const cancelEditProperty = () => {
    setEditingProperty(false);
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-gray-500">Loading property...</div>
      </div>
    );
  }

  if (!property) {
    return (
      <div className="p-8">
        <div className="text-red-600">Property not found</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            {property.display_name || 'Unnamed Property'}
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push('/properties')}
            size="sm"
            className="h-8 text-xs"
          >
            Back to Properties
          </Button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('details')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'details'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <FileText className="h-4 w-4 inline mr-2" />
            Details & Units
          </button>
          <button
            onClick={() => setActiveTab('performance')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'performance'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <DollarSign className="h-4 w-4 inline mr-2" />
            Financial Performance
          </button>
          <button
            onClick={() => setActiveTab('financials')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'financials'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <Calendar className="h-4 w-4 inline mr-2" />
            Scheduled Financials
          </button>
          <button
            onClick={() => setActiveTab('down-payment')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'down-payment'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <TrendingUp className="h-4 w-4 inline mr-2" />
            Bank Financing
          </button>
          <button
            onClick={() => setActiveTab('rent')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'rent'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <Home className="h-4 w-4 inline mr-2" />
            Set Rent
          </button>
          <button
            onClick={() => setActiveTab('comps')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'comps'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <LayoutGrid className="h-4 w-4 inline mr-2" />
            Comps
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'details' && (
        <>
          {editingProperty && (
            <Card className="mb-6 bg-blue-50 border-blue-200">
              <CardHeader>
                <CardTitle className="text-sm font-bold">Edit Property</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {/* Section 1: Display Name & Property Status */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="edit_display_name">Display Name *</Label>
                      <Input
                        id="edit_display_name"
                        value={propertyForm.display_name}
                        onChange={(e) => setPropertyForm({ ...propertyForm, display_name: e.target.value })}
                        className="text-sm"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="edit_property_status">Property Status *</Label>
                      <Select
                        value={propertyForm.property_status}
                        onValueChange={(value) => setPropertyForm({ ...propertyForm, property_status: value })}
                        required
                      >
                        <SelectTrigger className="text-sm">
                          <SelectValue placeholder="Select status" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="evaluating">
                            <div className="flex items-center gap-2">
                              <Eye className="h-4 w-4 text-blue-600" />
                              <span>Evaluating</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="own">
                            <div className="flex items-center gap-2">
                              <Home className="h-4 w-4 text-green-600" />
                              <span>Own</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="rehabbing">
                            <div className="flex items-center gap-2">
                              <Hammer className="h-4 w-4 text-orange-600" />
                              <span>Rehabbing</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="listed_for_rent">
                            <div className="flex items-center gap-2">
                              <ListChecks className="h-4 w-4 text-purple-600" />
                              <span>Listed for Rent</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="listed_for_sale">
                            <div className="flex items-center gap-2">
                              <Tag className="h-4 w-4 text-yellow-600" />
                              <span>Listed for Sale</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="sold">
                            <div className="flex items-center gap-2">
                              <ShoppingCart className="h-4 w-4 text-gray-600" />
                              <span>Sold</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="rented">
                            <div className="flex items-center gap-2">
                              <Key className="h-4 w-4 text-emerald-600" />
                              <span>Rented</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="hide">
                            <div className="flex items-center gap-2">
                              <Archive className="h-4 w-4 text-gray-400" />
                              <span>Hide</span>
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="edit_property_type">Property Type *</Label>
                      <Select
                        value={propertyForm.property_type}
                        onValueChange={(value) => setPropertyForm({ ...propertyForm, property_type: value })}
                        required
                      >
                        <SelectTrigger className="text-sm">
                          <SelectValue placeholder="Select property type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="single_family">Single Family</SelectItem>
                          <SelectItem value="multi_family">Multi Family</SelectItem>
                          <SelectItem value="condo">Condo</SelectItem>
                          <SelectItem value="apartment">Apartment</SelectItem>
                          <SelectItem value="townhome">Townhome</SelectItem>
                          <SelectItem value="duplex">Duplex</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-gray-200"></div>

                  {/* Section 2: Address (5 fields) */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Address</h3>
                    <div className="grid grid-cols-12 gap-4">
                      <div className="col-span-6">
                        <Label htmlFor="edit_address_line1">Address Line 1 *</Label>
                        <Input
                          id="edit_address_line1"
                          value={propertyForm.address_line1}
                          onChange={(e) => setPropertyForm({ ...propertyForm, address_line1: e.target.value })}
                          className="text-sm"
                          required
                        />
                      </div>
                      <div className="col-span-6">
                        <Label htmlFor="edit_address_line2">Address Line 2</Label>
                        <Input
                          id="edit_address_line2"
                          value={propertyForm.address_line2}
                          onChange={(e) => setPropertyForm({ ...propertyForm, address_line2: e.target.value })}
                          className="text-sm"
                          placeholder="Apt, Suite, Unit, etc."
                        />
                      </div>
                      <div className="col-span-7">
                        <Label htmlFor="edit_city">City *</Label>
                        <Input
                          id="edit_city"
                          value={propertyForm.city}
                          onChange={(e) => setPropertyForm({ ...propertyForm, city: e.target.value })}
                          className="text-sm"
                          required
                        />
                      </div>
                      <div className="col-span-2">
                        <Label htmlFor="edit_state">State *</Label>
                        <Input
                          id="edit_state"
                          value={propertyForm.state}
                          onChange={(e) => setPropertyForm({ ...propertyForm, state: e.target.value })}
                          className="text-sm"
                          maxLength={2}
                          placeholder="CA"
                          required
                        />
                      </div>
                      <div className="col-span-3">
                        <Label htmlFor="edit_zip_code">Zip Code *</Label>
                        <Input
                          id="edit_zip_code"
                          value={propertyForm.zip_code}
                          onChange={(e) => setPropertyForm({ ...propertyForm, zip_code: e.target.value })}
                          className="text-sm"
                          placeholder="12345"
                          required
                        />
                      </div>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-gray-200"></div>

                  {/* Section 3: Financials */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Financials</h3>
                    <div className="grid grid-cols-12 gap-4">
                      <div className="col-span-6">
                        <Label htmlFor="edit_current_market_value">Current Market Value *</Label>
                        <Input
                          id="edit_current_market_value"
                          type="number"
                          step="1"
                          min="0"
                          value={propertyForm.current_market_value}
                          onChange={(e) => handleInt64Change('current_market_value', e.target.value)}
                          className="text-sm"
                          required
                        />
                      </div>
                      <div className="col-span-6">
                        <Label htmlFor="edit_purchase_price">Purchase Price *</Label>
                        <Input
                          id="edit_purchase_price"
                          type="number"
                          step="1"
                          min="0"
                          value={propertyForm.purchase_price}
                          onChange={(e) => handleInt64Change('purchase_price', e.target.value)}
                          required
                          className="text-sm"
                        />
                      </div>
                      <div className="col-span-4">
                        <Label htmlFor="edit_purchase_date">Purchase Date *</Label>
                        <Input
                          id="edit_purchase_date"
                          type="date"
                          value={propertyForm.purchase_date}
                          onChange={(e) => setPropertyForm({ ...propertyForm, purchase_date: e.target.value })}
                          className="text-sm"
                          required
                        />
                        <p className="text-xs text-gray-500 mt-1">For depreciation calculations</p>
                      </div>
                      <div className="col-span-4">
                        <Label htmlFor="edit_down_payment">Down Payment *</Label>
                        <Input
                          id="edit_down_payment"
                          type="number"
                          step="1"
                          min="0"
                          value={propertyForm.down_payment}
                          onChange={(e) => handleInt64Change('down_payment', e.target.value)}
                          className="text-sm"
                          required
                        />
                      </div>
                      <div className="col-span-12">
                        <Label htmlFor="edit_cash_invested">Cash Invested (for CoC) *</Label>
                        <Input
                          id="edit_cash_invested"
                          type="number"
                          step="1"
                          min="0"
                          value={propertyForm.cash_invested}
                          onChange={(e) => handleInt64Change('cash_invested', e.target.value)}
                          className="text-sm"
                          placeholder="e.g., 75000"
                          required
                        />
                        <p className="text-xs text-gray-500 mt-1">What you have invested: down payment + rehab expenses + principal (if refinanced post-rehab with tenant)</p>
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Down Payment:</span>
                            <span className="font-semibold text-gray-900">
                              ${propertyForm.down_payment ? Math.round(parseFloat(propertyForm.down_payment) / 1000).toLocaleString() + 'k' : '$0'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Rehab Expenses:</span>
                            <span className="font-semibold text-gray-900">
                              ${totalRehabExpenses ? Math.round(totalRehabExpenses / 1000).toLocaleString() + 'k' : '$0'}
                            </span>
                          </div>
                          {principalAmount > 0 && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Principal (from scheduled financials):</span>
                              <span className="font-semibold text-gray-900">
                              -${Math.round(principalAmount / 1000).toLocaleString()}k
                            </span>
                            </div>
                          )}
                          <div className="flex justify-between pt-1 border-t border-gray-200">
                            <span className="text-gray-700 font-medium">Suggested Total:</span>
                            <span className="font-bold text-blue-600">
                              ${Math.round(((parseFloat(propertyForm.down_payment) || 0) + totalRehabExpenses - principalAmount) / 1000).toLocaleString()}k
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-gray-200"></div>

                  {/* Section 4: Multi-Family Fields (conditional) */}
                  {isMultiUnit && (
                    <>
                      <div>
                        <h3 className="text-sm font-semibold text-gray-700 mb-3">Multi-Family Details</h3>
                        <div className="grid grid-cols-12 gap-4">
                          <div className="col-span-3">
                            <Label htmlFor="edit_has_units">Has Units</Label>
                            <Select
                              value={propertyForm.has_units ? 'true' : 'false'}
                              onValueChange={(value) => setPropertyForm({ ...propertyForm, has_units: value === 'true' })}
                            >
                              <SelectTrigger className="text-sm">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="true">Yes</SelectItem>
                                <SelectItem value="false">No</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_unit_count">Unit Count</Label>
                            <Input
                              id="edit_unit_count"
                              type="number"
                              min="0"
                              step="1"
                              value={propertyForm.unit_count}
                              onChange={(e) => {
                                const cleaned = e.target.value.replace(/[^\d]/g, '');
                                setPropertyForm({ ...propertyForm, unit_count: cleaned });
                              }}
                              className="text-sm"
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_year_built">Year Built *</Label>
                            <Input
                              id="edit_year_built"
                              type="number"
                              min="1800"
                              max="2100"
                              step="1"
                              value={propertyForm.year_built}
                              onChange={(e) => {
                                const cleaned = e.target.value.replace(/[^\d]/g, '');
                                setPropertyForm({ ...propertyForm, year_built: cleaned });
                              }}
                              className="text-sm"
                              placeholder="e.g., 1985"
                              required
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_vacancy_rate">Vacancy Rate</Label>
                            <Input
                              id="edit_vacancy_rate"
                              type="number"
                              min="0"
                              max="1"
                              step="0.01"
                              value={propertyForm.vacancy_rate}
                              onChange={(e) => {
                                const cleaned = e.target.value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1');
                                setPropertyForm({ ...propertyForm, vacancy_rate: cleaned });
                              }}
                              className="text-sm"
                              placeholder="0.07"
                            />
                            <p className="text-xs text-gray-500 mt-1">e.g., 0.07 for 7%</p>
                          </div>
                          <div className="col-span-4">
                            <Label htmlFor="edit_current_monthly_rent_mf">Monthly Rent *</Label>
                            <Input
                              id="edit_current_monthly_rent_mf"
                              type="number"
                              min="0"
                              step="0.01"
                              value={propertyForm.current_monthly_rent}
                              onChange={(e) => {
                                const cleaned = e.target.value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1');
                                setPropertyForm({ ...propertyForm, current_monthly_rent: cleaned });
                              }}
                              className="text-sm"
                              required
                            />
                            <p className="text-xs text-gray-500 mt-1">Total monthly rent for all units</p>
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_monthly_rent_to_income_ratio_mf">R/I Ratio *</Label>
                            <Input
                              id="edit_monthly_rent_to_income_ratio_mf"
                              type="number"
                              step="0.01"
                              min="0"
                              value={propertyForm.monthly_rent_to_income_ratio}
                              onChange={(e) => {
                                const cleaned = e.target.value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1');
                                setPropertyForm({ ...propertyForm, monthly_rent_to_income_ratio: cleaned });
                              }}
                              className="text-sm"
                              placeholder="2.75"
                              required
                            />
                          </div>
                        </div>
                      </div>
                      <div className="border-t border-gray-200"></div>
                    </>
                  )}

                  {/* Section 5: Single Family Details (conditional) */}
                  {!isMultiUnit && (
                    <>
                      <div>
                        <h3 className="text-sm font-semibold text-gray-700 mb-3">Single Family Details</h3>
                        <div className="grid grid-cols-12 gap-4">
                          <div className="col-span-3">
                            <Label htmlFor="edit_bedrooms">Bedrooms *</Label>
                            <Input
                              id="edit_bedrooms"
                              type="number"
                              min="0"
                              step="1"
                              value={propertyForm.bedrooms}
                              onChange={(e) => handleInt64Change('bedrooms', e.target.value)}
                              className="text-sm"
                              required={!isMultiUnit}
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_bathrooms">Bathrooms *</Label>
                            <Input
                              id="edit_bathrooms"
                              type="number"
                              min="0"
                              step="0.5"
                              value={propertyForm.bathrooms}
                              onChange={(e) => handleFloat64Change('bathrooms', e.target.value)}
                              className="text-sm"
                              required={!isMultiUnit}
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_square_feet">Square Feet *</Label>
                            <Input
                              id="edit_square_feet"
                              type="number"
                              min="0"
                              step="1"
                              value={propertyForm.square_feet}
                              onChange={(e) => handleInt64Change('square_feet', e.target.value)}
                              className="text-sm"
                              required={!isMultiUnit}
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_year_built">Year Built *</Label>
                            <Input
                              id="edit_year_built"
                              type="number"
                              min="1800"
                              max="2100"
                              step="1"
                              value={propertyForm.year_built}
                              onChange={(e) => handleInt64Change('year_built', e.target.value)}
                              className="text-sm"
                              placeholder="e.g., 1985"
                              required
                            />
                          </div>
                          <div className="col-span-4">
                            <Label htmlFor="edit_current_monthly_rent">Monthly Rent *</Label>
                            <Input
                              id="edit_current_monthly_rent"
                              type="number"
                              min="0"
                              step="0.01"
                              value={propertyForm.current_monthly_rent}
                              onChange={(e) => handleFloat64Change('current_monthly_rent', e.target.value)}
                              className="text-sm"
                              required
                            />
                          </div>
                          <div className="col-span-3">
                            <Label htmlFor="edit_monthly_rent_to_income_ratio">R/I Ratio *</Label>
                            <Input
                              id="edit_monthly_rent_to_income_ratio"
                              type="number"
                              step="0.01"
                              min="0"
                              value={propertyForm.monthly_rent_to_income_ratio}
                              onChange={(e) => handleFloat64Change('monthly_rent_to_income_ratio', e.target.value)}
                              className="text-sm"
                              placeholder="2.75"
                              required
                            />
                          </div>
                        </div>
                      </div>
                      <div className="border-t border-gray-200"></div>
                    </>
                  )}

                  {/* Section 6: Notes */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Notes</h3>
                    <textarea
                      id="edit_notes"
                      value={propertyForm.notes}
                      onChange={(e) => setPropertyForm({ ...propertyForm, notes: e.target.value })}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                      placeholder="Additional details about the property..."
                    />
                  </div>
                </div>
                
                <div className="flex gap-2 mt-4">
                  <Button
                    type="button"
                    onClick={handleSaveProperty}
                    className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
                  >
                    <Check className="h-3 w-3 mr-1" />
                    Save Changes
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={cancelEditProperty}
                    className="h-8 text-xs"
                  >
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Property Information Card */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-bold">Property Information</CardTitle>
                  <Button
                    variant="outline"
                    onClick={startEditProperty}
                    className="h-8 text-xs"
                  >
                    <Edit2 className="h-3 w-3 mr-1.5" />
                    Edit Property
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-x-8 gap-y-4">
                <div>
                  <div className="text-sm text-gray-600">Address</div>
                  <div className="text-sm text-gray-900">
                    {property.address_line1 || 'N/A'}
                    {property.city && `, ${property.city}, ${property.state}`}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Property Type</div>
                  <div className="text-sm text-gray-900 capitalize">
                    {property.property_type?.replace('_', ' ') || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Purchase Price</div>
                  <div className="text-sm text-gray-900">
                    ${Math.round(property.purchase_price / 1000).toLocaleString()}k
                  </div>
                </div>
                {totalRehabExpenses > 0 && (
                  <div>
                    <div className="text-sm text-gray-600">Rehab Expenses</div>
                    <div className="text-sm text-gray-900">
                      ${Math.round(totalRehabExpenses / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.cash_invested !== null && property.cash_invested !== undefined && (
                  <div>
                    <div className="text-sm text-gray-600">Cash Invested (for CoC)</div>
                    <div className="text-sm text-gray-900 font-semibold">
                      ${Math.round(property.cash_invested / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.current_market_value !== null && property.current_market_value !== undefined && (
                  <div>
                    <div className="text-sm text-gray-600">Current Market Value</div>
                    <div className="text-sm text-gray-900">
                      ${Math.round(property.current_market_value / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.vacancy_rate !== undefined && property.vacancy_rate !== null && (
                  <div>
                    <div className="text-sm text-gray-600">Vacancy Rate</div>
                    <div className="text-sm text-gray-900">
                      {(property.vacancy_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
                <div>
                  <div className="text-sm text-gray-600">Property Status</div>
                  <div className="text-sm text-gray-900 capitalize flex items-center gap-2">
                    {property.property_status === 'own' && <Home className="h-4 w-4 text-green-600" />}
                    {property.property_status === 'evaluating' && <Eye className="h-4 w-4 text-blue-600" />}
                    {property.property_status === 'rehabbing' && <Hammer className="h-4 w-4 text-orange-600" />}
                    {property.property_status === 'listed_for_rent' && <ListChecks className="h-4 w-4 text-purple-600" />}
                    {property.property_status === 'listed_for_sale' && <Tag className="h-4 w-4 text-yellow-600" />}
                    {property.property_status === 'sold' && <ShoppingCart className="h-4 w-4 text-gray-600" />}
                    {property.property_status === 'rented' && <Key className="h-4 w-4 text-emerald-600" />}
                    {property.property_status === 'hide' && <Archive className="h-4 w-4 text-gray-400" />}
                    {property.property_status?.replace(/_/g, ' ') || 'N/A'}
                  </div>
                </div>
                {!isMultiUnit && (
                  <div>
                    <div className="text-sm text-gray-600">Monthly Rent</div>
                    <div className="text-sm text-gray-900">
                      ${property.current_monthly_rent?.toLocaleString() || 'N/A'}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Financial Performance Card */}
            {financialPerformance && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-bold">Financial Performance</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-x-8 gap-y-4">
                  <div>
                    <div className="text-sm text-gray-600">Total Revenue</div>
                    <div className="text-sm text-gray-900">
                      {new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: 'USD',
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      }).format(financialPerformance.ytd_total_revenue || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">IRS Revenue</div>
                    <div className="text-sm text-gray-900">
                      {new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: 'USD',
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      }).format(financialPerformance.ytd_rent)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">YTD Cost</div>
                    <div className="text-sm text-gray-900">
                      {new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: 'USD',
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      }).format(financialPerformance.ytd_expenses)}
                    </div>
                  </div>
                  <div className="col-span-2 grid grid-cols-2 gap-x-8">
                    <div>
                      <div className="text-sm text-gray-600">YTD IRS Profit / (Loss)</div>
                      <div className={`text-sm font-medium ${
                        financialPerformance.ytd_profit_loss >= 0 ? 'text-blue-600' : 'text-red-600'
                      }`}>
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format(financialPerformance.ytd_profit_loss)}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Cash Position</div>
                      <div className={`text-sm font-medium ${
                        ((financialPerformance.ytd_total_revenue || 0) - financialPerformance.ytd_expenses) >= 0 
                          ? 'text-blue-600' 
                          : 'text-red-600'
                      }`}>
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format((financialPerformance.ytd_total_revenue || 0) - financialPerformance.ytd_expenses)}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Details Card (for single-unit properties) */}
            {!isMultiUnit && (
              <Card>
                <CardHeader>
                  <CardTitle>Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {property.bedrooms !== null && property.bedrooms !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Bedrooms</div>
                      <div className="font-medium">{property.bedrooms}</div>
                    </div>
                  )}
                  {property.bathrooms !== null && property.bathrooms !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Bathrooms</div>
                      <div className="font-medium">{property.bathrooms}</div>
                    </div>
                  )}
                  {property.square_feet !== null && property.square_feet !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Square Feet</div>
                      <div className="font-medium">{property.square_feet.toLocaleString()}</div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Units Section (for multi-unit properties) */}
          {isMultiUnit && (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-bold">Units ({units.length})</CardTitle>
                  {!showAddUnit && !editingUnit && (
                    <Button
                      onClick={() => setShowAddUnit(true)}
                      variant="outline"
                      className="h-8 text-xs"
                    >
                      <Plus className="h-3 w-3 mr-1.5" />
                      Add Unit
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {loadingUnits ? (
                  <div className="text-gray-500 py-4">Loading units...</div>
                ) : (
                  <div className="space-y-4">
                    {/* Add Unit Form */}
                    {showAddUnit && (
                      <Card className="bg-blue-50 border-blue-200">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg">Add New Unit</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="col-span-2">
                              <Label htmlFor="new_unit_number">Unit Number *</Label>
                              <Input
                                id="new_unit_number"
                                value={unitForm.unit_number}
                                onChange={(e) => setUnitForm({ ...unitForm, unit_number: e.target.value })}
                                placeholder="e.g., Unit 1, 1A, Apt 201"
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_bedrooms">Bedrooms</Label>
                              <Input
                                id="new_bedrooms"
                                type="number"
                                min="0"
                                value={unitForm.bedrooms}
                                onChange={(e) => setUnitForm({ ...unitForm, bedrooms: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_bathrooms">Bathrooms</Label>
                              <Input
                                id="new_bathrooms"
                                type="number"
                                min="0"
                                step="0.5"
                                value={unitForm.bathrooms}
                                onChange={(e) => setUnitForm({ ...unitForm, bathrooms: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_sqft">Square Feet</Label>
                              <Input
                                id="new_sqft"
                                type="number"
                                min="0"
                                value={unitForm.square_feet}
                                onChange={(e) => setUnitForm({ ...unitForm, square_feet: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_rent">Monthly Rent</Label>
                              <Input
                                id="new_rent"
                                type="number"
                                step="0.01"
                                value={unitForm.current_monthly_rent}
                                onChange={(e) => setUnitForm({ ...unitForm, current_monthly_rent: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                          </div>
                          <div className="flex gap-2 mt-4">
                            <Button
                              type="button"
                              onClick={handleAddUnit}
                              disabled={!unitForm.unit_number}
                              size="sm"
                              className="bg-black text-white hover:bg-gray-800"
                            >
                              <Check className="h-4 w-4 mr-1" />
                              Save Unit
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={cancelEdit}
                              size="sm"
                            >
                              <X className="h-4 w-4 mr-1" />
                              Cancel
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Units Grid */}
                    {units.length === 0 && !showAddUnit ? (
                      <div className="text-gray-500 py-8 text-center">
                        No units added yet. Click "Add Unit" to get started.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {units.map((unit) => (
                          <Card key={unit.id} className={editingUnit === unit.id ? "bg-blue-50 border-blue-200" : "bg-gray-50"}>
                            {editingUnit === unit.id ? (
                              /* Edit Mode */
                              <>
                                <CardHeader className="pb-3">
                                  <CardTitle className="text-lg">Edit Unit</CardTitle>
                                </CardHeader>
                                <CardContent>
                                  <div className="space-y-3">
                                    <div>
                                      <Label htmlFor={`edit_unit_number_${unit.id}`}>Unit Number *</Label>
                                      <Input
                                        id={`edit_unit_number_${unit.id}`}
                                        value={unitForm.unit_number}
                                        onChange={(e) => setUnitForm({ ...unitForm, unit_number: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                      <div>
                                        <Label htmlFor={`edit_bedrooms_${unit.id}`}>Beds</Label>
                                        <Input
                                          id={`edit_bedrooms_${unit.id}`}
                                          type="number"
                                          min="0"
                                          value={unitForm.bedrooms}
                                          onChange={(e) => setUnitForm({ ...unitForm, bedrooms: e.target.value })}
                                          className="text-sm"
                                        />
                                      </div>
                                      <div>
                                        <Label htmlFor={`edit_bathrooms_${unit.id}`}>Baths</Label>
                                        <Input
                                          id={`edit_bathrooms_${unit.id}`}
                                          type="number"
                                          min="0"
                                          step="0.5"
                                          value={unitForm.bathrooms}
                                          onChange={(e) => setUnitForm({ ...unitForm, bathrooms: e.target.value })}
                                          className="text-sm"
                                        />
                                      </div>
                                    </div>
                                    <div>
                                      <Label htmlFor={`edit_sqft_${unit.id}`}>Sq Ft</Label>
                                      <Input
                                        id={`edit_sqft_${unit.id}`}
                                        type="number"
                                        min="0"
                                        value={unitForm.square_feet}
                                        onChange={(e) => setUnitForm({ ...unitForm, square_feet: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div>
                                      <Label htmlFor={`edit_rent_${unit.id}`}>Rent</Label>
                                      <Input
                                        id={`edit_rent_${unit.id}`}
                                        type="number"
                                        step="0.01"
                                        value={unitForm.current_monthly_rent}
                                        onChange={(e) => setUnitForm({ ...unitForm, current_monthly_rent: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="flex gap-2 pt-2">
                                      <Button
                                        type="button"
                                        onClick={() => handleEditUnit(unit.id)}
                                        disabled={!unitForm.unit_number}
                                        size="sm"
                                        className="flex-1 bg-black text-white hover:bg-gray-800"
                                      >
                                        <Check className="h-4 w-4 mr-1" />
                                        Save
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="outline"
                                        onClick={cancelEdit}
                                        size="sm"
                                        className="flex-1"
                                      >
                                        <X className="h-4 w-4 mr-1" />
                                        Cancel
                                      </Button>
                                    </div>
                                  </div>
                                </CardContent>
                              </>
                            ) : (
                              /* View Mode */
                              <>
                                <CardHeader className="pb-3">
                                  <div className="flex justify-between items-start">
                                    <CardTitle className="text-lg">{unit.unit_number}</CardTitle>
                                    <div className="flex gap-1">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => startEditUnit(unit)}
                                        className="h-7 w-7 p-0"
                                      >
                                        <Edit2 className="h-4 w-4" />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDeleteUnit(unit.id, unit.unit_number)}
                                        disabled={deletingUnit === unit.id}
                                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </div>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                  {unit.bedrooms !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Bedrooms:</span>
                                      <span className="text-gray-900">{unit.bedrooms}</span>
                                    </div>
                                  )}
                                  {unit.bathrooms !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Bathrooms:</span>
                                      <span className="text-gray-900">{unit.bathrooms}</span>
                                    </div>
                                  )}
                                  {unit.square_feet !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Sq Ft:</span>
                                      <span className="text-gray-900">{unit.square_feet.toLocaleString()}</span>
                                    </div>
                                  )}
                                  {unit.current_monthly_rent !== null && (
                                    <div className="flex justify-between text-sm border-t pt-2">
                                      <span className="text-gray-600">Rent:</span>
                                      <span className="text-gray-900">
                                        ${unit.current_monthly_rent.toLocaleString()}
                                      </span>
                                    </div>
                                  )}
                                </CardContent>
                              </>
                            )}
                          </Card>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {activeTab === 'performance' && (
        <FinancialPerformanceTab 
          propertyId={id}
          units={units}
          isMultiUnit={isMultiUnit}
        />
      )}

      {activeTab === 'financials' && (
        <ScheduledFinancialsTab 
          propertyId={id} 
          purchasePrice={property.purchase_price || 0}
        />
      )}

      {activeTab === 'down-payment' && (
        <RentAnalysisTab 
          propertyId={id}
          property={property || {}}
        />
      )}

      {activeTab === 'rent' && (
        <SetRentAnalysisTab 
          propertyId={id}
          property={property || {}}
        />
      )}

      {activeTab === 'comps' && (
        <ComparablesTab 
          propertyId={id}
        />
      )}
    </div>
  );
}
