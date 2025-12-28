'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Home, Save, Calendar, DollarSign, ArrowLeft, Camera, Upload, X, FileText } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useCreateRent, useCreateRentWithReceipt, useUpdateRent, useRent } from '@/lib/hooks/use-rent';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useSearchParams } from 'next/navigation';

interface Property {
  id: string;
  display_name?: string;
  address_line1?: string;
  property_type?: string;
  current_monthly_rent?: number;
}

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  current_monthly_rent: number | null;
}

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

// iOS-friendly accept string
const FILE_ACCEPT = 'image/*,application/pdf,.pdf,.jpg,.jpeg,.png,.gif,.webp,.heic,.heif';

export default function LogRentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rentId = searchParams.get('id');
  const isEditing = !!rentId;
  
  const createRent = useCreateRent();
  const createRentWithReceipt = useCreateRentWithReceipt();
  const updateRent = useUpdateRent();
  const { data: existingRent, isLoading: loadingRent } = useRent(rentId || '');
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Fetch tenants
  const { data: tenantsData } = useTenants();
  const tenants = tenantsData?.tenants || [];
  
  const [properties, setProperties] = useState<Property[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  
  // Default to current month
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;
  const monthStart = new Date(currentYear, currentMonth - 1, 1);
  const monthEnd = new Date(currentYear, currentMonth, 0);
  
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    tenant_id: '',
    amount: '',
    revenue_description: '', // Monthly Rent, Partial Month Rent, One Time Pet Fee, One Time Application Fee, Deposit, Other
    revenue_description_other: '', // Custom description when "Other" is selected
    is_non_irs_revenue: false, // Checkbox for non-IRS revenue (auto-checked for Deposit)
    is_one_time_fee: false, // Checkbox for one-time fee (pet fee, application fee, etc.)
    rent_period_month: currentMonth, // 1-12
    rent_period_year: currentYear,
    rent_period_start: monthStart.toISOString().split('T')[0], // Default to month start
    rent_period_end: monthEnd.toISOString().split('T')[0], // Default to month end
    use_custom_date_range: false, // Checkbox for custom date range
    payment_date: currentDate.toISOString().split('T')[0],
    payment_method: '',
    transaction_reference: '',
    is_late: false,
    late_fee: '',
    notes: '',
  });

  // Generate year options (current year - 2 to current year + 1)
  const yearOptions = useMemo(() => {
    const years = [];
    const currentYear = new Date().getFullYear();
    for (let y = currentYear - 2; y <= currentYear + 1; y++) {
      years.push(y);
    }
    return years;
  }, []);

  useEffect(() => {
    fetchProperties();
  }, []);

  // Load existing rent data when editing
  useEffect(() => {
    if (isEditing && existingRent) {
      // Populate form with existing rent data
      const rent = existingRent;
      const periodStart = rent.rent_period_start ? new Date(rent.rent_period_start).toISOString().split('T')[0] : monthStart.toISOString().split('T')[0];
      const periodEnd = rent.rent_period_end ? new Date(rent.rent_period_end).toISOString().split('T')[0] : monthEnd.toISOString().split('T')[0];
      
      setFormData({
        property_id: rent.property_id || '',
        unit_id: rent.unit_id || '',
        tenant_id: rent.tenant_id || '',
        amount: String(rent.amount || ''),
        revenue_description: rent.revenue_description || '',
        revenue_description_other: rent.revenue_description && !['Monthly Rent', 'Partial Month Rent', 'One Time Pet Fee', 'One Time Application Fee', 'Deposit'].includes(rent.revenue_description) ? rent.revenue_description : '',
        is_non_irs_revenue: rent.is_non_irs_revenue || false,
        is_one_time_fee: rent.is_one_time_fee || false,
        rent_period_month: (rent.rent_period_month !== undefined && rent.rent_period_month !== null) ? rent.rent_period_month : currentMonth,
        rent_period_year: (rent.rent_period_year !== undefined && rent.rent_period_year !== null) ? rent.rent_period_year : currentYear,
        rent_period_start: periodStart,
        rent_period_end: periodEnd,
        use_custom_date_range: rent.rent_period_start !== periodStart || rent.rent_period_end !== periodEnd,
        payment_date: rent.payment_date ? new Date(rent.payment_date).toISOString().split('T')[0] : currentDate.toISOString().split('T')[0],
        payment_method: rent.payment_method || '',
        transaction_reference: rent.transaction_reference || '',
        is_late: rent.is_late || false,
        late_fee: rent.late_fee ? String(rent.late_fee) : '',
        notes: rent.notes || '',
      });

      // Set selected property and fetch units if needed
      if (rent.property_id) {
        const property = properties.find(p => p.id === rent.property_id);
        if (property) {
          setSelectedProperty(property);
          if (property.property_type === 'multi_family' || property.property_type === 'duplex') {
            fetchUnits(rent.property_id);
          }
        }
      }
    }
  }, [isEditing, existingRent, properties]);

  useEffect(() => {
    if (formData.property_id) {
      const property = properties.find(p => p.id === formData.property_id);
      setSelectedProperty(property || null);
      
      if (property?.property_type === 'multi_family' || property?.property_type === 'duplex') {
        fetchUnits(formData.property_id);
      } else {
        setUnits([]);
        setFormData(prev => ({ ...prev, unit_id: '' }));
      }
    }
  }, [formData.property_id, properties]);

  // Create preview for selected file
  useEffect(() => {
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setFilePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  }, [file]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    setFile(selectedFile);
  };

  const clearFile = () => {
    setFile(null);
    setFilePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const fetchProperties = async () => {
    try {
      const response = await apiClient.get<{ items: Property[]; total: number }>('/properties');
      setProperties(response.items);
    } catch (err) {
      console.error('Error fetching properties:', err);
    }
  };

  const fetchUnits = async (propertyId: string) => {
    try {
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${propertyId}`);
      setUnits(response.items);
    } catch (err) {
      console.error('Error fetching units:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!formData.property_id || !formData.amount || !formData.payment_date) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      let rentPeriodStart = formData.rent_period_start;
      let rentPeriodEnd = formData.rent_period_end;
      let rentPeriodMonth: number | undefined = formData.rent_period_month;
      let rentPeriodYear: number | undefined = formData.rent_period_year;
      
      if (formData.is_one_time_fee) {
        // For one-time fees, use a single date
        rentPeriodStart = formData.rent_period_start || formData.payment_date;
        rentPeriodEnd = formData.rent_period_start || formData.payment_date; // Same date
        rentPeriodMonth = undefined;
        rentPeriodYear = undefined;
      } else {
        // For regular rent, calculate default dates if not using custom range
        if (!formData.use_custom_date_range) {
          // Calculate full month dates
          const year = formData.rent_period_year;
          const month = formData.rent_period_month;
          const startDate = new Date(year, month - 1, 1);
          const endDate = new Date(year, month, 0);
          rentPeriodStart = startDate.toISOString().split('T')[0];
          rentPeriodEnd = endDate.toISOString().split('T')[0];
        }
      }
      
      // Use custom description if "Other" is selected, otherwise use the selected option
      const revenueDescription = formData.revenue_description === 'Other' 
        ? formData.revenue_description_other 
        : formData.revenue_description || undefined;
      
      // Auto-check is_non_irs_revenue if Deposit, Deposit Payout, or Exit Deposit Deduction is selected
      const isNonIrsRevenue = (formData.revenue_description === 'Deposit' || 
                                formData.revenue_description === 'Deposit Payout' ||
                                formData.revenue_description === 'Exit Deposit Deduction')
        ? true 
        : formData.is_non_irs_revenue;
      
      // For Deposit Payout and Exit Deposit Deduction, allow negative amounts
      const amountValue = parseFloat(formData.amount);
      const finalAmount = ((formData.revenue_description === 'Deposit Payout' || 
                           formData.revenue_description === 'Exit Deposit Deduction') && 
                           amountValue > 0)
        ? -amountValue  // Make negative if positive amount entered for payout/deduction
        : amountValue;
      
      const payload = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        tenant_id: formData.tenant_id || undefined,
        amount: finalAmount,
        revenue_description: revenueDescription,
        is_non_irs_revenue: isNonIrsRevenue,
        is_one_time_fee: formData.is_one_time_fee,
        rent_period_month: rentPeriodMonth,
        rent_period_year: rentPeriodYear,
        rent_period_start: rentPeriodStart,
        rent_period_end: rentPeriodEnd,
        payment_date: formData.payment_date,
        payment_method: (formData.payment_method || undefined) as 'check' | 'cash' | 'electronic' | 'money_order' | 'other' | undefined,
        transaction_reference: formData.transaction_reference || undefined,
        is_late: formData.is_late,
        late_fee: formData.late_fee ? parseFloat(formData.late_fee) : undefined,
        notes: formData.notes || undefined,
      };

      // Log the payload for debugging
      console.log('📤 Rent Payment Payload:', JSON.stringify(payload, null, 2));

      if (isEditing && rentId) {
        // For updates, if file is provided, upload it first then update
        if (file) {
          // Upload document first
          const formDataToSend = new FormData();
          formDataToSend.append('file', file);
          formDataToSend.append('document_type', 'receipt');
          formDataToSend.append('property_id', formData.property_id);
          if (formData.unit_id) {
            formDataToSend.append('unit_id', formData.unit_id);
          }
          if (formData.tenant_id) {
            formDataToSend.append('tenant_id', formData.tenant_id);
          }
          
          const docResponse = await apiClient.upload<{ document: { id: string } }>('/documents/upload', formDataToSend);
          
          // Update rent with document_storage_id
          await updateRent.mutateAsync({ 
            id: rentId, 
            data: { ...payload, document_storage_id: docResponse.document.id }
          });
        } else {
          await updateRent.mutateAsync({ id: rentId, data: payload });
        }
      } else {
        // For creates, use with-receipt endpoint if file is provided
        if (file) {
          const formDataToSend = new FormData();
          formDataToSend.append('property_id', formData.property_id);
          if (formData.unit_id) formDataToSend.append('unit_id', formData.unit_id);
          if (formData.tenant_id) formDataToSend.append('tenant_id', formData.tenant_id);
          formDataToSend.append('amount', String(finalAmount));
          if (revenueDescription) formDataToSend.append('revenue_description', revenueDescription);
          formDataToSend.append('is_non_irs_revenue', String(isNonIrsRevenue));
          formDataToSend.append('is_one_time_fee', String(formData.is_one_time_fee));
          if (rentPeriodMonth) formDataToSend.append('rent_period_month', String(rentPeriodMonth));
          if (rentPeriodYear) formDataToSend.append('rent_period_year', String(rentPeriodYear));
          if (rentPeriodStart) formDataToSend.append('rent_period_start', rentPeriodStart);
          if (rentPeriodEnd) formDataToSend.append('rent_period_end', rentPeriodEnd);
          formDataToSend.append('payment_date', formData.payment_date);
          if (formData.payment_method) formDataToSend.append('payment_method', formData.payment_method);
          if (formData.transaction_reference) formDataToSend.append('transaction_reference', formData.transaction_reference);
          formDataToSend.append('is_late', String(formData.is_late));
          if (formData.late_fee) formDataToSend.append('late_fee', formData.late_fee);
          if (formData.notes) formDataToSend.append('notes', formData.notes);
          formDataToSend.append('file', file);
          formDataToSend.append('document_type', 'receipt');

          await createRentWithReceipt.mutateAsync(formDataToSend);
        } else {
          await createRent.mutateAsync(payload);
        }
      }
      router.push('/rent');
    } catch (err) {
      console.error('Error logging rent:', err);
      setError(`Failed to log rent payment: ${(err as Error).message}`);
    }
  };

  const isMultiUnit = selectedProperty?.property_type === 'multi_family' || 
                      selectedProperty?.property_type === 'duplex';

  const selectedUnit = units.find(u => u.id === formData.unit_id);
  const suggestedAmount = selectedUnit?.current_monthly_rent || selectedProperty?.current_monthly_rent || 0;

  const getMonthLabel = (month: number) => MONTHS.find(m => m.value === month)?.label || '';

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="mb-4 -ml-2 text-gray-600 hover:text-gray-900 h-8 text-xs"
        >
          <ArrowLeft className="h-3 w-3 mr-1.5" />
          Back
        </Button>
        <div className="text-xs text-gray-500 mb-1">{isEditing ? 'Editing:' : 'Recording:'}</div>
        <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-blue-600" />
          {isEditing ? 'Edit Rent Payment' : 'Log Rent Payment'}
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          {isEditing ? 'Update rent payment details' : 'Record a rent payment received from a tenant'}
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
          {error}
        </div>
      )}

      <Card className="border-gray-200 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-500" />
            Payment Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Property Selection */}
            <div>
              <Label htmlFor="property_id" className="text-xs font-medium text-gray-700">
                Property <span className="text-red-500">*</span>
              </Label>
              <Select
                value={formData.property_id}
                onValueChange={(value) => setFormData({ ...formData, property_id: value })}
              >
                <SelectTrigger className="text-xs mt-1.5 h-8">
                  <SelectValue placeholder="Select property" />
                </SelectTrigger>
                <SelectContent>
                  {properties.map((property) => (
                    <SelectItem key={property.id} value={property.id}>
                      {property.display_name || property.address_line1 || 'Unnamed Property'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Unit Selection (for multi-unit properties) */}
            {isMultiUnit && units.length > 0 && (
              <div>
                <Label htmlFor="unit_id" className="text-xs font-medium text-gray-700">
                  Unit <span className="text-red-500">*</span>
                </Label>
                <Select
                  value={formData.unit_id}
                  onValueChange={(value) => setFormData({ ...formData, unit_id: value })}
                >
                  <SelectTrigger className="text-xs mt-1.5 h-8">
                    <SelectValue placeholder="Select unit" />
                  </SelectTrigger>
                  <SelectContent>
                    {units.map((unit) => (
                      <SelectItem key={unit.id} value={unit.id}>
                        {unit.unit_number}
                        {unit.current_monthly_rent && ` - $${unit.current_monthly_rent.toLocaleString()}/mo`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Tenant Selection */}
            <div>
              <Label htmlFor="tenant_id" className="text-xs font-medium text-gray-700">
                Tenant (optional)
              </Label>
              <Select
                value={formData.tenant_id || undefined}
                onValueChange={(value) => setFormData({ ...formData, tenant_id: value === 'none' ? '' : value })}
              >
                <SelectTrigger className="text-xs mt-1.5 h-8">
                  <SelectValue placeholder="Select tenant (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {tenants.map((tenant) => (
                    <SelectItem key={tenant.id} value={tenant.id}>
                      {tenant.first_name} {tenant.last_name}
                      {tenant.email && ` (${tenant.email})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Rent Period (Month/Year) or One-Time Fee */}
            <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
              <Label className="text-xs font-medium text-gray-700 block mb-2">
                {formData.is_one_time_fee ? 'One-Time Fee Date' : 'Rent For Period'} <span className="text-red-500">*</span>
              </Label>
              
              {formData.is_one_time_fee ? (
                /* One-Time Fee: Single Date Input */
                <div>
                  <Label htmlFor="rent_period_start" className="text-[10px] text-gray-500">Fee Date</Label>
                  <Input
                    id="rent_period_start"
                    type="date"
                    value={formData.rent_period_start}
                    onChange={(e) => setFormData({ 
                      ...formData, 
                      rent_period_start: e.target.value,
                      rent_period_end: e.target.value, // Same date for one-time fees
                    })}
                    className="text-xs mt-1 h-8"
                  />
                  <p className="text-[10px] text-gray-500 mt-2">
                    One-time fee date: <span className="font-medium">{formData.rent_period_start}</span>
                  </p>
                </div>
              ) : (
                /* Regular Rent: Month/Year with Optional Custom Range */
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="rent_period_month" className="text-[10px] text-gray-500">Month</Label>
                      <Select
                        value={String(formData.rent_period_month)}
                        onValueChange={(value) => {
                          const month = parseInt(value);
                          const year = formData.rent_period_year;
                          const startDate = new Date(year, month - 1, 1);
                          const endDate = new Date(year, month, 0);
                          setFormData({ 
                            ...formData, 
                            rent_period_month: month,
                            rent_period_start: startDate.toISOString().split('T')[0],
                            rent_period_end: endDate.toISOString().split('T')[0],
                          });
                        }}
                      >
                        <SelectTrigger className="text-xs mt-1 h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {MONTHS.map((month) => (
                            <SelectItem key={month.value} value={String(month.value)}>
                              {month.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="rent_period_year" className="text-[10px] text-gray-500">Year</Label>
                      <Select
                        value={String(formData.rent_period_year)}
                        onValueChange={(value) => {
                          const year = parseInt(value);
                          const month = formData.rent_period_month;
                          const startDate = new Date(year, month - 1, 1);
                          const endDate = new Date(year, month, 0);
                          setFormData({ 
                            ...formData, 
                            rent_period_year: year,
                            rent_period_start: startDate.toISOString().split('T')[0],
                            rent_period_end: endDate.toISOString().split('T')[0],
                          });
                        }}
                      >
                        <SelectTrigger className="text-xs mt-1 h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {yearOptions.map((year) => (
                            <SelectItem key={year} value={String(year)}>
                              {year}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  {/* Custom Date Range Checkbox */}
                  <div className="mt-3 pt-3 border-t border-gray-300">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="use_custom_date_range"
                        checked={formData.use_custom_date_range}
                        onChange={(e) => setFormData({ ...formData, use_custom_date_range: e.target.checked })}
                        className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <Label htmlFor="use_custom_date_range" className="text-xs font-medium text-gray-700 cursor-pointer">
                        Use custom date range (not full month)
                      </Label>
                    </div>
                    
                    {/* Custom Date Range Inputs */}
                    {formData.use_custom_date_range && (
                      <div className="grid grid-cols-2 gap-3 mt-3">
                        <div>
                          <Label htmlFor="rent_period_start" className="text-[10px] text-gray-500">Start Date</Label>
                          <Input
                            id="rent_period_start"
                            type="date"
                            value={formData.rent_period_start}
                            onChange={(e) => setFormData({ ...formData, rent_period_start: e.target.value })}
                            className="text-xs mt-1 h-8"
                          />
                        </div>
                        <div>
                          <Label htmlFor="rent_period_end" className="text-[10px] text-gray-500">End Date</Label>
                          <Input
                            id="rent_period_end"
                            type="date"
                            value={formData.rent_period_end}
                            onChange={(e) => setFormData({ ...formData, rent_period_end: e.target.value })}
                            className="text-xs mt-1 h-8"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                  
                  <p className="text-[10px] text-gray-500 mt-2">
                    Recording rent for: <span className="font-medium">{getMonthLabel(formData.rent_period_month)} {formData.rent_period_year}</span>
                    {formData.use_custom_date_range && (
                      <span className="ml-2 text-orange-600">
                        ({formData.rent_period_start} to {formData.rent_period_end})
                      </span>
                    )}
                  </p>
                </>
              )}
            </div>

            {/* Amount and Payment Date */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="amount" className="text-xs font-medium text-gray-700">
                  Amount <span className="text-red-500">*</span>
                </Label>
                <div className="relative mt-1.5">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-xs">$</span>
                  <Input
                    id="amount"
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    required
                    className="text-xs pl-7 h-8"
                    placeholder={suggestedAmount ? suggestedAmount.toLocaleString() : '0.00'}
                  />
                </div>
                {suggestedAmount > 0 && (
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, amount: String(suggestedAmount) })}
                    className="text-[10px] text-blue-600 hover:text-blue-800 mt-1"
                  >
                    Use expected: ${suggestedAmount.toLocaleString()}
                  </button>
                )}
              </div>

              <div>
                <Label htmlFor="payment_date" className="text-xs font-medium text-gray-700">
                  Payment Date <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="payment_date"
                  type="date"
                  value={formData.payment_date}
                  onChange={(e) => setFormData({ ...formData, payment_date: e.target.value })}
                  required
                  className="text-xs mt-1.5 h-8"
                />
              </div>
            </div>

            {/* Revenue Description */}
            <div>
              <Label htmlFor="revenue_description" className="text-xs font-medium text-gray-700">
                Revenue Description
              </Label>
              <Select
                value={formData.revenue_description}
                onValueChange={(value) => {
                  const isDeposit = value === 'Deposit' || value === 'Deposit Payout' || value === 'Exit Deposit Deduction';
                  // Auto-set as one-time fee for Exit Deposit Deduction
                  const isOneTimeFee = value === 'Exit Deposit Deduction' || 
                                      value === 'One Time Pet Fee' || 
                                      value === 'One Time Application Fee';
                  
                  setFormData({ 
                    ...formData, 
                    revenue_description: value,
                    is_non_irs_revenue: isDeposit ? true : formData.is_non_irs_revenue, // Auto-check for Deposit/Deposit Payout/Exit Deposit Deduction
                    is_one_time_fee: isOneTimeFee ? true : formData.is_one_time_fee,
                  });
                }}
              >
                <SelectTrigger className="text-xs mt-1.5 h-8">
                  <SelectValue placeholder="Select revenue type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Monthly Rent">Monthly Rent</SelectItem>
                  <SelectItem value="Partial Month Rent">Partial Month Rent</SelectItem>
                  <SelectItem value="One Time Pet Fee">One Time Pet Fee</SelectItem>
                  <SelectItem value="One Time Application Fee">One Time Application Fee</SelectItem>
                  <SelectItem value="Deposit">Deposit</SelectItem>
                  <SelectItem value="Deposit Payout">Deposit Payout</SelectItem>
                  <SelectItem value="Exit Deposit Deduction">Exit Deposit Deduction</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
              
              {/* Custom description input when "Other" is selected */}
              {formData.revenue_description === 'Other' && (
                <Input
                  id="revenue_description_other"
                  type="text"
                  placeholder="Enter custom revenue description"
                  value={formData.revenue_description_other}
                  onChange={(e) => setFormData({ ...formData, revenue_description_other: e.target.value })}
                  className="text-xs mt-2 h-8"
                />
              )}
            </div>

            {/* One-Time Fee Checkbox - After Revenue Description */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_one_time_fee"
                checked={formData.is_one_time_fee}
                onChange={(e) => {
                  const isOneTime = e.target.checked;
                  if (isOneTime) {
                    // When switching to one-time fee, set date to payment date
                    setFormData({ 
                      ...formData, 
                      is_one_time_fee: true,
                      rent_period_start: formData.payment_date,
                      rent_period_end: formData.payment_date,
                    });
                  } else {
                    // When switching back to regular rent, reset to current month
                    const year = currentYear;
                    const month = currentMonth;
                    const startDate = new Date(year, month - 1, 1);
                    const endDate = new Date(year, month, 0);
                    setFormData({ 
                      ...formData, 
                      is_one_time_fee: false,
                      rent_period_month: month,
                      rent_period_year: year,
                      rent_period_start: startDate.toISOString().split('T')[0],
                      rent_period_end: endDate.toISOString().split('T')[0],
                      use_custom_date_range: false,
                    });
                  }
                }}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <Label htmlFor="is_one_time_fee" className="text-xs font-medium text-gray-700 cursor-pointer">
                One-time payment (e.g., pet fee, application fee)
              </Label>
            </div>

            {/* Non-IRS Revenue Checkbox */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_non_irs_revenue"
                checked={formData.is_non_irs_revenue}
                onChange={(e) => setFormData({ ...formData, is_non_irs_revenue: e.target.checked })}
                disabled={formData.revenue_description === 'Deposit' || formData.revenue_description === 'Deposit Payout' || formData.revenue_description === 'Exit Deposit Deduction'} // Disabled when Deposit/Deposit Payout/Exit Deposit Deduction is selected (auto-checked)
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <Label htmlFor="is_non_irs_revenue" className="text-xs font-medium text-gray-700 cursor-pointer">
                Non-IRS Revenue {(formData.revenue_description === 'Deposit' || formData.revenue_description === 'Deposit Payout' || formData.revenue_description === 'Exit Deposit Deduction') && <span className="text-gray-500">(auto-checked for deposits)</span>}
              </Label>
            </div>
            
            {/* Deposit Payout Helper Text */}
            {formData.revenue_description === 'Deposit Payout' && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-2 text-xs text-purple-700">
                💡 <strong>Note:</strong> Enter the payout amount as a positive number. It will be recorded as a negative amount to reduce the deposit balance.
              </div>
            )}
            
            {/* Exit Deposit Deduction Helper Text */}
            {formData.revenue_description === 'Exit Deposit Deduction' && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-2 text-xs text-orange-700">
                💡 <strong>Note:</strong> Enter the deduction amount as a positive number. It will be recorded as a negative amount (one-time revenue) to reduce the deposit balance.
              </div>
            )}

            {/* Payment Method and Reference */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="payment_method" className="text-xs font-medium text-gray-700">
                  Payment Method
                </Label>
                <Select
                  value={formData.payment_method}
                  onValueChange={(value) => setFormData({ ...formData, payment_method: value })}
                >
                  <SelectTrigger className="text-xs mt-1.5 h-8">
                    <SelectValue placeholder="Select method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="check">Check</SelectItem>
                    <SelectItem value="cash">Cash</SelectItem>
                    <SelectItem value="electronic">Electronic Transfer</SelectItem>
                    <SelectItem value="money_order">Money Order</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="transaction_reference" className="text-xs font-medium text-gray-700">
                  Reference # / Check #
                </Label>
                <Input
                  id="transaction_reference"
                  value={formData.transaction_reference}
                  onChange={(e) => setFormData({ ...formData, transaction_reference: e.target.value })}
                  className="text-xs mt-1.5 h-8"
                  placeholder="e.g., Check #1234"
                />
              </div>
            </div>

            {/* Late Payment Section */}
            <div className="border border-orange-200 rounded-lg p-3 bg-orange-50/50">
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  id="is_late"
                  checked={formData.is_late}
                  onChange={(e) => setFormData({ ...formData, is_late: e.target.checked })}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-orange-600 focus:ring-orange-500"
                />
                <Label htmlFor="is_late" className="text-xs font-medium text-gray-700 cursor-pointer">
                  This payment was late
                </Label>
              </div>
              {formData.is_late && (
                <div>
                  <Label htmlFor="late_fee" className="text-xs font-medium text-gray-700">
                    Late Fee Amount
                  </Label>
                  <div className="relative mt-1.5">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-xs">$</span>
                    <Input
                      id="late_fee"
                      type="number"
                      step="0.01"
                      min="0"
                      value={formData.late_fee}
                      onChange={(e) => setFormData({ ...formData, late_fee: e.target.value })}
                      className="text-xs pl-7 max-w-[200px] h-8"
                      placeholder="0.00"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Receipt/Photo Upload */}
            <div>
              <Label className="text-xs font-medium text-gray-700">
                Receipt/Image (Optional)
              </Label>
              <div className="mt-1.5">
                {file ? (
                  <div className="border-2 border-green-300 bg-green-50 rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      {filePreview ? (
                        <img 
                          src={filePreview} 
                          alt="Preview" 
                          className="h-12 w-12 object-cover rounded-lg shadow-sm"
                        />
                      ) : file.type === 'application/pdf' ? (
                        <div className="h-12 w-12 bg-red-100 rounded-lg flex items-center justify-center">
                          <FileText className="h-6 w-6 text-red-600" />
                        </div>
                      ) : (
                        <div className="h-12 w-12 bg-gray-200 rounded-lg flex items-center justify-center">
                          <FileText className="h-6 w-6 text-gray-500" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate text-xs">{file.name}</p>
                        <p className="text-[10px] text-gray-500">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={clearFile}
                        className="h-8 w-8 p-0 text-gray-500 hover:text-red-600"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-gray-400 active:bg-gray-50 transition-colors"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 rounded-full">
                          <Camera className="h-4 w-4 text-blue-600" />
                        </div>
                        <div className="p-2 bg-gray-100 rounded-full">
                          <Upload className="h-4 w-4 text-gray-600" />
                        </div>
                      </div>
                      <p className="text-xs font-medium text-gray-700 mt-1">
                        Tap to take photo or upload
                      </p>
                      <p className="text-[10px] text-gray-500">
                        Supports photos, PDF, JPEG, PNG (max 10MB)
                      </p>
                    </div>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={FILE_ACCEPT}
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <Label htmlFor="notes" className="text-xs font-medium text-gray-700">
                Notes
              </Label>
              <Input
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="text-xs mt-1.5 h-8"
                placeholder="Any additional notes..."
              />
            </div>

            {/* Submit Buttons */}
            <div className="flex gap-2 pt-3 border-t border-gray-200">
              <Button
                type="submit"
                disabled={createRent.isPending}
                className="bg-black text-white hover:bg-gray-800 h-8 text-xs px-4"
              >
                <Save className="h-3 w-3 mr-1.5" />
                {createRent.isPending ? 'Saving...' : 'Log Rent Payment'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                disabled={createRent.isPending}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
