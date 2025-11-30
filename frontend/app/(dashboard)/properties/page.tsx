'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
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
import { Plus, Building2, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';
import { apiClient } from '@/lib/api-client';

export default function PropertiesPage() {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useProperties();
  const [deleting, setDeleting] = useState<string | null>(null);

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

  const handleDelete = async (propertyId: string, propertyName: string) => {
    if (!confirm(`Are you sure you want to delete "${propertyName}"? This action cannot be undone.`)) {
      return;
    }

    setDeleting(propertyId);
    try {
      await apiClient.delete(`/properties/${propertyId}`);
      console.log('✅ [PROPERTY] Deleted:', propertyId);
      // Refetch the properties list
      refetch();
    } catch (err) {
      console.error('❌ [PROPERTY] Error deleting:', err);
      alert(`Failed to delete property: ${(err as Error).message}`);
    } finally {
      setDeleting(null);
    }
  };

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
                  <TableHead>Down Payment</TableHead>
                  <TableHead>Market Value</TableHead>
                  <TableHead>Vacancy Rate</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((property) => (
                  <TableRow 
                    key={property.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => router.push(`/properties/${property.id}`)}
                  >
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
                      ${Math.round(property.purchase_price / 1000).toLocaleString()}k
                    </TableCell>
                    <TableCell>
                      {property.down_payment 
                        ? `$${Math.round(property.down_payment / 1000).toLocaleString()}k`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {property.current_market_value 
                        ? `$${Math.round(property.current_market_value / 1000).toLocaleString()}k`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {property.vacancy_rate !== undefined && property.vacancy_rate !== null
                        ? `${(property.vacancy_rate * 100).toFixed(1)}%`
                        : '7.0%'}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {property.property_type || '-'}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:bg-red-50"
                          onClick={() => handleDelete(property.id, property.display_name || 'this property')}
                          disabled={deleting === property.id}
                        >
                          {deleting === property.id ? (
                            'Deleting...'
                          ) : (
                            <>
                              <Trash2 className="h-4 w-4" />
                            </>
                          )}
                        </Button>
                      </div>
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

