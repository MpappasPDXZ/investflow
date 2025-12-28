'use client';

import { useState, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Plus, 
  DollarSign, 
  Trash2, 
  Edit,
  ChevronDown,
  ChevronRight,
  Building2,
  FileText,
  Eye
} from 'lucide-react';
import { format } from 'date-fns';
import { useRents, useDeleteRent } from '@/lib/hooks/use-rent';
import { useProperties } from '@/lib/hooks/use-properties';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import type { RentPayment } from '@/lib/types';
import Link from 'next/link';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

interface GroupedByProperty {
  [propertyId: string]: RentPayment[];
}

export default function RentPage() {
  const router = useRouter();
  const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set()); // "propertyId-year"
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [hasInitializedExpansion, setHasInitializedExpansion] = useState(false);
  
  const { data: propertiesData } = useProperties();
  const { data: rentsData, isLoading } = useRents(); // No filters - just user_id auth
  const deleteRent = useDeleteRent();
  
  const properties = propertiesData?.items || [];
  const rents = rentsData?.items || [];

  // Group by property
  const groupedByProperty = useMemo(() => {
    const result: GroupedByProperty = {};
    rents.forEach(rent => {
      const propId = rent.property_id;
      if (!result[propId]) result[propId] = [];
      result[propId].push(rent);
    });
    
    // Sort rents within each property by payment_date (newest first)
    Object.values(result).forEach(propertyRents => {
      propertyRents.sort((a, b) => new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime());
    });
    
    return result;
  }, [rents]);

  // Group by property and year
  const groupedByPropertyAndYear = useMemo(() => {
    const result: Record<string, Record<number, RentPayment[]>> = {};
    
    rents.forEach(rent => {
      const propId = rent.property_id;
      // Use rent_period_year if available, otherwise use payment_date year
      const year = rent.rent_period_year || new Date(rent.payment_date).getFullYear();
      
      if (!result[propId]) result[propId] = {};
      if (!result[propId][year]) result[propId][year] = [];
      result[propId][year].push(rent);
    });
    
    // Sort rents within each year by payment_date (newest first)
    Object.values(result).forEach(years => {
      Object.values(years).forEach(yearRents => {
        yearRents.sort((a, b) => new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime());
      });
    });
    
    return result;
  }, [rents]);

  // Calculate 4 breakdowns for a list of rents
  const calculateBreakdown = (rentsList: RentPayment[]) => {
    let irsMonthly = 0;
    let irsOneTime = 0;
    let nonIrsMonthly = 0;
    let nonIrsOneTime = 0;
    
    rentsList.forEach(rent => {
      const amount = Number(rent.amount);
      const isNonIrs = rent.is_non_irs_revenue || false;
      const isOneTime = rent.is_one_time_fee || false;
      
      if (isNonIrs) {
        if (isOneTime) {
          nonIrsOneTime += amount;
        } else {
          nonIrsMonthly += amount;
        }
      } else {
        if (isOneTime) {
          irsOneTime += amount;
        } else {
          irsMonthly += amount;
        }
      }
    });
    
    return { irsMonthly, irsOneTime, nonIrsMonthly, nonIrsOneTime };
  };

  // Get property name
  const getPropertyName = (propId: string) => {
    const prop = properties.find(p => p.id === propId);
    return prop?.display_name || prop?.address_line1 || 'Unknown Property';
  };

  // Toggle functions
  const toggleProperty = (propId: string) => {
    setExpandedProperties(prev => {
      const newSet = new Set(prev);
      if (newSet.has(propId)) {
        newSet.delete(propId);
      } else {
        newSet.add(propId);
      }
      return newSet;
    });
  };

  const toggleYear = (propId: string, year: number) => {
    const key = `${propId}-${year}`;
    setExpandedYears(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
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

  // Auto-expand current year on initial load
  useEffect(() => {
    if (!hasInitializedExpansion && rents.length > 0) {
      const currentYear = new Date().getFullYear();
      const newExpandedYears = new Set<string>();
      const newExpandedProperties = new Set<string>();
      
      rents.forEach(rent => {
        const year = rent.rent_period_year || new Date(rent.payment_date).getFullYear();
        if (year === currentYear) {
          newExpandedProperties.add(rent.property_id);
          newExpandedYears.add(`${rent.property_id}-${currentYear}`);
        }
      });
      
      setExpandedProperties(newExpandedProperties);
      setExpandedYears(newExpandedYears);
      setHasInitializedExpansion(true);
    }
  }, [rents, hasInitializedExpansion]);

  // Calculate totals
  const grandTotal = rents.reduce((sum, r) => sum + Number(r.amount), 0);
  const breakdown = calculateBreakdown(rents);
  // IRS Total = IRS Monthly + IRS One-time (excludes non-IRS revenue like deposits)
  const irsTotal = breakdown.irsMonthly + breakdown.irsOneTime;

  // Sort properties by name
  const sortedPropertyIds = Object.keys(groupedByProperty).sort((a, b) => 
    getPropertyName(a).localeCompare(getPropertyName(b))
  );

  const formatAmount = (amt: number) => 
    amt > 0 ? `$${amt.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-';

  return (
    <div className="p-3 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <div>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <DollarSign className="h-3.5 w-3.5" />
            Rent Collection
          </h1>
          <p className="text-xs text-gray-500">Track rent payments received</p>
        </div>
        <Link href="/rent/log">
          <Button size="sm" className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
            <Plus className="h-3 w-3 mr-1" />
            Log Payment
          </Button>
        </Link>
      </div>

      {/* Summary Row */}
      <div className="flex gap-3 mb-3 text-xs">
        <div className="bg-blue-50 px-2 py-1 rounded">
          <span className="text-blue-600">Total:</span>{' '}
          <span className="font-bold text-blue-900">
            ${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div className="bg-green-50 px-2 py-1 rounded">
          <span className="text-green-600">IRS Total:</span>{' '}
          <span className="font-bold text-green-900">
            ${irsTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8 text-gray-500 text-sm">Loading rent payments...</div>
      )}

      {/* Empty State */}
      {!isLoading && rents.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <DollarSign className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No rent payments found</p>
            <Link href="/rent/log">
              <Button size="sm" className="mt-3">Log Payment</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Grouped by Property */}
      {sortedPropertyIds.map(propId => {
        const propertyRents = groupedByProperty[propId];
        const years = groupedByPropertyAndYear[propId] || {};
        const sortedYears = Object.keys(years).map(Number).sort((a, b) => b - a);
        const propertyTotal = propertyRents.reduce((sum, r) => sum + Number(r.amount), 0);
        const propertyBreakdown = calculateBreakdown(propertyRents);
        const isPropertyExpanded = expandedProperties.has(propId);

        return (
          <Card key={propId} className="mb-3">
            {/* Property Header with Breakdown */}
            <CardHeader 
              className="py-2 px-3 cursor-pointer hover:bg-gray-50"
              onClick={() => toggleProperty(propId)}
            >
              <div className="flex items-center gap-2">
                {isPropertyExpanded ? (
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                )}
                <Building2 className="h-4 w-4 text-gray-600" />
                <span className="font-semibold text-sm">{getPropertyName(propId)}</span>
                <span className="text-xs text-gray-500">({propertyRents.length})</span>
                <span className="ml-auto font-bold text-sm">
                  ${propertyTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
              
              {/* Breakdown Row - Desktop */}
              <div className="hidden md:flex gap-1 mt-2 flex-wrap">
                <div className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-800">
                  IRS Monthly: {formatAmount(propertyBreakdown.irsMonthly)}
                </div>
                <div className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-700">
                  IRS One-time: {formatAmount(propertyBreakdown.irsOneTime)}
                </div>
                <div className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-800">
                  Non-IRS Monthly: {formatAmount(propertyBreakdown.nonIrsMonthly)}
                </div>
                <div className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-700">
                  Non-IRS One-time: {formatAmount(propertyBreakdown.nonIrsOneTime)}
                </div>
              </div>
            </CardHeader>

            {/* Years within Property */}
            {isPropertyExpanded && (
              <CardContent className="p-0">
                {sortedYears.map(year => {
                  const yearRents = years[year];
                  const yearKey = `${propId}-${year}`;
                  const isYearExpanded = expandedYears.has(yearKey);
                  const yearTotal = yearRents.reduce((sum, r) => sum + Number(r.amount), 0);
                  const yearBreakdown = calculateBreakdown(yearRents);

                  return (
                    <div key={year} className="border-t">
                      {/* Year Header */}
                      <div 
                        className="flex items-center gap-2 px-3 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
                        onClick={() => toggleYear(propId, year)}
                      >
                        {isYearExpanded ? (
                          <ChevronDown className="h-3 w-3 text-gray-400" />
                        ) : (
                          <ChevronRight className="h-3 w-3 text-gray-400" />
                        )}
                        <span className="font-medium text-xs">{year}</span>
                        <span className="text-[10px] text-gray-500">({yearRents.length})</span>
                        <span className="ml-auto font-semibold text-xs">
                          ${yearTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                      </div>

                      {/* Year Breakdown - collapsed view */}
                      {!isYearExpanded && (
                        <div className="hidden md:flex gap-1 px-3 pb-2 flex-wrap">
                          {yearBreakdown.irsMonthly > 0 && (
                            <div className="text-[9px] px-1 py-0.5 rounded bg-green-100 text-green-800">
                              IRS Monthly: {formatAmount(yearBreakdown.irsMonthly)}
                            </div>
                          )}
                          {yearBreakdown.irsOneTime > 0 && (
                            <div className="text-[9px] px-1 py-0.5 rounded bg-green-50 text-green-700">
                              IRS One-time: {formatAmount(yearBreakdown.irsOneTime)}
                            </div>
                          )}
                          {yearBreakdown.nonIrsMonthly > 0 && (
                            <div className="text-[9px] px-1 py-0.5 rounded bg-purple-100 text-purple-800">
                              Non-IRS Monthly: {formatAmount(yearBreakdown.nonIrsMonthly)}
                            </div>
                          )}
                          {yearBreakdown.nonIrsOneTime > 0 && (
                            <div className="text-[9px] px-1 py-0.5 rounded bg-purple-50 text-purple-700">
                              Non-IRS One-time: {formatAmount(yearBreakdown.nonIrsOneTime)}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Rent List */}
                      {isYearExpanded && (
                        <div className="divide-y">
                          {yearRents.map(rent => (
                            <div 
                              key={rent.id}
                              className="px-3 py-2 flex items-center gap-2 hover:bg-gray-50"
                            >
                              {/* Date */}
                              <span className="text-[10px] text-gray-500 w-16 shrink-0">
                                {format(new Date(rent.payment_date), 'MM/dd')}
                              </span>
                              
                              {/* Period */}
                              <span className="text-[10px] text-gray-600 w-20 shrink-0">
                                {rent.rent_period_month 
                                  ? `${MONTHS[rent.rent_period_month - 1]} ${rent.rent_period_year}`
                                  : 'One-time'}
                              </span>
                              
                              {/* Tenant */}
                              <span className="text-[10px] text-gray-600 w-24 truncate shrink-0">
                                {rent.tenant_name || '-'}
                              </span>
                              
                              {/* Revenue Type Badge */}
                              <span className={`text-[9px] px-1 py-0.5 rounded shrink-0 ${
                                rent.is_non_irs_revenue 
                                  ? 'bg-purple-100 text-purple-800' 
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                {rent.revenue_description || 'Unspecified'}
                                {rent.is_one_time_fee && ' (One-time)'}
                              </span>
                              
                              {/* Description */}
                              <span className="text-xs truncate flex-1">
                                {rent.property_name || getPropertyName(rent.property_id)}
                                {rent.unit_name && ` - Unit ${rent.unit_name}`}
                              </span>
                              
                              {/* Amount */}
                              <span className={`font-semibold text-xs w-20 text-right shrink-0 ${
                                Number(rent.amount) < 0 ? 'text-red-600' : 'text-blue-700'
                              }`}>
                                {Number(rent.amount) < 0 ? '-' : ''}${Math.abs(Number(rent.amount)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </span>
                              
                              {/* Actions */}
                              <div className="flex gap-1 shrink-0">
                                {rent.document_storage_id && (
                                  <ReceiptViewer
                                    documentId={rent.document_storage_id}
                                    fileName={rent.revenue_description || 'Rent Receipt'}
                                    trigger={
                                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                                        <Eye className="h-3 w-3" />
                                      </Button>
                                    }
                                  />
                                )}
                                <Link href={`/rent/log?id=${rent.id}`}>
                                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                                    <Edit className="h-3 w-3" />
                                  </Button>
                                </Link>
                                <Button 
                                  variant="ghost" 
                                  size="sm" 
                                  className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                                  onClick={() => handleDelete(rent.id)}
                                  disabled={deletingId === rent.id}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}
