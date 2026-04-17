'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useExpensesByYear, useExpenseSummary, useDeleteExpense } from '@/lib/hooks/use-expenses';
import type { ExpenseSummary } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Plus,
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  Trash2,
  Edit2,
  DollarSign,
  Filter,
  Eye,
  Building2,
  Loader2
} from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';
import type { Expense } from '@/lib/types';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  is_active: boolean;
}

const EXPENSE_TYPE_LABELS: Record<string, string> = {
  'maintenance': 'Maintenance',
  'capex': 'CapEx',
  'rehab': 'Rehab',
  'pandi': 'P&I',
  'tax': 'Tax',
  'utilities': 'Utilities',
  'insurance': 'Insurance',
  'property_management': 'Prop Mgmt',
  'other': 'Other'
};

const TAX_CATEGORY_LABELS: Record<string, string> = {
  'advertising': 'Advertising',
  'auto_travel': 'Auto/Travel',
  'cleaning': 'Cleaning',
  'commissions': 'Commissions',
  'insurance': 'Insurance',
  'legal_professional': 'Legal/Prof',
  'management_fees': 'Mgmt Fees',
  'mortgage_interest': 'Mortgage Int',
  'other_interest': 'Other Int',
  'repairs': 'Repairs',
  'supplies': 'Supplies',
  'taxes': 'Taxes',
  'utilities': 'Utilities',
  'capital_improvement': 'CapEx',
  'other': 'Other',
};

const TAX_CATEGORIES = [
  { key: 'advertising', label: 'Advert', fullLabel: 'Line 5 - Advertising' },
  { key: 'auto_travel', label: 'Auto', fullLabel: 'Line 6 - Auto and travel' },
  { key: 'cleaning', label: 'Clean', fullLabel: 'Line 7 - Cleaning and maintenance' },
  { key: 'commissions', label: 'Comm', fullLabel: 'Line 8 - Commissions' },
  { key: 'insurance', label: 'Insur', fullLabel: 'Line 9 - Insurance' },
  { key: 'legal_professional', label: 'Legal', fullLabel: 'Line 10 - Legal and professional fees' },
  { key: 'management_fees', label: 'Mgmt', fullLabel: 'Line 11 - Management fees' },
  { key: 'mortgage_interest', label: 'Mortg', fullLabel: 'Line 12 - Mortgage interest' },
  { key: 'other_interest', label: 'OthInt', fullLabel: 'Line 13 - Other interest' },
  { key: 'repairs', label: 'Repair', fullLabel: 'Line 14 - Repairs' },
  { key: 'supplies', label: 'Supply', fullLabel: 'Line 15 - Supplies' },
  { key: 'taxes', label: 'Taxes', fullLabel: 'Line 16 - Taxes' },
  { key: 'utilities', label: 'Util', fullLabel: 'Line 17 - Utilities' },
  { key: 'capital_improvement', label: 'CapEx', fullLabel: 'Line 18 - Capital improvements' },
  { key: 'other', label: 'Other', fullLabel: 'Line 19 - Other' },
];

const EXPENSE_CATEGORIES = [
  { key: 'co_equip', label: '10-Co Eq', fullLabel: '10 - Co. Equipment' },
  { key: 'rent_equip', label: '20-Rent', fullLabel: '20 - Rented Equip.' },
  { key: 'equip_maint', label: '30-Maint', fullLabel: '30 - Equip. Maint.' },
  { key: 'small_tools', label: '40-Tools', fullLabel: '40 - Small Tools' },
  { key: 'bulk_comm', label: '50-Bulk', fullLabel: '50 - Bulk Commodities' },
  { key: 'eng_equip', label: '60-Eng', fullLabel: '60 - Eng. Equipment' },
  { key: 'subs', label: '70-Subs', fullLabel: '70 - Subcontractors' },
  { key: 'other', label: '80-Other', fullLabel: '80 - Other' },
];

const taxCategoryBadgeColors: Record<string, string> = {
  advertising: 'bg-cyan-100 text-cyan-800',
  auto_travel: 'bg-amber-100 text-amber-800',
  cleaning: 'bg-lime-100 text-lime-800',
  commissions: 'bg-rose-100 text-rose-800',
  insurance: 'bg-indigo-100 text-indigo-800',
  legal_professional: 'bg-violet-100 text-violet-800',
  management_fees: 'bg-fuchsia-100 text-fuchsia-800',
  mortgage_interest: 'bg-red-100 text-red-800',
  other_interest: 'bg-orange-100 text-orange-800',
  repairs: 'bg-blue-100 text-blue-800',
  supplies: 'bg-teal-100 text-teal-800',
  taxes: 'bg-yellow-100 text-yellow-800',
  utilities: 'bg-green-100 text-green-800',
  capital_improvement: 'bg-purple-100 text-purple-800',
  other: 'bg-gray-100 text-gray-800',
};

const expenseCategoryBadgeColors: Record<string, string> = {
  co_equip: 'bg-purple-100 text-purple-800',
  rent_equip: 'bg-indigo-100 text-indigo-800',
  equip_maint: 'bg-blue-100 text-blue-800',
  small_tools: 'bg-yellow-100 text-yellow-800',
  bulk_comm: 'bg-green-100 text-green-800',
  eng_equip: 'bg-orange-100 text-orange-800',
  subs: 'bg-pink-100 text-pink-800',
  other: 'bg-gray-100 text-gray-800',
};

const formatAmount = (amt: number) =>
  amt > 0 ? `$${amt.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '-';

function YearExpenses({
  propertyId,
  year,
  selectedExpenseType,
  vendorFilter,
  units,
  properties,
}: {
  propertyId: string;
  year: number;
  selectedExpenseType: string;
  vendorFilter: string;
  units: Unit[];
  properties: any;
}) {
  const { data, isLoading } = useExpensesByYear(propertyId, year);
  const deleteExpense = useDeleteExpense();

  const filteredExpenses = useMemo(() => {
    if (!data?.items) return [];
    let filtered = data.items;
    if (selectedExpenseType) {
      filtered = filtered.filter(e => e.expense_type === selectedExpenseType);
    }
    if (vendorFilter) {
      const lowerFilter = vendorFilter.toLowerCase();
      filtered = filtered.filter(e =>
        e.vendor?.toLowerCase().includes(lowerFilter) ||
        e.description?.toLowerCase().includes(lowerFilter)
      );
    }
    return [...filtered].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [data, selectedExpenseType, vendorFilter]);

  const handleDelete = async (id: string, description: string) => {
    if (confirm(`Delete expense "${description}"?`)) {
      await deleteExpense.mutateAsync(id);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4 text-gray-400 text-xs gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading {year} expenses...
      </div>
    );
  }

  if (filteredExpenses.length === 0) {
    return (
      <div className="text-center py-3 text-gray-400 text-xs">
        {selectedExpenseType || vendorFilter ? 'No matching expenses' : 'No expenses'}
      </div>
    );
  }

  return (
    <div className="divide-y">
      {filteredExpenses.map(expense => (
        <div
          key={expense.id}
          className="px-3 py-2 flex items-center gap-2 hover:bg-gray-50"
        >
          <span className="text-[10px] text-gray-500 w-16 shrink-0">
            {expense.date.slice(5).replace('-', '/')}
          </span>
          <span className={`text-[9px] px-1 py-0.5 rounded shrink-0 ${expense.tax_category ? taxCategoryBadgeColors[expense.tax_category] || 'bg-gray-100' : 'bg-gray-100'}`}>
            {TAX_CATEGORY_LABELS[expense.tax_category || ''] || EXPENSE_TYPE_LABELS[expense.expense_type] || expense.expense_type}
          </span>
          <span className="text-xs truncate flex-1">
            {expense.description}
          </span>
          {expense.vendor && (
            <span className="text-[10px] text-gray-400 truncate max-w-[80px] hidden sm:inline">
              {expense.vendor}
            </span>
          )}
          <span className="font-semibold text-xs w-16 text-right shrink-0">
            ${Number(expense.amount).toLocaleString()}
          </span>
          <div className="flex gap-1 shrink-0">
            {expense.document_storage_id && (
              <ReceiptViewer
                documentId={expense.document_storage_id}
                fileName={expense.description}
                trigger={
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                    <Eye className="h-3 w-3" />
                  </Button>
                }
              />
            )}
            <Link href={`/expenses/${expense.id}/edit`}>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                <Edit2 className="h-3 w-3" />
              </Button>
            </Link>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
              onClick={() => handleDelete(expense.id, expense.description)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ExpensesPage() {
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [selectedExpenseType, setSelectedExpenseType] = useState<string>('');
  const [vendorFilter, setVendorFilter] = useState<string>('');
  const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [hasInitializedExpansion, setHasInitializedExpansion] = useState(false);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(true);

  const { data: properties } = usePropertiesHook();
  const { data: summary, isLoading } = useExpenseSummary(selectedPropertyId || undefined);

  useEffect(() => {
    if (!selectedPropertyId && properties?.items && properties.items.length > 0) {
      setSelectedPropertyId(properties.items[0].id);
    }
  }, [properties, selectedPropertyId]);

  useEffect(() => {
    const fetchAllUnits = async () => {
      if (!properties?.items) return;
      setLoadingUnits(true);
      try {
        const allUnits: Unit[] = [];
        for (const property of properties.items) {
          const response = await apiClient.get<{ items: Unit[] }>(`/units?property_id=${property.id}`);
          allUnits.push(...response.items);
        }
        setUnits(allUnits);
      } catch (err) {
        console.error('Error fetching units:', err);
      } finally {
        setLoadingUnits(false);
      }
    };
    fetchAllUnits();
  }, [properties]);

  useEffect(() => {
    if (!hasInitializedExpansion && summary && summary.yearly_totals.length > 0 && selectedPropertyId) {
      const currentYear = new Date().getFullYear();
      const newExpandedYears = new Set<string>();
      const newExpandedProperties = new Set<string>();

      summary.yearly_totals.forEach(yt => {
        if (yt.year >= currentYear) {
          newExpandedProperties.add(selectedPropertyId);
          newExpandedYears.add(`${selectedPropertyId}-${yt.year}`);
        }
      });

      if (newExpandedProperties.size === 0) {
        newExpandedProperties.add(selectedPropertyId);
      }

      setExpandedProperties(newExpandedProperties);
      setExpandedYears(newExpandedYears);
      setHasInitializedExpansion(true);
    }
  }, [summary, hasInitializedExpansion, selectedPropertyId]);

  const handlePropertyChange = (newPropertyId: string) => {
    setSelectedPropertyId(newPropertyId);
    setHasInitializedExpansion(false);
    setExpandedProperties(new Set());
    setExpandedYears(new Set());
  };

  const getPropertyName = (propId: string) => {
    if (propId === 'unassigned') return 'Unassigned';
    const prop = properties?.items.find(p => p.id === propId);
    return prop?.display_name || prop?.address_line1 || 'Unknown Property';
  };

  const toggleProperty = (propId: string) => {
    setExpandedProperties(prev => {
      const newSet = new Set(prev);
      if (newSet.has(propId)) newSet.delete(propId);
      else newSet.add(propId);
      return newSet;
    });
  };

  const toggleYear = (propId: string, year: number) => {
    const key = `${propId}-${year}`;
    setExpandedYears(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) newSet.delete(key);
      else newSet.add(key);
      return newSet;
    });
  };

  const getUnitDescription = (propertyId: string, unitId: string | undefined) => {
    if (!unitId) return '';
    const property = properties?.items.find(p => p.id === propertyId);
    const unit = units.find(u => u.id === unitId);
    if (!property || !unit) return '';
    return `${property.display_name || 'Property'} - Unit ${unit.unit_number}`;
  };

  const exportToCSV = async () => {
    if (!selectedPropertyId) return;

    const params = new URLSearchParams();
    params.append('property_id', selectedPropertyId);
    params.append('limit', '1000');
    try {
      const allExpenses = await apiClient.get<{ items: Expense[] }>(`/expenses?${params.toString()}`);
      if (!allExpenses?.items?.length) return;

      const headers = ['ID', 'Property', 'Unit', 'Date', 'Description', 'Amount', 'Vendor', 'Expense Type', 'Expense Category', 'IRS Category', 'Notes', 'Has Receipt', 'Created At', 'Updated At'];
      const escapeCsv = (value: string): string => {
        const str = String(value || '');
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      };

      const rows = allExpenses.items.map(e => [
        escapeCsv(String(e.id || '')),
        escapeCsv(String(getPropertyName(e.property_id || 'unassigned'))),
        escapeCsv(String(getUnitDescription(e.property_id, e.unit_id) || '')),
        escapeCsv(String(e.date || '')),
        escapeCsv(String(e.description || '')),
        escapeCsv(String(Number(e.amount || 0).toFixed(2))),
        escapeCsv(String(e.vendor || '')),
        escapeCsv(String(e.expense_type || '')),
        escapeCsv(String(e.expense_category || '')),
        escapeCsv(String(TAX_CATEGORY_LABELS[e.tax_category || ''] || e.tax_category || '')),
        escapeCsv(String(e.notes || '')),
        escapeCsv(e.has_receipt === true ? 'Yes' : e.has_receipt === false ? 'No' : e.document_storage_id ? 'Yes' : 'No'),
        escapeCsv(String(e.created_at || '')),
        escapeCsv(String(e.updated_at || ''))
      ]);

      const csv = [headers.map(escapeCsv).join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `expenses-${format(new Date(), 'yyyy-MM-dd')}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting expenses:', err);
    }
  };

  const isPropertyExpanded = expandedProperties.has(selectedPropertyId);
  const sortedYears = summary?.yearly_totals.map(yt => yt.year).sort((a, b) => b - a) ?? [];

  return (
    <div className="pt-0 px-3 pb-3 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-1.5">
        <div>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <DollarSign className="h-3.5 w-3.5" />
            Expenses
          </h1>
          <p className="text-xs text-gray-500">Track property expenses for CPA</p>
        </div>
        <div className="flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            onClick={exportToCSV}
            disabled={loadingUnits || !summary?.total_count}
            className="h-7 text-xs px-2"
          >
            <Download className="h-3 w-3 mr-1" />
            Export
          </Button>
          <Link href="/expenses/add">
            <Button size="sm" className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
              <Plus className="h-3 w-3 mr-1" />
              Add
            </Button>
          </Link>
        </div>
      </div>

      {/* Property Filter */}
      <div className="mb-2">
        <select
          value={selectedPropertyId}
          onChange={(e) => handlePropertyChange(e.target.value)}
          className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full md:w-auto min-w-[200px]"
          required
        >
          <option value="">Select Property</option>
          {properties?.items.map((prop) => (
            <option key={prop.id} value={prop.id}>
              {prop.display_name || prop.address_line1 || prop.id}
            </option>
          ))}
        </select>
      </div>

      {/* Filters */}
      <div className="mb-3">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-900"
        >
          <Filter className="h-3 w-3" />
          {showFilters ? 'Hide Filters' : 'Filters'}
          {showFilters ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </button>
        {showFilters && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
            <select
              value={selectedExpenseType}
              onChange={(e) => setSelectedExpenseType(e.target.value)}
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
            >
              <option value="">All Expense Types</option>
              {Object.entries(EXPENSE_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <input
              type="text"
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              placeholder="Search vendor/description"
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
            />
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8 text-gray-500 text-sm">Loading expenses...</div>
      )}

      {/* Empty State */}
      {!isLoading && !selectedPropertyId && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <DollarSign className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Please select a property to view expenses</p>
          </CardContent>
        </Card>
      )}
      {!isLoading && selectedPropertyId && summary && summary.total_count === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <DollarSign className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No expenses found</p>
            <Link href="/expenses/add">
              <Button size="sm" className="mt-3">Add Expense</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Property Card */}
      {selectedPropertyId && summary && summary.total_count > 0 && (
        <Card className="mb-3">
          <CardHeader
            className="py-2 px-3 cursor-pointer hover:bg-gray-50"
            onClick={() => toggleProperty(selectedPropertyId)}
          >
            <div className="flex items-center gap-2">
              {isPropertyExpanded ? (
                <ChevronDown className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-gray-400" />
              )}
              <Building2 className="h-4 w-4 text-gray-600" />
              <span className="font-semibold text-sm">{getPropertyName(selectedPropertyId)}</span>
              <span className="text-xs text-gray-500">({summary.total_count})</span>
              <span className="ml-auto font-bold text-sm">
                ${summary.grand_total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="hidden md:flex gap-1 mt-2 flex-wrap">
              {TAX_CATEGORIES.filter(t => (summary.tax_category_totals?.[t.key] || 0) > 0).map(t => (
                <div
                  key={t.key}
                  className={`text-[10px] px-1.5 py-0.5 rounded ${taxCategoryBadgeColors[t.key]}`}
                  title={t.fullLabel}
                >
                  {t.label}: {formatAmount(summary.tax_category_totals[t.key] || 0)}
                </div>
              ))}
            </div>
          </CardHeader>

          {isPropertyExpanded && (
            <CardContent className="p-0">
              {sortedYears.map(year => {
                const yearData = summary.yearly_totals.find(yt => yt.year === year)!;
                const yearKey = `${selectedPropertyId}-${year}`;
                const isYearExpanded = expandedYears.has(yearKey);

                return (
                  <div key={year} className="border-t">
                    <div
                      className="flex items-center gap-2 px-3 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
                      onClick={() => toggleYear(selectedPropertyId, year)}
                    >
                      {isYearExpanded ? (
                        <ChevronDown className="h-3 w-3 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-3 w-3 text-gray-400" />
                      )}
                      <span className="font-medium text-xs">{year}</span>
                      <span className="text-[10px] text-gray-500">({yearData.count})</span>
                      <span className="ml-auto font-semibold text-xs">
                        ${yearData.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    {!isYearExpanded && (
                      <div className="hidden md:flex gap-1 px-3 pb-2 flex-wrap">
                        {TAX_CATEGORIES.filter(t => (yearData.by_tax_category?.[t.key] || 0) > 0).map(t => (
                          <div
                            key={t.key}
                            className={`text-[9px] px-1 py-0.5 rounded ${taxCategoryBadgeColors[t.key]}`}
                          >
                            {t.label}: {formatAmount(yearData.by_tax_category[t.key] || 0)}
                          </div>
                        ))}
                      </div>
                    )}

                    {isYearExpanded && (
                      <YearExpenses
                        propertyId={selectedPropertyId}
                        year={year}
                        selectedExpenseType={selectedExpenseType}
                        vendorFilter={vendorFilter}
                        units={units}
                        properties={properties}
                      />
                    )}
                  </div>
                );
              })}
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
