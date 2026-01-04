'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateExpense, useCreateExpenseWithReceipt } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api-client';
import { format } from 'date-fns';
import { Camera, Upload, X, FileText, Image } from 'lucide-react';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  current_monthly_rent: number | null;
  is_active: boolean;
}

// iOS-friendly accept string
const FILE_ACCEPT = 'image/*,application/pdf,.pdf,.jpg,.jpeg,.png,.gif,.webp,.heic,.heif';

export default function AddExpensePage() {
  const router = useRouter();
  const { data: properties } = usePropertiesHook();
  const createExpense = useCreateExpense();
  const createExpenseWithReceipt = useCreateExpenseWithReceipt();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(false);
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    description: '',
    date: format(new Date(), 'yyyy-MM-dd'),
    amount: '',
    vendor: '',
    expense_type: 'maintenance',
    expense_category: 'bulk_comm',
    notes: '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);

  // Fetch units when property changes
  useEffect(() => {
    if (formData.property_id) {
      fetchUnits(formData.property_id);
    } else {
      setUnits([]);
      setFormData(prev => ({ ...prev, unit_id: '' }));
    }
  }, [formData.property_id]);

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

  const fetchUnits = async (propertyId: string) => {
    try {
      setLoadingUnits(true);
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${propertyId}`);
      setUnits(response.items.filter(u => u.is_active));
    } catch (err) {
      console.error('Error fetching units:', err);
      setUnits([]);
    } finally {
      setLoadingUnits(false);
    }
  };

  const handlePropertyChange = (propertyId: string) => {
    setFormData({ ...formData, property_id: propertyId, unit_id: '' });
  };

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    console.log('📝 [EXPENSE] Creating expense:', formData);

    try {
      if (file) {
        // Use with-receipt endpoint if file is provided
        console.log('📤 [EXPENSE] POST /api/v1/expenses/with-receipt - Request');
        const formDataToSend = new FormData();
        formDataToSend.append('property_id', formData.property_id);
        formDataToSend.append('description', formData.description);
        formDataToSend.append('date', formData.date);
        formDataToSend.append('amount', formData.amount);
        formDataToSend.append('expense_type', formData.expense_type);
        if (formData.expense_category) formDataToSend.append('expense_category', formData.expense_category);
        if (formData.unit_id) formDataToSend.append('unit_id', formData.unit_id);
        if (formData.vendor) formDataToSend.append('vendor', formData.vendor);
        if (formData.notes) formDataToSend.append('notes', formData.notes);
        formDataToSend.append('file', file);
        formDataToSend.append('document_type', 'receipt');

        const response = await createExpenseWithReceipt.mutateAsync(formDataToSend);
        console.log('✅ [EXPENSE] POST /api/v1/expenses/with-receipt - Response:', response);
      } else {
        // Use regular endpoint if no file
        console.log('📤 [EXPENSE] POST /api/v1/expenses - Request (no receipt)');
        const expenseData = {
          property_id: formData.property_id,
          description: formData.description,
          date: formData.date,
          amount: parseFloat(formData.amount),
          expense_type: formData.expense_type,
          expense_category: formData.expense_category || undefined,
          unit_id: formData.unit_id || undefined,
          vendor: formData.vendor || undefined,
          notes: formData.notes || undefined,
        };

        const response = await createExpense.mutateAsync(expenseData);
        console.log('✅ [EXPENSE] POST /api/v1/expenses - Response:', response);
      }
      
      console.log('📝 [EXPENSE] Backend to PostgreSQL/Lakekeeper: Expense created');
      
      router.push('/expenses');
    } catch (err) {
      console.error('❌ [EXPENSE] Error creating expense:', err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const selectedProperty = properties?.items.find(p => p.id === formData.property_id);
  const hasUnits = units.length > 0;
  const isPdf = file?.type === 'application/pdf';

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg md:text-xl font-bold text-gray-900">Add Expense</h1>
        <p className="text-xs md:text-sm text-gray-600 mt-0.5">Record a new property expense</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm">Expense Details</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Responsive grid - 1 col on mobile, 2 on desktop */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="property_id" className="text-xs md:text-sm">Property *</Label>
                <select
                  id="property_id"
                  value={formData.property_id}
                  onChange={(e) => handlePropertyChange(e.target.value)}
                  required
                  className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                >
                  <option value="">Select Property</option>
                  {properties?.items.map((prop) => (
                    <option key={prop.id} value={prop.id}>
                      {prop.display_name || prop.address_line1 || prop.id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="date" className="text-xs md:text-sm">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  required
                  className="text-base md:text-sm mt-1 min-h-[44px]"
                />
              </div>

              {/* Unit selector - only show if property has units */}
              {formData.property_id && (
                <div className="md:col-span-2">
                  <Label htmlFor="unit_id" className="text-xs md:text-sm">
                    Unit {hasUnits ? '(optional)' : ''}
                  </Label>
                  {loadingUnits ? (
                    <div className="text-xs text-gray-500 mt-1">Loading units...</div>
                  ) : hasUnits ? (
                    <select
                      id="unit_id"
                      value={formData.unit_id}
                      onChange={(e) => setFormData({ ...formData, unit_id: e.target.value })}
                      className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                    >
                      <option value="">Property-level expense (no specific unit)</option>
                      {units.map((unit) => (
                        <option key={unit.id} value={unit.id}>
                          Unit {unit.unit_number}
                          {unit.current_monthly_rent ? ` - $${unit.current_monthly_rent}/mo` : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="text-xs text-gray-500 mt-1 italic">
                      No units - expense will be assigned to property
                    </div>
                  )}
                </div>
              )}

              <div className="md:col-span-2">
                <Label htmlFor="description" className="text-xs md:text-sm">Description *</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  required
                  className="text-base md:text-sm mt-1 min-h-[44px]"
                  placeholder="e.g., Plumbing repair, Paint, HVAC service"
                />
              </div>
              <div>
                <Label htmlFor="amount" className="text-xs md:text-sm">Amount *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0"
                  inputMode="decimal"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  required
                  className="text-base md:text-sm mt-1 min-h-[44px]"
                  placeholder="0.00"
                />
              </div>
              <div>
                <Label htmlFor="expense_type" className="text-xs md:text-sm">Expense Type *</Label>
                <select
                  id="expense_type"
                  value={formData.expense_type}
                  onChange={(e) => setFormData({ ...formData, expense_type: e.target.value })}
                  required
                  className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                >
                  <option value="maintenance">Maintenance</option>
                  <option value="capex">Capital Expenditure</option>
                  <option value="rehab">Rehab</option>
                  <option value="pandi">Principal & Interest</option>
                  <option value="tax">Tax</option>
                  <option value="utilities">Utilities</option>
                  <option value="insurance">Insurance</option>
                  <option value="property_management">Property Management</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <Label htmlFor="expense_category" className="text-xs md:text-sm">Cost Code</Label>
                <select
                  id="expense_category"
                  value={formData.expense_category}
                  onChange={(e) => setFormData({ ...formData, expense_category: e.target.value })}
                  className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                >
                  <option value="co_equip">10 - Co. Equipment</option>
                  <option value="rent_equip">20 - Rented Equip.</option>
                  <option value="equip_maint">30 - Equip. Maint.</option>
                  <option value="small_tools">40 - Small Tools</option>
                  <option value="bulk_comm">50 - Bulk Commodities</option>
                  <option value="eng_equip">60 - Eng. Equipment</option>
                  <option value="subs">70 - Subcontractors</option>
                  <option value="other">80 - Other</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="vendor" className="text-xs md:text-sm">Vendor</Label>
                <Input
                  id="vendor"
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  className="text-base md:text-sm mt-1 min-h-[44px]"
                  placeholder="e.g., Home Depot, Plumber LLC"
                />
              </div>
              
              {/* Receipt/Photo Upload - Mobile Friendly */}
              <div className="md:col-span-2">
                <Label className="text-xs md:text-sm">Receipt/Invoice (Optional)</Label>
                <div className="mt-2">
                  {file ? (
                    // File Selected Preview
                    <div className="border-2 border-green-300 bg-green-50 rounded-lg p-4">
                      <div className="flex items-center gap-3">
                        {filePreview ? (
                          <img 
                            src={filePreview} 
                            alt="Preview" 
                            className="h-16 w-16 object-cover rounded-lg shadow-sm"
                          />
                        ) : isPdf ? (
                          <div className="h-16 w-16 bg-red-100 rounded-lg flex items-center justify-center">
                            <FileText className="h-8 w-8 text-red-600" />
                          </div>
                        ) : (
                          <div className="h-16 w-16 bg-gray-200 rounded-lg flex items-center justify-center">
                            <FileText className="h-8 w-8 text-gray-500" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate text-sm">{file.name}</p>
                          <p className="text-xs text-gray-500">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={clearFile}
                          className="h-10 w-10 p-0 text-gray-500 hover:text-red-600"
                        >
                          <X className="h-5 w-5" />
                        </Button>
                      </div>
                    </div>
                  ) : (
                    // File Upload Area
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400 active:bg-gray-50 transition-colors"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-blue-100 rounded-full">
                            <Camera className="h-6 w-6 text-blue-600" />
                          </div>
                          <div className="p-3 bg-gray-100 rounded-full">
                            <Upload className="h-6 w-6 text-gray-600" />
                          </div>
                        </div>
                        <p className="text-sm font-medium text-gray-700 mt-2">
                          Tap to take photo or upload
                        </p>
                        <p className="text-xs text-gray-500">
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
              
              <div className="md:col-span-2">
                <Label htmlFor="notes" className="text-xs md:text-sm">Notes</Label>
                <textarea
                  id="notes"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-md text-base md:text-sm mt-1"
                  placeholder="Additional details..."
                />
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
                {error}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button
                type="submit"
                className="bg-black text-white hover:bg-gray-800 min-h-[48px] flex-1 sm:flex-none"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Expense'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="min-h-[48px]"
                onClick={() => router.back()}
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
