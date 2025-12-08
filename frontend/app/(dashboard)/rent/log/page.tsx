'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Home, Save, Calendar, DollarSign, ArrowLeft } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useCreateRent } from '@/lib/hooks/use-rent';

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

export default function LogRentPage() {
  const router = useRouter();
  const createRent = useCreateRent();
  
  const [properties, setProperties] = useState<Property[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Default to current month
  const currentDate = new Date();
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    amount: '',
    rent_period_month: currentDate.getMonth() + 1, // 1-12
    rent_period_year: currentDate.getFullYear(),
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
      const payload = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        amount: parseFloat(formData.amount),
        rent_period_month: formData.rent_period_month,
        rent_period_year: formData.rent_period_year,
        payment_date: formData.payment_date,
        payment_method: (formData.payment_method || undefined) as 'check' | 'cash' | 'electronic' | 'money_order' | 'other' | undefined,
        transaction_reference: formData.transaction_reference || undefined,
        is_late: formData.is_late,
        late_fee: formData.late_fee ? parseFloat(formData.late_fee) : undefined,
        notes: formData.notes || undefined,
      };

      await createRent.mutateAsync(payload);
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
        <div className="text-xs text-gray-500 mb-1">Recording:</div>
        <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-blue-600" />
          Log Rent Payment
        </h1>
        <p className="text-sm text-gray-600 mt-1">Record a rent payment received from a tenant</p>
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

            {/* Rent Period (Month/Year) */}
            <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
              <Label className="text-xs font-medium text-gray-700 block mb-2">
                Rent For Period <span className="text-red-500">*</span>
              </Label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="rent_period_month" className="text-[10px] text-gray-500">Month</Label>
                  <Select
                    value={String(formData.rent_period_month)}
                    onValueChange={(value) => setFormData({ ...formData, rent_period_month: parseInt(value) })}
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
                    onValueChange={(value) => setFormData({ ...formData, rent_period_year: parseInt(value) })}
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
              <p className="text-[10px] text-gray-500 mt-2">
                Recording rent for: <span className="font-medium">{getMonthLabel(formData.rent_period_month)} {formData.rent_period_year}</span>
              </p>
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
