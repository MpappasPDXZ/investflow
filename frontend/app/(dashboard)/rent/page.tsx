'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { 
  Plus, 
  DollarSign, 
  Calendar, 
  Trash2, 
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Filter
} from 'lucide-react';
import { format } from 'date-fns';
import { useRents, useDeleteRent } from '@/lib/hooks/use-rent';
import { useProperties } from '@/lib/hooks/use-properties';
import type { RentPayment } from '@/lib/types';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  check: 'Check',
  cash: 'Cash',
  electronic: 'Electronic',
  money_order: 'Money Order',
  other: 'Other',
};

interface GroupedRents {
  [year: number]: RentPayment[];
}

export default function RentPage() {
  const router = useRouter();
  const [selectedYear, setSelectedYear] = useState<string>('all');
  const [selectedProperty, setSelectedProperty] = useState<string>('all');
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set([new Date().getFullYear()]));
  const [deletingId, setDeletingId] = useState<string | null>(null);
  
  const { data: propertiesData } = useProperties();
  const deleteRent = useDeleteRent();
  
  // Build filters
  const filters: Record<string, string | number> = {};
  if (selectedProperty !== 'all') filters.property_id = selectedProperty;
  if (selectedYear !== 'all') filters.year = parseInt(selectedYear);
  
  const { data: rentsData, isLoading, error } = useRents(filters);
  
  const properties = propertiesData?.items || [];
  const rents = rentsData?.items || [];

  // Group rents by year
  const groupedRents = useMemo(() => {
    const groups: GroupedRents = {};
    rents.forEach(rent => {
      const year = rent.rent_period_year;
      if (!groups[year]) groups[year] = [];
      groups[year].push(rent);
    });
    // Sort each year's rents by month descending
    Object.keys(groups).forEach(year => {
      groups[parseInt(year)].sort((a, b) => b.rent_period_month - a.rent_period_month);
    });
    return groups;
  }, [rents]);

  // Get sorted years (descending)
  const years = Object.keys(groupedRents).map(Number).sort((a, b) => b - a);

  // Calculate totals
  const grandTotal = rents.reduce((sum: number, r: RentPayment) => sum + Number(r.amount), 0);
  const yearTotals = useMemo(() => {
    const totals: Record<number, number> = {};
    Object.entries(groupedRents).forEach(([year, yearRents]) => {
      totals[parseInt(year)] = yearRents.reduce((sum: number, r: RentPayment) => sum + Number(r.amount), 0);
    });
    return totals;
  }, [groupedRents]);

  // Generate year options for filter
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const allYears = new Set([...years, currentYear]);
    return Array.from(allYears).sort((a, b) => b - a);
  }, [years]);

  const toggleYear = (year: number) => {
    const newExpanded = new Set(expandedYears);
    if (newExpanded.has(year)) {
      newExpanded.delete(year);
    } else {
      newExpanded.add(year);
    }
    setExpandedYears(newExpanded);
  };

  const handleDelete = async (rentId: string) => {
    if (!confirm('Are you sure you want to delete this rent payment?')) return;
    
    try {
      setDeletingId(rentId);
      await deleteRent.mutateAsync(rentId);
    } catch (err) {
      console.error('Error deleting rent:', err);
      alert('Failed to delete rent payment');
    } finally {
      setDeletingId(null);
    }
  };

  const getPropertyName = (propertyId: string) => {
    const property = properties.find(p => p.id === propertyId);
    return property?.display_name || property?.address_line1 || 'Unknown Property';
  };

  return (
    <div className="p-8">
      {/* Header - Compact */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <DollarSign className="h-5 w-5 text-blue-600" />
            Rent Collection
          </h1>
          <p className="text-sm text-gray-600 mt-1">Track and manage rent payments received</p>
        </div>
        <Button
          onClick={() => router.push('/rent/log')}
          className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
        >
          <Plus className="h-3 w-3 mr-1.5" />
          Log Rent Payment
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <DollarSign className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500 font-medium">Total Collected</p>
                <p className="text-lg font-bold text-blue-700">
                  ${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Calendar className="h-4 w-4 text-gray-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500 font-medium">Payments Logged</p>
                <p className="text-lg font-bold text-gray-900">{rents.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <AlertCircle className="h-4 w-4 text-orange-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500 font-medium">Late Payments</p>
                <p className="text-lg font-bold text-gray-900">
                  {rents.filter(r => r.is_late).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters - Compact */}
      <div className="flex items-center gap-2 mb-4">
        <Filter className="h-3.5 w-3.5 text-gray-400" />
        <Select value={selectedProperty} onValueChange={setSelectedProperty}>
          <SelectTrigger className="w-[200px] h-8 text-xs">
            <SelectValue placeholder="All Properties" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Properties</SelectItem>
            {properties.map((property) => (
              <SelectItem key={property.id} value={property.id}>
                {property.display_name || property.address_line1 || 'Unnamed'}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={selectedYear} onValueChange={setSelectedYear}>
          <SelectTrigger className="w-[120px] h-8 text-xs">
            <SelectValue placeholder="All Years" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Years</SelectItem>
            {yearOptions.map((year) => (
              <SelectItem key={year} value={String(year)}>
                {year}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Rent Payments Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-bold">Rent Payment History</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500 text-sm">Loading...</div>
          ) : error ? (
            <div className="text-center py-12">
              <DollarSign className="h-12 w-12 text-red-300 mx-auto mb-3" />
              <p className="text-red-600 font-medium mb-2 text-sm">Error loading rent payments</p>
              <p className="text-gray-500 text-xs mb-4">
                {error instanceof Error ? error.message : 'Unknown error occurred'}
              </p>
              <p className="text-gray-500 text-xs mb-4">
                This might be because you haven't logged any rent payments yet. Try logging your first payment to create the rent table.
              </p>
              <Button
                onClick={() => router.push('/rent/log')}
                variant="outline"
                className="text-xs h-8"
              >
                <Plus className="h-3 w-3 mr-1.5" />
                Log Your First Payment
              </Button>
            </div>
          ) : rents.length === 0 ? (
            <div className="text-center py-12">
              <DollarSign className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 mb-4 text-sm">No rent payments logged yet</p>
              <Button
                onClick={() => router.push('/rent/log')}
                variant="outline"
                className="text-xs h-8"
              >
                <Plus className="h-3 w-3 mr-1.5" />
                Log Your First Payment
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {years.map((year) => (
                <div key={year} className="border rounded-lg overflow-hidden">
                  {/* Year Header - Compact */}
                  <button
                    onClick={() => toggleYear(year)}
                    className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {expandedYears.has(year) ? (
                        <ChevronDown className="h-4 w-4 text-gray-500" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-500" />
                      )}
                      <span className="font-bold text-gray-900 text-sm">{year}</span>
                      <span className="text-xs text-gray-500">
                        ({groupedRents[year].length} payment{groupedRents[year].length !== 1 ? 's' : ''})
                      </span>
                    </div>
                    <span className="font-bold text-blue-700 text-sm">
                      ${yearTotals[year]?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </button>

                  {/* Year's Payments - Desktop Table */}
                  {expandedYears.has(year) && (
                    <>
                      <div className="hidden md:block">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-gray-50/50">
                              <TableHead className="text-xs font-medium">Period</TableHead>
                              <TableHead className="text-xs font-medium">Property</TableHead>
                              <TableHead className="text-xs font-medium text-right">Amount</TableHead>
                              <TableHead className="text-xs font-medium">Payment Date</TableHead>
                              <TableHead className="text-xs font-medium">Method</TableHead>
                              <TableHead className="text-xs font-medium">Status</TableHead>
                              <TableHead className="text-xs font-medium w-[60px]">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {groupedRents[year].map((rent) => (
                              <TableRow key={rent.id} className="hover:bg-gray-50">
                                <TableCell className="text-xs font-medium">
                                  {MONTHS[rent.rent_period_month - 1]} {rent.rent_period_year}
                                </TableCell>
                                <TableCell className="text-xs text-gray-600">
                                  {getPropertyName(rent.property_id)}
                                </TableCell>
                                <TableCell className="text-xs font-medium text-right text-blue-700">
                                  ${Number(rent.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                  {rent.late_fee && Number(rent.late_fee) > 0 && (
                                    <span className="text-orange-600 text-[10px] ml-1">
                                      (+${Number(rent.late_fee).toLocaleString()} fee)
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell className="text-xs text-gray-600">
                                  {format(new Date(rent.payment_date), 'MMM d, yyyy')}
                                </TableCell>
                                <TableCell className="text-xs text-gray-600">
                                  {rent.payment_method ? PAYMENT_METHOD_LABELS[rent.payment_method] : '-'}
                                </TableCell>
                                <TableCell>
                                  {rent.is_late ? (
                                    <span className="inline-flex items-center gap-1 text-[10px] text-orange-600 bg-orange-50 px-2 py-0.5 rounded">
                                      <AlertCircle className="h-3 w-3" />
                                      Late
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-[10px] text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                                      <CheckCircle2 className="h-3 w-3" />
                                      On Time
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDelete(rent.id)}
                                    disabled={deletingId === rent.id}
                                    className="h-7 w-7 p-0 text-gray-400 hover:text-red-600"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                            {/* Year Subtotal */}
                            <TableRow className="bg-gray-50 font-medium">
                              <TableCell colSpan={2} className="text-xs text-gray-600">
                                Subtotal for {year}
                              </TableCell>
                              <TableCell className="text-xs text-right text-blue-700 font-bold">
                                ${yearTotals[year]?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </TableCell>
                              <TableCell colSpan={4}></TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                      </div>
                      
                      {/* Year's Payments - Mobile Cards */}
                      <div className="md:hidden divide-y">
                        {groupedRents[year].map((rent) => (
                          <div key={rent.id} className="p-4 bg-white">
                            <div className="flex justify-between items-start mb-2">
                              <div>
                                <p className="font-medium text-gray-900">
                                  {MONTHS[rent.rent_period_month - 1]} {rent.rent_period_year}
                                </p>
                                <p className="text-sm text-gray-600">{getPropertyName(rent.property_id)}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-bold text-green-700">
                                  ${Number(rent.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </p>
                                {rent.late_fee && Number(rent.late_fee) > 0 && (
                                  <p className="text-orange-600 text-xs">
                                    +${Number(rent.late_fee).toLocaleString()} fee
                                  </p>
                                )}
                              </div>
                            </div>
                            <div className="flex justify-between items-center text-sm">
                              <div className="flex items-center gap-3 text-gray-600">
                                <span>{format(new Date(rent.payment_date), 'MMM d, yyyy')}</span>
                                <span>{rent.payment_method ? PAYMENT_METHOD_LABELS[rent.payment_method] : '-'}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                {rent.is_late ? (
                                  <span className="inline-flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
                                    <AlertCircle className="h-3 w-3" />
                                    Late
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                                    <CheckCircle2 className="h-3 w-3" />
                                    On Time
                                  </span>
                                )}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDelete(rent.id)}
                                  disabled={deletingId === rent.id}
                                  className="h-10 w-10 p-0 text-gray-400 hover:text-red-600"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                        {/* Year Subtotal - Mobile */}
                        <div className="p-4 bg-gray-50 flex justify-between items-center">
                          <span className="text-sm text-gray-600">Subtotal for {year}</span>
                          <span className="font-bold text-green-700">
                            ${yearTotals[year]?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}

              {/* Grand Total */}
              {years.length > 0 && (
                <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <span className="font-bold text-gray-900 text-sm">Grand Total</span>
                  <span className="text-lg font-bold text-blue-700">
                    ${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
