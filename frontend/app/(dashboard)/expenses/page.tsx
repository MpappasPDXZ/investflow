'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useExpenses, useExpenseSummary, useDeleteExpense } from '@/lib/hooks/use-expenses';
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
  Building2
} from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';
import type { Expense } from '@/lib/types';

// Expense type labels (for the main expense type dropdown)
const EXPENSE_TYPE_LABELS: Record<string, string> = {
  'maintenance': 'Maintenance',
  'capex': 'CapEx',
  'rehab': 'Rehab',
  'pandi': 'P&I',
  'utilities': 'Utilities',
  'insurance': 'Insurance',
  'property_management': 'Prop Mgmt',
  'other': 'Other'
};

// Cost code categories (the new numbered categories)
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

export default function ExpensesPage() {
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [selectedExpenseType, setSelectedExpenseType] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set()); // "propertyId-year"
  const [showFilters, setShowFilters] = useState(false);
  const [hasInitializedExpansion, setHasInitializedExpansion] = useState(false);
  
  const { data: properties } = usePropertiesHook();
  const { data: expenses, isLoading } = useExpenses(selectedPropertyId || undefined);
  const { data: summary } = useExpenseSummary(selectedPropertyId || undefined);
  const deleteExpense = useDeleteExpense();

  // Auto-expand current year on initial load
  useEffect(() => {
    if (!hasInitializedExpansion && expenses?.items && expenses.items.length > 0) {
      const currentYear = new Date().getFullYear();
      const newExpandedYears = new Set<string>();
      const newExpandedProperties = new Set<string>();
      
      // Find all properties that have expenses in the current year
      expenses.items.forEach(expense => {
        const expenseYear = new Date(expense.date).getFullYear();
        if (expenseYear === currentYear) {
          const propId = expense.property_id || 'unassigned';
          newExpandedProperties.add(propId);
          newExpandedYears.add(`${propId}-${currentYear}`);
        }
      });
      
      setExpandedProperties(newExpandedProperties);
      setExpandedYears(newExpandedYears);
      setHasInitializedExpansion(true);
    }
  }, [expenses, hasInitializedExpansion]);

  // Filter expenses
  const filteredExpenses = useMemo(() => {
    if (!expenses?.items) return [];
    
    let filtered = expenses.items;
    
    if (selectedExpenseType) {
      filtered = filtered.filter(e => e.expense_type === selectedExpenseType);
    }
    if (startDate) {
      filtered = filtered.filter(e => e.date >= startDate);
    }
    if (endDate) {
      filtered = filtered.filter(e => e.date <= endDate);
    }
    
    return filtered;
  }, [expenses, selectedExpenseType, startDate, endDate]);

  // Group by property, then by year
  const groupedByPropertyAndYear = useMemo(() => {
    const result: Record<string, Record<number, Expense[]>> = {};
    
    filteredExpenses.forEach(expense => {
      const propId = expense.property_id || 'unassigned';
      const year = new Date(expense.date).getFullYear();
      
      if (!result[propId]) result[propId] = {};
      if (!result[propId][year]) result[propId][year] = [];
      result[propId][year].push(expense);
    });
    
    // Sort expenses within each year by date (newest first)
    Object.values(result).forEach(years => {
      Object.values(years).forEach(exps => {
        exps.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      });
    });
    
    return result;
  }, [filteredExpenses]);

  // Calculate totals by type for a list of expenses
  const calculateTypeBreakdown = (exps: Expense[]) => {
    const breakdown: Record<string, number> = {};
    EXPENSE_CATEGORIES.forEach(t => breakdown[t.key] = 0);
    exps.forEach(e => {
      const category = e.expense_category || 'other';
      if (breakdown[category] !== undefined) {
        breakdown[category] += Number(e.amount);
      }
    });
    return breakdown;
  };

  // Get property name
  const getPropertyName = (propId: string) => {
    if (propId === 'unassigned') return 'Unassigned';
    const prop = properties?.items.find(p => p.id === propId);
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

  const handleDelete = async (id: string, description: string) => {
    if (confirm(`Delete expense "${description}"?`)) {
      await deleteExpense.mutateAsync(id);
    }
  };

  const exportToCSV = () => {
    if (!expenses?.items) return;
    const headers = ['Property', 'Date', 'Description', 'Amount', 'Type', 'Vendor', 'Notes'];
    const rows = expenses.items.map(e => [
      getPropertyName(e.property_id || 'unassigned'),
      e.date,
      `"${e.description.replace(/"/g, '""')}"`,
      e.amount.toFixed(2),
      e.expense_type,
      e.vendor || '',
      `"${(e.notes || '').replace(/"/g, '""')}"`,
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `expenses-${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatAmount = (amt: number) => 
    amt > 0 ? `$${amt.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '-';

  // Sort properties by name
  const sortedPropertyIds = Object.keys(groupedByPropertyAndYear).sort((a, b) => 
    getPropertyName(a).localeCompare(getPropertyName(b))
  );

  return (
    <div className="p-3 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
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
            disabled={!expenses?.items?.length}
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

      {/* Summary Row */}
      {summary && (
        <div className="flex gap-3 mb-3 text-xs">
          <div className="bg-blue-50 px-2 py-1 rounded">
            <span className="text-blue-600">Total:</span>{' '}
            <span className="font-bold text-blue-900">
              ${summary.grand_total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="bg-gray-50 px-2 py-1 rounded">
            <span className="text-gray-600">Count:</span>{' '}
            <span className="font-bold">{summary.total_count}</span>
          </div>
        </div>
      )}

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
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
            >
              <option value="">All Properties</option>
              {properties?.items.map((prop) => (
                <option key={prop.id} value={prop.id}>
                  {prop.display_name || prop.address_line1 || prop.id}
                </option>
              ))}
            </select>
            <select
              value={selectedExpenseType}
              onChange={(e) => setSelectedExpenseType(e.target.value)}
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
            >
              <option value="">All Types</option>
              {EXPENSE_CATEGORIES.map(t => (
                <option key={t.key} value={t.key}>{t.fullLabel}</option>
              ))}
            </select>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
              placeholder="Start"
            />
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-2 py-2 md:py-1 border border-gray-300 rounded text-sm md:text-xs min-h-[44px] md:min-h-0"
              placeholder="End"
            />
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8 text-gray-500 text-sm">Loading expenses...</div>
      )}

      {/* Empty State */}
      {!isLoading && filteredExpenses.length === 0 && (
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

      {/* Grouped by Property, then Year */}
      {sortedPropertyIds.map(propId => {
        const years = groupedByPropertyAndYear[propId];
        const sortedYears = Object.keys(years).map(Number).sort((a, b) => b - a);
        const allPropertyExpenses = sortedYears.flatMap(y => years[y]);
        const propertyTotal = allPropertyExpenses.reduce((sum, e) => sum + Number(e.amount), 0);
        const propertyBreakdown = calculateTypeBreakdown(allPropertyExpenses);
        const isPropertyExpanded = expandedProperties.has(propId);

        return (
          <Card key={propId} className="mb-3">
            {/* Property Header with Type Breakdown */}
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
                <span className="text-xs text-gray-500">({allPropertyExpenses.length})</span>
                <span className="ml-auto font-bold text-sm">
                  ${propertyTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
              
              {/* Type Breakdown Row - Desktop */}
              <div className="hidden md:flex gap-1 mt-2 flex-wrap">
                {EXPENSE_CATEGORIES.map(t => (
                  <div 
                    key={t.key}
                    className={`text-[10px] px-1.5 py-0.5 rounded ${expenseCategoryBadgeColors[t.key]}`}
                    title={t.fullLabel}
                  >
                    {t.label}: {formatAmount(propertyBreakdown[t.key])}
                  </div>
                ))}
              </div>
            </CardHeader>

            {/* Years within Property */}
            {isPropertyExpanded && (
              <CardContent className="p-0">
                {sortedYears.map(year => {
                  const yearExpenses = years[year];
                  const yearKey = `${propId}-${year}`;
                  const isYearExpanded = expandedYears.has(yearKey);
                  const yearTotal = yearExpenses.reduce((sum, e) => sum + Number(e.amount), 0);
                  const yearBreakdown = calculateTypeBreakdown(yearExpenses);

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
                        <span className="text-[10px] text-gray-500">({yearExpenses.length})</span>
                        <span className="ml-auto font-semibold text-xs">
                          ${yearTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                      </div>

                      {/* Year Type Breakdown - collapsed view */}
                      {!isYearExpanded && (
                        <div className="hidden md:flex gap-1 px-3 pb-2 flex-wrap">
                          {EXPENSE_CATEGORIES.filter(t => yearBreakdown[t.key] > 0).map(t => (
                            <div 
                              key={t.key}
                              className={`text-[9px] px-1 py-0.5 rounded ${expenseCategoryBadgeColors[t.key]}`}
                            >
                              {t.label}: {formatAmount(yearBreakdown[t.key])}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Expense List */}
                      {isYearExpanded && (
                        <div className="divide-y">
                          {yearExpenses.map(expense => (
                            <div 
                              key={expense.id}
                              className="px-3 py-2 flex items-center gap-2 hover:bg-gray-50"
                            >
                              {/* Date */}
                              <span className="text-[10px] text-gray-500 w-16 shrink-0">
                                {format(new Date(expense.date), 'MM/dd')}
                              </span>
                              
                              {/* Type Badge */}
                              <span className={`text-[9px] px-1 py-0.5 rounded shrink-0 ${expenseCategoryBadgeColors[expense.expense_category] || 'bg-gray-100'}`}>
                                {EXPENSE_CATEGORIES.find(t => t.key === expense.expense_category)?.label || EXPENSE_TYPE_LABELS[expense.expense_type] || expense.expense_type}
                              </span>
                              
                              {/* Description */}
                              <span className="text-xs truncate flex-1">
                                {expense.description}
                              </span>
                              
                              {/* Vendor */}
                              {expense.vendor && (
                                <span className="text-[10px] text-gray-400 truncate max-w-[80px] hidden sm:inline">
                                  {expense.vendor}
                                </span>
                              )}
                              
                              {/* Amount */}
                              <span className="font-semibold text-xs w-16 text-right shrink-0">
                                ${Number(expense.amount).toLocaleString()}
                              </span>
                              
                              {/* Actions */}
                              <div className="flex gap-1 shrink-0">
                                {expense.document_storage_id && (
                                  <ReceiptViewer
                                    documentId={expense.document_storage_id}
                                    fileName={expense.description}
                                    fileType="image/jpeg"
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
