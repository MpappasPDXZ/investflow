'use client';

import { useEffect } from 'react';
import { useProperties } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Building2 } from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';

export default function PropertiesPage() {
  const { data, isLoading, error } = useProperties();

  useEffect(() => {
    console.log('📊 [PROPERTIES] Page loaded');
    if (data) {
      console.log('✅ [PROPERTIES] GET /api/v1/properties - Response:', data);
      console.log('📝 [PROPERTIES] Backend to PostgreSQL/Lakekeeper: Properties fetched');
    }
    if (error) {
      console.error('❌ [PROPERTIES] Error:', error);
    }
  }, [data, error]);

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-gray-500">Loading properties...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Properties</h1>
          <p className="text-gray-600 mt-1">Manage your rental properties</p>
        </div>
        <Link href="/properties/add">
          <Button className="bg-black text-white hover:bg-gray-800">
            <Plus className="h-4 w-4 mr-2" />
            Add Property
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Properties</CardTitle>
        </CardHeader>
        <CardContent>
          {data?.items.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No properties found. <Link href="/properties/add" className="text-blue-600 hover:underline">Add your first property</Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Address</TableHead>
                  <TableHead>Purchase Price</TableHead>
                  <TableHead>Monthly Rent</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((property) => (
                  <TableRow key={property.id}>
                    <TableCell className="font-medium">
                      {property.display_name || 'Unnamed Property'}
                    </TableCell>
                    <TableCell>
                      {property.address_line1 && (
                        <div className="text-sm">
                          {property.address_line1}
                          {property.city && `, ${property.city}, ${property.state}`}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      ${property.purchase_price?.toLocaleString() || 'N/A'}
                    </TableCell>
                    <TableCell>
                      ${property.current_monthly_rent?.toLocaleString() || 'N/A'}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {property.property_type || '-'}
                    </TableCell>
                    <TableCell>
                      <Link href={`/properties/${property.id}`}>
                        <Button variant="ghost" size="sm" className="text-black hover:bg-gray-100">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

