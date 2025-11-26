'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateExpenseWithReceipt } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { format } from 'date-fns';

export default function AddExpensePage() {
  const router = useRouter();
  const { data: properties } = usePropertiesHook();
  const createExpense = useCreateExpenseWithReceipt();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    property_id: '',
    description: '',
    date: format(new Date(), 'yyyy-MM-dd'),
    amount: '',
    vendor: '',
    expense_type: 'maintenance',
    is_planned: false,
    notes: '',
  });
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    console.log('📝 [EXPENSE] Creating expense:', formData);
    console.log('📤 [EXPENSE] POST /api/v1/expenses/with-receipt - Request');

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('property_id', formData.property_id);
      formDataToSend.append('description', formData.description);
      formDataToSend.append('date', formData.date);
      formDataToSend.append('amount', formData.amount);
      formDataToSend.append('expense_type', formData.expense_type);
      formDataToSend.append('is_planned', formData.is_planned.toString());
      if (formData.vendor) formDataToSend.append('vendor', formData.vendor);
      if (formData.notes) formDataToSend.append('notes', formData.notes);
      if (file) {
        formDataToSend.append('file', file);
        formDataToSend.append('document_type', 'receipt');
      }

      const response = await createExpense.mutateAsync(formDataToSend);
      
      console.log('✅ [EXPENSE] POST /api/v1/expenses/with-receipt - Response:', response);
      console.log('📝 [EXPENSE] Backend to PostgreSQL/Lakekeeper: Expense created');
      
      router.push('/expenses');
    } catch (err) {
      console.error('❌ [EXPENSE] Error creating expense:', err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Add Expense</h1>
        <p className="text-gray-600 mt-1">Record a new property expense</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Expense Details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="property_id">Property *</Label>
                <select
                  id="property_id"
                  value={formData.property_id}
                  onChange={(e) => setFormData({ ...formData, property_id: e.target.value })}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
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
                <Label htmlFor="date">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  required
                  className="text-sm"
                />
              </div>
              <div className="col-span-2">
                <Label htmlFor="description">Description *</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  required
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="amount">Amount *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  required
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="expense_type">Expense Type *</Label>
                <select
                  id="expense_type"
                  value={formData.expense_type}
                  onChange={(e) => setFormData({ ...formData, expense_type: e.target.value })}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="maintenance">Maintenance</option>
                  <option value="capex">Capital Expenditure</option>
                  <option value="pandi">Principal & Interest</option>
                  <option value="utilities">Utilities</option>
                  <option value="insurance">Insurance</option>
                  <option value="property_management">Property Management</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <Label htmlFor="vendor">Vendor</Label>
                <Input
                  id="vendor"
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div className="col-span-2">
                <Label htmlFor="file">Receipt/Invoice (Image or PDF)</Label>
                <Input
                  id="file"
                  type="file"
                  accept="image/*,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="text-sm"
                />
              </div>
              <div className="col-span-2 flex items-center">
                <input
                  type="checkbox"
                  id="is_planned"
                  checked={formData.is_planned}
                  onChange={(e) => setFormData({ ...formData, is_planned: e.target.checked })}
                  className="mr-2"
                />
                <Label htmlFor="is_planned" className="text-sm">
                  Planned Expense
                </Label>
              </div>
              <div className="col-span-2">
                <Label htmlFor="notes">Notes</Label>
                <textarea
                  id="notes"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                type="submit"
                className="bg-black text-white hover:bg-gray-800"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Expense'}
              </Button>
              <Button
                type="button"
                variant="outline"
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

