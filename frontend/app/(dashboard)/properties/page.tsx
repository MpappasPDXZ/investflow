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
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Properties
          </h1>
          <p className="text-sm text-gray-600 mt-1">Manage your rental properties</p>
        </div>
        <Link href="/properties/add">
          <Button className="bg-black text-white hover:bg-gray-800 h-8 text-xs">
            <Plus className="h-3 w-3 mr-1.5" />
            Add Property
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-bold">All Properties</CardTitle>
        </CardHeader>
        <CardContent>
          {data?.items.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              No properties found. <Link href="/properties/add" className="text-blue-600 hover:underline">Add your first property</Link>
            </div>
          ) : (
            <>
              {/* Desktop Table View */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Name</TableHead>
                      <TableHead className="text-xs">Address</TableHead>
                      <TableHead className="text-xs">Purchase Price</TableHead>
                      <TableHead className="text-xs">Cash Invested</TableHead>
                      <TableHead className="text-xs">Market Value</TableHead>
                      <TableHead className="text-xs">Vacancy Rate</TableHead>
                      <TableHead className="text-xs">Type</TableHead>
                      <TableHead className="text-xs">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data?.items.map((property) => (
                      <TableRow 
                        key={property.id}
                        className="cursor-pointer hover:bg-gray-50"
                        onClick={() => router.push(`/properties/${property.id}`)}
                      >
                        <TableCell className="font-medium text-xs">
                          {property.display_name || 'Unnamed Property'}
                        </TableCell>
                        <TableCell>
                          {property.address_line1 && (
                            <div className="text-xs">
                              {property.address_line1}
                              {property.city && `, ${property.city}, ${property.state}`}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">
                          ${Math.round(property.purchase_price / 1000).toLocaleString()}k
                        </TableCell>
                        <TableCell className="text-xs">
                          {property.cash_invested 
                            ? `$${Math.round(property.cash_invested / 1000).toLocaleString()}k`
                            : '-'}
                        </TableCell>
                        <TableCell className="text-xs">
                          {property.current_market_value 
                            ? `$${Math.round(property.current_market_value / 1000).toLocaleString()}k`
                            : '-'}
                        </TableCell>
                        <TableCell className="text-xs">
                          {property.vacancy_rate !== undefined && property.vacancy_rate !== null
                            ? `${(property.vacancy_rate * 100).toFixed(1)}%`
                            : '7.0%'}
                        </TableCell>
                        <TableCell className="text-xs text-gray-600">
                          {property.property_type || '-'}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-red-600 hover:bg-red-50"
                              onClick={() => handleDelete(property.id, property.display_name || 'this property')}
                              disabled={deleting === property.id}
                            >
                              {deleting === property.id ? (
                                '...'
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              
              {/* Mobile Card View */}
              <div className="md:hidden space-y-3">
                {data?.items.map((property) => (
                  <div
                    key={property.id}
                    className="border rounded-lg p-4 bg-white active:bg-gray-50 cursor-pointer"
                    onClick={() => router.push(`/properties/${property.id}`)}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-semibold text-gray-900">
                          {property.display_name || 'Unnamed Property'}
                        </h3>
                        {property.address_line1 && (
                          <p className="text-sm text-gray-600 mt-0.5">
                            {property.address_line1}
                            {property.city && `, ${property.city}, ${property.state}`}
                          </p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:bg-red-50 h-10 w-10 p-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(property.id, property.display_name || 'this property');
                        }}
                        disabled={deleting === property.id}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
                      <div>
                        <span className="text-gray-500">Purchase:</span>{' '}
                        <span className="font-medium">${Math.round(property.purchase_price / 1000).toLocaleString()}k</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Market:</span>{' '}
                        <span className="font-medium">
                          {property.current_market_value 
                            ? `$${Math.round(property.current_market_value / 1000).toLocaleString()}k`
                            : '-'}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500">Cash Invested:</span>{' '}
                        <span className="font-medium">
                          {property.cash_invested 
                            ? `$${Math.round(property.cash_invested / 1000).toLocaleString()}k`
                            : '-'}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500">Vacancy:</span>{' '}
                        <span className="font-medium">
                          {property.vacancy_rate !== undefined && property.vacancy_rate !== null
                            ? `${(property.vacancy_rate * 100).toFixed(1)}%`
                            : '7.0%'}
                        </span>
                      </div>
                    </div>
                    
                    {property.property_type && (
                      <div className="mt-2 text-xs text-gray-500">
                        Type: {property.property_type}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

