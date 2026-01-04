'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiClient } from '@/lib/api-client';

export default function AddPropertyPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    display_name: '',
    purchase_price: '',
    purchase_date: '2024-10-23',
    down_payment: '',
    cash_invested: '',
    current_market_value: '',
    property_status: 'evaluating',
    vacancy_rate: '0.07',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    zip_code: '',
    property_type: '',
    year_built: '',
    bedrooms: '',
    bathrooms: '',
    square_feet: '',
    current_monthly_rent: '',
    notes: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Determine if property is multi-unit
      const isMultiUnit = formData.property_type === 'multi_family' || formData.property_type === 'duplex';

      // Build the request payload
      const payload: any = {
        display_name: formData.display_name || undefined,
        purchase_price: parseFloat(formData.purchase_price) || 0,
        purchase_date: formData.purchase_date || '2024-10-23',
        down_payment: formData.down_payment ? parseFloat(formData.down_payment) : undefined,
        cash_invested: formData.cash_invested ? parseFloat(formData.cash_invested) : undefined,
        current_market_value: formData.current_market_value ? parseFloat(formData.current_market_value) : undefined,
        property_status: formData.property_status,
        vacancy_rate: formData.vacancy_rate ? parseFloat(formData.vacancy_rate) : 0.07,
        monthly_rent_to_income_ratio: 2.75,
        address_line1: formData.address_line1 || undefined,
        address_line2: formData.address_line2 || undefined,
        city: formData.city || undefined,
        state: formData.state || undefined,
        zip_code: formData.zip_code || undefined,
        property_type: formData.property_type || undefined,
        year_built: formData.year_built ? parseInt(formData.year_built) : undefined,
        notes: formData.notes || undefined,
        has_units: isMultiUnit,
        unit_count: isMultiUnit ? 0 : null,
      };

      // For single-unit properties, add unit details to property
      if (!isMultiUnit) {
        payload.current_monthly_rent = formData.current_monthly_rent ? parseFloat(formData.current_monthly_rent) : undefined;
        payload.bedrooms = formData.bedrooms ? parseInt(formData.bedrooms) : undefined;
        payload.bathrooms = formData.bathrooms ? parseFloat(formData.bathrooms) : undefined;
        payload.square_feet = formData.square_feet ? parseInt(formData.square_feet) : undefined;
      }

      // Remove undefined values
      Object.keys(payload).forEach(key => {
        if (payload[key] === undefined || payload[key] === '') {
          delete payload[key];
        }
      });

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
      console.log('📋 [PROPERTY] Field order compliance check:');
      console.log('   Expected order:', orderedKeys);
      console.log('   Actual payload keys:', payloadKeys);
      console.log('   ✅ Order matches:', JSON.stringify(orderedKeys) === JSON.stringify(payloadKeys.slice(0, orderedKeys.length)));
      console.log('📝 [PROPERTY] Creating property with ordered payload:', orderedPayload);
      
      const property = await apiClient.post<{ id: string }>('/properties', orderedPayload);
      console.log('✅ [PROPERTY] Property created:', property);

      // Redirect to property detail page (where units can be added)
      router.push(`/properties/${property.id}`);
    } catch (err) {
      console.error('❌ [PROPERTY] Error:', err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const isMultiUnit = formData.property_type === 'multi_family' || formData.property_type === 'duplex';

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Add Property</h1>
        <p className="text-gray-600 mt-1">Create a new rental property</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Property Details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                  id="display_name"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="purchase_price">Purchase Price *</Label>
                <Input
                  id="purchase_price"
                  type="number"
                  step="0.01"
                  value={formData.purchase_price}
                  onChange={(e) => setFormData({ ...formData, purchase_price: e.target.value })}
                  required
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="purchase_date">Purchase Date</Label>
                <Input
                  id="purchase_date"
                  type="date"
                  value={formData.purchase_date}
                  onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                  className="text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">Used for depreciation calculations</p>
              </div>
              <div>
                <Label htmlFor="down_payment">Down Payment</Label>
                <Input
                  id="down_payment"
                  type="number"
                  step="0.01"
                  value={formData.down_payment}
                  onChange={(e) => setFormData({ ...formData, down_payment: e.target.value })}
                  className="text-sm"
                  placeholder="Initial equity investment"
                />
              </div>
              <div>
                <Label htmlFor="cash_invested">Cash Invested</Label>
                <Input
                  id="cash_invested"
                  type="number"
                  step="0.01"
                  value={formData.cash_invested}
                  onChange={(e) => setFormData({ ...formData, cash_invested: e.target.value })}
                  className="text-sm"
                  placeholder="Total cash invested"
                />
              </div>
              <div>
                <Label htmlFor="current_market_value">Current Market Value</Label>
                <Input
                  id="current_market_value"
                  type="number"
                  step="0.01"
                  value={formData.current_market_value}
                  onChange={(e) => setFormData({ ...formData, current_market_value: e.target.value })}
                  className="text-sm"
                  placeholder="Estimated current value"
                />
              </div>
              <div>
                <Label htmlFor="property_status">Property Status *</Label>
                <Select
                  value={formData.property_status}
                  onValueChange={(value) => setFormData({ ...formData, property_status: value })}
                  required
                >
                  <SelectTrigger className="text-sm">
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="evaluating">Evaluating</SelectItem>
                    <SelectItem value="own">Own</SelectItem>
                    <SelectItem value="rehabbing">Rehabbing</SelectItem>
                    <SelectItem value="listed_for_rent">Listed for Rent</SelectItem>
                    <SelectItem value="listed_for_sale">Listed for Sale</SelectItem>
                    <SelectItem value="sold">Sold</SelectItem>
                    <SelectItem value="hide">Hide</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="vacancy_rate">Vacancy Rate (decimal, e.g., 0.07 = 7%)</Label>
                <Input
                  id="vacancy_rate"
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={formData.vacancy_rate}
                  onChange={(e) => setFormData({ ...formData, vacancy_rate: e.target.value })}
                  className="text-sm"
                  placeholder="0.07"
                />
              </div>
              <div>
                <Label htmlFor="address_line1">Address</Label>
                <Input
                  id="address_line1"
                  value={formData.address_line1}
                  onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="address_line2">Address Line 2</Label>
                <Input
                  id="address_line2"
                  value={formData.address_line2}
                  onChange={(e) => setFormData({ ...formData, address_line2: e.target.value })}
                  className="text-sm"
                  placeholder="Apt, Suite, Unit, etc."
                />
              </div>
              <div>
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="state">State</Label>
                <Input
                  id="state"
                  value={formData.state}
                  onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="zip_code">Zip Code</Label>
                <Input
                  id="zip_code"
                  value={formData.zip_code}
                  onChange={(e) => setFormData({ ...formData, zip_code: e.target.value })}
                  className="text-sm"
                />
              </div>
              <div>
                <Label htmlFor="year_built">Year Built</Label>
                <Input
                  id="year_built"
                  type="number"
                  min="1800"
                  max="2100"
                  value={formData.year_built}
                  onChange={(e) => setFormData({ ...formData, year_built: e.target.value })}
                  className="text-sm"
                  placeholder="e.g., 1985"
                />
              </div>
              <div className="col-span-2">
                <Label htmlFor="property_type">Property Type *</Label>
                <Select
                  value={formData.property_type}
                  onValueChange={(value) => setFormData({ ...formData, property_type: value })}
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
                {isMultiUnit && (
                  <p className="text-xs text-blue-600 mt-1">
                    You'll be able to add units after creating the property
                  </p>
                )}
              </div>
            </div>

            {/* Single-unit property fields */}
            {!isMultiUnit && formData.property_type && (
              <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                <div>
                  <Label htmlFor="bedrooms">Bedrooms</Label>
                  <Input
                    id="bedrooms"
                    type="number"
                    min="0"
                    value={formData.bedrooms}
                    onChange={(e) => setFormData({ ...formData, bedrooms: e.target.value })}
                    className="text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="bathrooms">Bathrooms</Label>
                  <Input
                    id="bathrooms"
                    type="number"
                    min="0"
                    step="0.5"
                    value={formData.bathrooms}
                    onChange={(e) => setFormData({ ...formData, bathrooms: e.target.value })}
                    className="text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="square_feet">Square Feet</Label>
                  <Input
                    id="square_feet"
                    type="number"
                    min="0"
                    value={formData.square_feet}
                    onChange={(e) => setFormData({ ...formData, square_feet: e.target.value })}
                    className="text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="current_monthly_rent">Monthly Rent</Label>
                  <Input
                    id="current_monthly_rent"
                    type="number"
                    step="0.01"
                    value={formData.current_monthly_rent}
                    onChange={(e) => setFormData({ ...formData, current_monthly_rent: e.target.value })}
                    className="text-sm"
                  />
                </div>
              </div>
            )}

            {/* Notes field - always shown */}
            <div className="pt-4 border-t">
              <Label htmlFor="notes">Notes</Label>
              <textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mt-1"
                placeholder="Additional details about the property..."
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                type="submit"
                className="bg-black text-white hover:bg-gray-800"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Property'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                disabled={loading}
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
