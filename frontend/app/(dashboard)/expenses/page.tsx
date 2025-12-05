'use client';

import { useState, useMemo } from 'react';
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
  Eye
} from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';
import type { Expense } from '@/lib/types';

interface GroupedExpenses {
  [year: number]: Expense[];
}

export default function ExpensesPage() {
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [selectedExpenseType, setSelectedExpenseType] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  
  const { data: properties } = usePropertiesHook();
  const { data: expenses, isLoading } = useExpenses(selectedPropertyId || undefined);
  const { data: summary } = useExpenseSummary(selectedPropertyId || undefined);
  const deleteExpense = useDeleteExpense();

  const expenseTypeLabels: Record<string, string> = {
    capex: 'CapEx',
    rehab: 'Rehab',
    pandi: 'P&I',
    utilities: 'Utilities',
    maintenance: 'Maintenance',
    insurance: 'Insurance',
    property_management: 'Prop Mgmt',
    other: 'Other',
  };

  const expenseTypeBadgeColors: Record<string, string> = {
    capex: 'bg-purple-100 text-purple-800',
    rehab: 'bg-indigo-100 text-indigo-800',
    pandi: 'bg-blue-100 text-blue-800',
    utilities: 'bg-yellow-100 text-yellow-800',
    maintenance: 'bg-orange-100 text-orange-800',
    insurance: 'bg-green-100 text-green-800',
    property_management: 'bg-pink-100 text-pink-800',
    other: 'bg-gray-100 text-gray-800',
  };

  // Filter and group expenses by year
  const groupedExpenses = useMemo(() => {
    if (!expenses?.items) return {};

    let filtered = expenses.items;

    // Filter by expense type
    if (selectedExpenseType) {
      filtered = filtered.filter(e => e.expense_type === selectedExpenseType);
    }

    // Filter by date range
    if (startDate) {
      filtered = filtered.filter(e => e.date >= startDate);
    }
    if (endDate) {
      filtered = filtered.filter(e => e.date <= endDate);
    }

    // Group by year
    const grouped: GroupedExpenses = {};
    filtered.forEach(expense => {
      const year = new Date(expense.date).getFullYear();
      if (!grouped[year]) {
        grouped[year] = [];
      }
      grouped[year].push(expense);
    });

    // Sort each year's expenses by date (newest first)
    Object.keys(grouped).forEach(year => {
      grouped[Number(year)].sort((a, b) => 
        new Date(b.date).getTime() - new Date(a.date).getTime()
      );
    });

    return grouped;
  }, [expenses, selectedExpenseType, startDate, endDate]);

  // Get sorted years (newest first)
  const sortedYears = useMemo(() => {
    return Object.keys(groupedExpenses)
      .map(Number)
      .sort((a, b) => b - a);
  }, [groupedExpenses]);

  // Calculate year totals (ensure amounts are numbers)
  const yearTotals = useMemo(() => {
    const totals: Record<number, number> = {};
    Object.entries(groupedExpenses).forEach(([year, yearExpenses]) => {
      totals[Number(year)] = yearExpenses.reduce((sum: number, e: Expense) => sum + Number(e.amount), 0);
    });
    return totals;
  }, [groupedExpenses]);

  // Grand total
  const grandTotal = useMemo(() => {
    return Object.values(yearTotals).reduce((sum, total) => sum + total, 0);
  }, [yearTotals]);

  const toggleYear = (year: number) => {
    setExpandedYears(prev => {
      const newSet = new Set(prev);
      if (newSet.has(year)) {
        newSet.delete(year);
      } else {
        newSet.add(year);
      }
      return newSet;
    });
  };

  const expandAll = () => {
    setExpandedYears(new Set(sortedYears));
  };

  const collapseAll = () => {
    setExpandedYears(new Set());
  };

  const handleDelete = async (id: string, description: string) => {
    if (confirm(`Delete expense "${description}"?`)) {
      await deleteExpense.mutateAsync(id);
    }
  };

  const exportToCSV = () => {
    if (!expenses?.items) return;

    const headers = ['Date', 'Description', 'Amount', 'Type', 'Vendor', 'Notes'];
    const rows = expenses.items.map(e => [
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

  return (
    <div className="p-3 max-w-5xl mx-auto">
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
          {summary.yearly_totals[0] && (
            <div className="bg-green-50 px-2 py-1 rounded">
              <span className="text-green-600">{summary.yearly_totals[0].year}:</span>{' '}
              <span className="font-bold text-green-900">
                ${summary.yearly_totals[0].total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
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
              {Object.entries(expenseTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
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

      {/* Expense List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-2 px-3">
          <CardTitle className="text-sm font-semibold">Expenses by Year</CardTitle>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" onClick={expandAll} className="h-6 px-2 text-xs">
              Expand
            </Button>
            <Button variant="ghost" size="sm" onClick={collapseAll} className="h-6 px-2 text-xs">
              Collapse
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-2">
          {isLoading ? (
            <div className="text-center py-6 text-gray-500 text-xs">Loading...</div>
          ) : sortedYears.length === 0 ? (
            <div className="text-center py-6 text-gray-500">
              <FileText className="h-8 w-8 mx-auto text-gray-300 mb-1" />
              <p className="text-xs">No expenses found.</p>
              <Link href="/expenses/add" className="text-blue-600 hover:underline text-xs">
                Add your first expense
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedYears.map(year => {
                const isExpanded = expandedYears.has(year);
                const yearExpenses = groupedExpenses[year];
                const yearTotal = yearTotals[year];

                return (
                  <div key={year}>
                    {/* Year Header - Mobile friendly touch target */}
                    <button
                      onClick={() => toggleYear(year)}
                      className="flex items-center justify-between w-full text-left hover:bg-gray-50 active:bg-gray-100 px-2 py-3 md:py-1 rounded min-h-[44px]"
                    >
                      <div className="flex items-center gap-1.5">
                        {isExpanded ? (
                          <ChevronDown className="h-3 w-3 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-3 w-3 text-gray-500" />
                        )}
                        <span className="text-sm font-semibold text-gray-900">{year}</span>
                        <span className="text-xs text-gray-500">({yearExpenses.length})</span>
                      </div>
                      <div className="text-sm font-semibold text-red-700">
                        ${yearTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </button>

                    {/* Year Items - Responsive layout */}
                    {isExpanded && (
                      <div className="space-y-2 md:space-y-1 ml-2 md:ml-5 mt-2 md:mt-1">
                        {yearExpenses.map((expense) => (
                          <div 
                            key={expense.id} 
                            className="flex flex-col md:flex-row md:justify-between md:items-center py-3 md:py-1 px-3 md:px-2 bg-gray-50 rounded text-sm md:text-xs gap-2 md:gap-0"
                          >
                            {/* Mobile: Stacked layout, Desktop: Inline */}
                            <div className="flex items-start md:items-center gap-2 flex-1 min-w-0">
                              <span className="text-gray-500 w-12 shrink-0">
                                {format(new Date(expense.date), 'M/d')}
                              </span>
                              <div className="flex flex-col md:flex-row md:items-center gap-1 md:gap-2 flex-1 min-w-0">
                                <span className="font-medium text-gray-900 truncate">
                                  {expense.description}
                                </span>
                                <div className="flex items-center gap-2">
                                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${expenseTypeBadgeColors[expense.expense_type] || 'bg-gray-100'}`}>
                                    {expenseTypeLabels[expense.expense_type] || expense.expense_type}
                                  </span>
                                  {expense.vendor && (
                                    <span className="text-gray-400 truncate hidden sm:inline text-xs">
                                      {expense.vendor}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            {/* Actions row - larger touch targets on mobile */}
                            <div className="flex items-center justify-between md:justify-end gap-3 md:gap-1 shrink-0 pl-14 md:pl-0">
                              <span className="font-semibold text-gray-900 mr-2 md:mr-1 text-base md:text-xs">
                                ${Number(expense.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </span>
                              <div className="flex items-center gap-1">
                                {expense.document_storage_id && (
                                  <ReceiptViewer 
                                    expenseId={expense.id}
                                    trigger={
                                      <button 
                                        className="text-gray-400 hover:text-blue-600 active:text-blue-700 p-2 md:p-0.5 -m-1 md:m-0 min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 flex items-center justify-center"
                                        title="View receipt"
                                      >
                                        <Eye className="h-5 w-5 md:h-3 md:w-3" />
                                      </button>
                                    }
                                  />
                                )}
                                <Link href={`/expenses/${expense.id}/edit`}>
                                  <button className="text-gray-400 hover:text-blue-600 active:text-blue-700 p-2 md:p-0.5 -m-1 md:m-0 min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 flex items-center justify-center">
                                    <Edit2 className="h-5 w-5 md:h-3 md:w-3" />
                                  </button>
                                </Link>
                                <button
                                  onClick={() => handleDelete(expense.id, expense.description)}
                                  className="text-gray-400 hover:text-red-600 active:text-red-700 p-2 md:p-0.5 -m-1 md:m-0 min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 flex items-center justify-center"
                                >
                                  <Trash2 className="h-5 w-5 md:h-3 md:w-3" />
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Grand Total */}
              <div className="flex justify-between items-center p-2 bg-red-100 rounded font-bold text-sm mt-3">
                <span>Total Expenses</span>
                <span className="text-red-700">
                  ${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
