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
import { Plus, Building2, Trash2, Home, Eye, Hammer, ListChecks, Tag, Archive, ShoppingCart, Key } from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';
import { apiClient } from '@/lib/api-client';

export default function PropertiesPage() {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useProperties();
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    // Removed logging to prevent Fast Refresh noise
  }, [data, error]);

  const handleDelete = async (propertyId: string, propertyName: string) => {
    // First confirmation
    if (!confirm(`Are you sure you want to delete "${propertyName}"? This action cannot be undone.`)) {
      return;
    }

    // Second confirmation
    if (!confirm(`⚠️ FINAL WARNING: This will permanently delete "${propertyName}" and all associated data. This cannot be undone. Are you absolutely sure?`)) {
      return;
    }

    setDeleting(propertyId);
    try {
      console.log(`🗑️ [PROPERTY] Deleting property: ${propertyId} (${propertyName})`);
      await apiClient.delete(`/properties/${propertyId}`);
      console.log(`✅ [PROPERTY] Successfully deleted property: ${propertyId}`);
      // Refetch the properties list
      refetch();
    } catch (err) {
      const errorMessage = (err as Error).message;
      console.error(`❌ [PROPERTY] Error deleting property ${propertyId}:`, err);
      alert(`Failed to delete property: ${errorMessage}`);
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
                      <TableHead className="text-xs">Status</TableHead>
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
                          <div className="flex items-center gap-2">
                            {property.property_status === 'own' && <Home className="h-4 w-4 text-green-600" />}
                            {property.property_status === 'evaluating' && <Eye className="h-4 w-4 text-blue-600" />}
                            {property.property_status === 'rehabbing' && <Hammer className="h-4 w-4 text-orange-600" />}
                            {property.property_status === 'listed_for_rent' && <ListChecks className="h-4 w-4 text-purple-600" />}
                            {property.property_status === 'listed_for_sale' && <Tag className="h-4 w-4 text-yellow-600" />}
                            {property.property_status === 'sold' && <ShoppingCart className="h-4 w-4 text-gray-600" />}
                            {property.property_status === 'rented' && <Key className="h-4 w-4 text-emerald-600" />}
                            {property.property_status === 'hide' && <Archive className="h-4 w-4 text-gray-400" />}
                            <span className="capitalize">
                              {property.property_status?.replace(/_/g, ' ') || 'N/A'}
                            </span>
                          </div>
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
                        <span className="text-gray-500">Status:</span>{' '}
                        <span className="font-medium flex items-center gap-1">
                          {property.property_status === 'own' && <Home className="h-3.5 w-3.5 text-green-600" />}
                          {property.property_status === 'evaluating' && <Eye className="h-3.5 w-3.5 text-blue-600" />}
                          {property.property_status === 'rehabbing' && <Hammer className="h-3.5 w-3.5 text-orange-600" />}
                          {property.property_status === 'listed_for_rent' && <ListChecks className="h-3.5 w-3.5 text-purple-600" />}
                          {property.property_status === 'listed_for_sale' && <Tag className="h-3.5 w-3.5 text-yellow-600" />}
                          {property.property_status === 'sold' && <ShoppingCart className="h-3.5 w-3.5 text-gray-600" />}
                          {property.property_status === 'rented' && <Key className="h-3.5 w-3.5 text-emerald-600" />}
                          {property.property_status === 'hide' && <Archive className="h-3.5 w-3.5 text-gray-400" />}
                          <span className="capitalize">
                            {property.property_status?.replace(/_/g, ' ') || 'N/A'}
                          </span>
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

