'use client';

import { useState, useEffect } from 'react';
import { useExpenses } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileDown } from 'lucide-react';
import { format } from 'date-fns';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  is_active: boolean;
}

export default function ExportExpensesPage() {
  const { data: properties } = usePropertiesHook();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [year, setYear] = useState<string>(new Date().getFullYear().toString());
  const [exportType, setExportType] = useState<'fy' | 'all'>('fy');
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(true);

  const { data: expenses } = useExpenses(selectedPropertyId || undefined);

  // Fetch all units for all properties
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

  // Helper function to get unit description (property + unit number)
  const getUnitDescription = (propertyId: string, unitId: string | undefined) => {
    if (!unitId) return '';
    const property = properties?.items.find(p => p.id === propertyId);
    const unit = units.find(u => u.id === unitId);
    if (!property || !unit) return '';
    return `${property.display_name || 'Property'} - Unit ${unit.unit_number}`;
  };

  const handleExport = () => {
    if (!expenses?.items.length) {
      alert('No expenses to export');
      return;
    }

    // Filter expenses
    let filteredExpenses = expenses.items;

    if (exportType === 'fy' && year) {
      const startDate = new Date(parseInt(year), 0, 1);
      const endDate = new Date(parseInt(year), 11, 31);
      filteredExpenses = expenses.items.filter(exp => {
        const expDate = new Date(exp.date);
        return expDate >= startDate && expDate <= endDate;
      });
    }

    // Convert to CSV - removed 'Is Planned' column
    // CSV escape function: escape quotes and wrap in quotes if contains comma, quote, or newline
    const escapeCsv = (value: string): string => {
      const str = String(value || '');
      // If contains comma, quote, or newline, wrap in quotes and escape internal quotes
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const headers = ['ID', 'Property', 'Unit', 'Date', 'Description', 'Amount', 'Vendor', 'Expense Type', 'Expense Category', 'Notes', 'Has Receipt', 'Created At', 'Updated At'];
    const rows = filteredExpenses.map(exp => {
      const unitDesc = getUnitDescription(exp.property_id, exp.unit_id);

      return [
        escapeCsv(String(exp.id || '')),
        escapeCsv(String(properties?.items.find(p => p.id === exp.property_id)?.display_name || '')),
        escapeCsv(String(unitDesc || '')),
        escapeCsv(String(exp.date || '')),
        escapeCsv(String(exp.description || '')),
        escapeCsv(String(Number(exp.amount || 0).toFixed(2))),
        escapeCsv(String(exp.vendor || '')),
        escapeCsv(String(exp.expense_type || '')),
        escapeCsv(String(exp.expense_category || '')),
        escapeCsv(String(exp.notes || '')),
        escapeCsv((() => {
          // Handle has_receipt: true, false, null, undefined
          // Explicitly check for boolean false (not just falsy)
          if (exp.has_receipt === true) return 'Yes';
          if (exp.has_receipt === false) return 'No';
          // If has_receipt is null/undefined, check document_storage_id
          if (exp.has_receipt == null) {
            return exp.document_storage_id ? 'Yes' : 'No';
          }
          // Default to No if we can't determine
          return 'No';
        })()),
        escapeCsv(String(exp.created_at || '')),
        escapeCsv(String(exp.updated_at || ''))
      ];
    });

    const csv = [
      headers.map(escapeCsv).join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `expenses_${exportType === 'fy' ? year : 'all'}_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs text-gray-500 mb-1">Export:</div>
        <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <FileDown className="h-5 w-5" />
          Export Expenses
        </h1>
        <p className="text-sm text-gray-600 mt-1">Export expenses to CSV for accounting</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="text-sm font-bold">Export Options</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Property
            </label>
            <select
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs bg-white text-gray-900 h-8"
            >
              <option value="">All Properties</option>
              {properties?.items.map((prop) => (
                <option key={prop.id} value={prop.id}>
                  {prop.display_name || prop.address_line1 || prop.id}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Export Type
            </label>
            <select
              value={exportType}
              onChange={(e) => setExportType(e.target.value as 'fy' | 'all')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs bg-white text-gray-900 h-8"
            >
              <option value="fy">Fiscal Year</option>
              <option value="all">All Time</option>
            </select>
          </div>

          {exportType === 'fy' && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Year
              </label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                min="2000"
                max={new Date().getFullYear() + 1}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-xs bg-white text-gray-900 h-8"
              />
            </div>
          )}

          <Button
            onClick={handleExport}
            disabled={loadingUnits || !expenses?.items.length}
            className="bg-black text-white hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed h-8 text-xs mt-4"
          >
            <FileDown className="h-3 w-3 mr-1.5" />
            {loadingUnits ? 'Loading units...' : 'Export to CSV'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

