'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateProperty } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api-client';

export default function AddPropertyPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    display_name: '',
    purchase_price: '',
    address_line1: '',
    city: '',
    state: '',
    zip_code: '',
    property_type: '',
    bedrooms: '',
    bathrooms: '',
    square_feet: '',
    current_monthly_rent: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    console.log('📝 [PROPERTY] Creating property:', formData);
    console.log('📤 [PROPERTY] POST /api/v1/properties - Request:', formData);

    try {
      const response = await apiClient.post('/properties', {
        ...formData,
        purchase_price: parseFloat(formData.purchase_price) || 0,
        monthly_rent_to_income_ratio: 2.75,
        bedrooms: formData.bedrooms ? parseInt(formData.bedrooms) : null,
        bathrooms: formData.bathrooms ? parseFloat(formData.bathrooms) : null,
        square_feet: formData.square_feet ? parseInt(formData.square_feet) : null,
        current_monthly_rent: formData.current_monthly_rent ? parseFloat(formData.current_monthly_rent) : null,
      });

      console.log('✅ [PROPERTY] POST /api/v1/properties - Response:', response);
      console.log('📝 [PROPERTY] Backend to PostgreSQL/Lakekeeper: Property created');
      
      router.push('/properties');
    } catch (err) {
      console.error('❌ [PROPERTY] Error creating property:', err);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

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
                <Label htmlFor="address_line1">Address</Label>
                <Input
                  id="address_line1"
                  value={formData.address_line1}
                  onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
                  className="text-sm"
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
                <Label htmlFor="property_type">Property Type</Label>
                <Input
                  id="property_type"
                  value={formData.property_type}
                  onChange={(e) => setFormData({ ...formData, property_type: e.target.value })}
                  placeholder="single_family, condo, etc."
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
                {loading ? 'Creating...' : 'Create Property'}
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

