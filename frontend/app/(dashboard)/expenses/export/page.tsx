'use client';

import { useState } from 'react';
import { useExpenses } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileDown } from 'lucide-react';
import { format } from 'date-fns';

export default function ExportExpensesPage() {
  const { data: properties } = usePropertiesHook();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [year, setYear] = useState<string>(new Date().getFullYear().toString());
  const [exportType, setExportType] = useState<'fy' | 'all'>('fy');
  
  const { data: expenses } = useExpenses(selectedPropertyId || undefined);

  const handleExport = () => {
    console.log('📤 [EXPORT] Exporting expenses');
    console.log('📝 [EXPORT] Property:', selectedPropertyId || 'All');
    console.log('📝 [EXPORT] Type:', exportType);
    console.log('📝 [EXPORT] Year:', year);

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

    // Convert to CSV
    const headers = ['Date', 'Description', 'Amount', 'Type', 'Vendor', 'Property'];
    const rows = filteredExpenses.map(exp => [
      format(new Date(exp.date), 'yyyy-MM-dd'),
      exp.description,
      exp.amount.toFixed(2),
      exp.expense_type,
      exp.vendor || '',
      properties?.items.find(p => p.id === exp.property_id)?.display_name || '',
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
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

    console.log('✅ [EXPORT] CSV exported:', filteredExpenses.length, 'expenses');
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Export Expenses</h1>
        <p className="text-gray-600 mt-1">Export expenses to CSV for accounting</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Export Options</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Property
            </label>
            <select
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
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
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Export Type
            </label>
            <select
              value={exportType}
              onChange={(e) => setExportType(e.target.value as 'fy' | 'all')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="fy">Fiscal Year</option>
              <option value="all">All Time</option>
            </select>
          </div>

          {exportType === 'fy' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Year
              </label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                min="2000"
                max={new Date().getFullYear() + 1}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
            </div>
          )}

          <Button
            onClick={handleExport}
            className="bg-black text-white hover:bg-gray-800"
          >
            <FileDown className="h-4 w-4 mr-2" />
            Export to CSV
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

