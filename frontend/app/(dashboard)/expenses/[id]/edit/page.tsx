'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useExpense, useUpdateExpense } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api-client';
import { format } from 'date-fns';
import { FileText, Upload, Check } from 'lucide-react';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  current_monthly_rent: number | null;
  is_active: boolean;
}

export default function EditExpensePage() {
  const router = useRouter();
  const params = useParams();
  const expenseId = params.id as string;
  
  console.log(`[PAGE] 📄 EditExpensePage mounted for expense ${expenseId}`);
  
  const { data: expense, isLoading: loadingExpense, refetch } = useExpense(expenseId);
  const { data: properties } = usePropertiesHook();
  const updateExpense = useUpdateExpense();
  
  const [loading, setLoading] = useState(false);
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [error, setError] = useState('');
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [receiptUploaded, setReceiptUploaded] = useState(false);
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

  // Load expense data when it arrives
  useEffect(() => {
    if (expense) {
      console.log(`[PAGE] 📝 Expense data loaded, populating form`, expense);
      setFormData({
        property_id: expense.property_id || '',
        unit_id: expense.unit_id || '',
        description: expense.description || '',
        date: expense.date || format(new Date(), 'yyyy-MM-dd'),
        amount: String(expense.amount) || '',
        vendor: expense.vendor || '',
        expense_type: expense.expense_type || 'maintenance',
        expense_category: expense.expense_category || 'bulk_comm',
        notes: expense.notes || '',
      });
      // Fetch units for this property
      if (expense.property_id) {
        fetchUnits(expense.property_id);
      }
    }
  }, [expense]);

  const fetchUnits = async (propertyId: string) => {
    try {
      console.log(`[PAGE] 🏢 Fetching units for property ${propertyId}`);
      const start = performance.now();
      setLoadingUnits(true);
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${propertyId}`);
      setUnits(response.items.filter(u => u.is_active));
      const duration = performance.now() - start;
      console.log(`[PAGE] ✅ Units loaded in ${duration.toFixed(0)}ms:`, response.items.length, 'units');
    } catch (err) {
      console.error('[PAGE] ❌ Error fetching units:', err);
      setUnits([]);
    } finally {
      setLoadingUnits(false);
    }
  };

  const handlePropertyChange = (propertyId: string) => {
    setFormData({ ...formData, property_id: propertyId, unit_id: '' });
    if (propertyId) {
      fetchUnits(propertyId);
    } else {
      setUnits([]);
    }
  };

  const handleUploadReceipt = async () => {
    if (!file || !expense) return;
    
    setUploadingReceipt(true);
    setError('');
    
    try {
      // Upload document first
      const formDataToSend = new FormData();
      formDataToSend.append('file', file);
      formDataToSend.append('document_type', 'receipt');
      formDataToSend.append('property_id', expense.property_id);
      if (expense.unit_id) {
        formDataToSend.append('unit_id', expense.unit_id);
      }
      
      const docResponse = await apiClient.upload<{ document: { id: string } }>('/documents/upload', formDataToSend);
      
      // Update expense with document_storage_id
      await updateExpense.mutateAsync({
        id: expenseId,
        data: {
          document_storage_id: docResponse.document.id,
        },
      });
      
      setReceiptUploaded(true);
      setFile(null);
      refetch(); // Refresh expense data
    } catch (err) {
      console.error('Error uploading receipt:', err);
      setError('Failed to upload receipt: ' + (err as Error).message);
    } finally {
      setUploadingReceipt(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await updateExpense.mutateAsync({
        id: expenseId,
        data: {
          description: formData.description,
          date: formData.date,
          amount: parseFloat(formData.amount),
          vendor: formData.vendor || undefined,
          expense_type: formData.expense_type as any,
          expense_category: formData.expense_category as any,
          unit_id: formData.unit_id || undefined,
          notes: formData.notes || undefined,
        },
      });
      
      router.push('/expenses');
    } catch (err) {
      console.error('❌ [EXPENSE] Error updating expense:', err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const hasUnits = units.length > 0;
  const hasReceipt = expense?.document_storage_id;

  console.log(`[PAGE] 📊 Render state:`, {
    loadingExpense,
    hasExpense: !!expense,
    propertiesCount: properties?.items?.length || 0,
    unitsCount: units.length,
    loadingUnits
  });

  if (loadingExpense) {
    console.log(`[PAGE] ⏳ Loading expense ${expenseId}...`);
    return (
      <div className="p-4">
        <div className="text-sm text-gray-500">Loading expense...</div>
      </div>
    );
  }

  if (!expense) {
    console.log(`[PAGE] ❌ Expense ${expenseId} not found`);
    return (
      <div className="p-4">
        <div className="text-sm text-red-500">Expense not found</div>
      </div>
    );
  }

  console.log(`[PAGE] ✅ Rendering expense form for ${expenseId}`);

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-bold text-gray-900">Edit Expense</h1>
        <p className="text-xs text-gray-600 mt-0.5">Update expense details</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm">Expense Details</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="property_id" className="text-xs">Property *</Label>
                <select
                  id="property_id"
                  value={formData.property_id}
                  onChange={(e) => handlePropertyChange(e.target.value)}
                  required
                  className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm mt-1 !bg-white"
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
                <Label htmlFor="date" className="text-xs">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  required
                  className="text-sm mt-1"
                />
              </div>

              {/* Unit selector - only show if property has units */}
              {formData.property_id && (
                <div className="col-span-2">
                  <Label htmlFor="unit_id" className="text-xs">
                    Unit {hasUnits ? '(optional)' : ''}
                  </Label>
                  {loadingUnits ? (
                    <div className="text-xs text-gray-500 mt-1">Loading units...</div>
                  ) : hasUnits ? (
                    <select
                      id="unit_id"
                      value={formData.unit_id}
                      onChange={(e) => setFormData({ ...formData, unit_id: e.target.value })}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm mt-1 !bg-white"
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

              <div className="col-span-2">
                <Label htmlFor="description" className="text-xs">Description *</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  required
                  className="text-sm mt-1"
                  placeholder="e.g., Plumbing repair, Paint, HVAC service"
                />
              </div>
              <div>
                <Label htmlFor="amount" className="text-xs">Amount *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  required
                  className="text-sm mt-1"
                  placeholder="0.00"
                />
              </div>
              <div>
                <Label htmlFor="expense_type" className="text-xs">Expense Type *</Label>
                <select
                  id="expense_type"
                  value={formData.expense_type}
                  onChange={(e) => setFormData({ ...formData, expense_type: e.target.value })}
                  required
                  className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm mt-1 !bg-white"
                >
                  <option value="maintenance">Maintenance</option>
                  <option value="capex">Capital Expenditure</option>
                  <option value="rehab">Rehab</option>
                  <option value="pandi">Principal & Interest</option>
                  <option value="utilities">Utilities</option>
                  <option value="insurance">Insurance</option>
                  <option value="property_management">Property Management</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <Label htmlFor="expense_category" className="text-xs">Cost Code</Label>
                <select
                  id="expense_category"
                  value={formData.expense_category}
                  onChange={(e) => setFormData({ ...formData, expense_category: e.target.value })}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm mt-1 !bg-white"
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
              <div>
                <Label htmlFor="vendor" className="text-xs">Vendor</Label>
                <Input
                  id="vendor"
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  className="text-sm mt-1"
                  placeholder="e.g., Home Depot, Plumber LLC"
                />
              </div>
              
              {/* Receipt Section */}
              <div className="col-span-2">
                <Label className="text-xs">Receipt/Invoice</Label>
                <div className="mt-1 p-3 bg-gray-50 rounded-md border">
                  {hasReceipt ? (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-green-700">
                        <Check className="h-4 w-4" />
                        <span>Receipt attached</span>
                      </div>
                      <ReceiptViewer expenseId={expenseId} />
                    </div>
                  ) : receiptUploaded ? (
                    <div className="flex items-center gap-2 text-sm text-green-700">
                      <Check className="h-4 w-4" />
                      <span>Receipt uploaded successfully!</span>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <FileText className="h-4 w-4" />
                        <span>No receipt attached</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Input
                          id="file"
                          type="file"
                          accept="image/*,.pdf"
                          onChange={(e) => setFile(e.target.files?.[0] || null)}
                          className="text-xs flex-1"
                        />
                        {file && (
                          <Button
                            type="button"
                            size="sm"
                            onClick={handleUploadReceipt}
                            disabled={uploadingReceipt}
                            className="h-8 text-xs"
                          >
                            <Upload className="h-3 w-3 mr-1" />
                            {uploadingReceipt ? 'Uploading...' : 'Upload'}
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="col-span-2">
                <Label htmlFor="notes" className="text-xs">Notes</Label>
                <textarea
                  id="notes"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={2}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm mt-1 !bg-white"
                  placeholder="Additional details..."
                />
              </div>
            </div>

            {error && (
              <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <Button
                type="submit"
                size="sm"
                className="bg-black text-white hover:bg-gray-800"
                disabled={loading}
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
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
