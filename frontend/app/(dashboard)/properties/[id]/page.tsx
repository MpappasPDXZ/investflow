'use client';

import { use } from 'react';
import { useProperty } from '@/lib/hooks/use-properties';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Building2 } from 'lucide-react';

export default function PropertyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: property, isLoading } = useProperty(id);

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
      <div className="mb-6">
        <div className="text-sm text-gray-600 mb-2">Viewing:</div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Building2 className="h-8 w-8" />
          {property.display_name || 'Unnamed Property'}
        </h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Property Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="text-sm text-gray-600">Address</div>
              <div className="font-medium">
                {property.address_line1 || 'N/A'}
                {property.city && `, ${property.city}, ${property.state}`}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Purchase Price</div>
              <div className="font-medium">
                ${property.purchase_price?.toLocaleString() || 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Monthly Rent</div>
              <div className="font-medium">
                ${property.current_monthly_rent?.toLocaleString() || 'N/A'}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Property Type</div>
              <div className="font-medium">{property.property_type || 'N/A'}</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {property.bedrooms && (
              <div>
                <div className="text-sm text-gray-600">Bedrooms</div>
                <div className="font-medium">{property.bedrooms}</div>
              </div>
            )}
            {property.bathrooms && (
              <div>
                <div className="text-sm text-gray-600">Bathrooms</div>
                <div className="font-medium">{property.bathrooms}</div>
              </div>
            )}
            {property.square_feet && (
              <div>
                <div className="text-sm text-gray-600">Square Feet</div>
                <div className="font-medium">{property.square_feet.toLocaleString()}</div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

