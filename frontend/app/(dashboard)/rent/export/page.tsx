'use client';

import { useState } from 'react';
import { useRents } from '@/lib/hooks/use-rent';
import { useProperties } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileDown } from 'lucide-react';
import { format } from 'date-fns';

export default function ExportRentsPage() {
  const { data: properties } = useProperties();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [year, setYear] = useState<string>(new Date().getFullYear().toString());
  const [exportType, setExportType] = useState<'fy' | 'all'>('fy');

  const { data: rentsData } = useRents(
    selectedPropertyId ? { property_id: selectedPropertyId } : {}
  );

  const rents = rentsData?.items || [];

  const getPropertyName = (propertyId: string) => {
    const prop = properties?.items.find(p => p.id === propertyId);
    return prop?.display_name || prop?.address_line1 || propertyId;
  };

  const handleExport = () => {
    if (!rents.length) {
      alert('No rent payments to export');
      return;
    }

    // Filter rents
    let filteredRents = rents;

    if (exportType === 'fy' && year) {
      const startDate = new Date(parseInt(year), 0, 1);
      const endDate = new Date(parseInt(year), 11, 31);
      filteredRents = rents.filter(rent => {
        const paymentDate = new Date(rent.payment_date);
        return paymentDate >= startDate && paymentDate <= endDate;
      });
    }

    // CSV escape function: escape quotes and wrap in quotes if contains comma, quote, or newline
    const escapeCsv = (value: string | number | boolean | null | undefined): string => {
      if (value === null || value === undefined) return '';
      const str = String(value);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const headers = [
      'ID',
      'Property',
      'Unit',
      'Tenant',
      'Revenue Description',
      'Is Non-IRS Revenue',
      'Is One-Time Fee',
      'Rent Period Month',
      'Rent Period Year',
      'Rent Period Start',
      'Rent Period End',
      'Amount',
      'Payment Date',
      'Payment Method',
      'Transaction Reference',
      'Is Late',
      'Late Fee',
      'Notes',
      'Created At',
      'Updated At'
    ];

    const rows = filteredRents.map(rent => {
      return [
        escapeCsv(rent.id || ''),
        escapeCsv(rent.property_name || getPropertyName(rent.property_id) || ''),
        escapeCsv(rent.unit_name || ''),
        escapeCsv(rent.tenant_name || ''),
        escapeCsv(rent.revenue_description || ''),
        escapeCsv(rent.is_non_irs_revenue ? 'Yes' : 'No'),
        escapeCsv(rent.is_one_time_fee ? 'Yes' : 'No'),
        escapeCsv(rent.rent_period_month || ''),
        escapeCsv(rent.rent_period_year || ''),
        escapeCsv(rent.rent_period_start || ''),
        escapeCsv(rent.rent_period_end || ''),
        escapeCsv(Number(rent.amount || 0).toFixed(2)),
        escapeCsv(rent.payment_date || ''),
        escapeCsv(rent.payment_method || ''),
        escapeCsv(rent.transaction_reference || ''),
        escapeCsv(rent.is_late ? 'Yes' : 'No'),
        escapeCsv(rent.late_fee ? Number(rent.late_fee).toFixed(2) : ''),
        escapeCsv(rent.notes || ''),
        escapeCsv(rent.created_at || ''),
        escapeCsv(rent.updated_at || '')
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
    a.download = `rents_${selectedPropertyId ? getPropertyName(selectedPropertyId).replace(/[^a-z0-9]/gi, '_') : 'all'}_${exportType === 'fy' ? year : 'all'}_${new Date().toISOString().split('T')[0]}.csv`;
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
          Export Rent Payments
        </h1>
        <p className="text-sm text-gray-600 mt-1">Export rent payments to CSV for accounting</p>
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
            disabled={!selectedPropertyId || !rents.length}
            className="bg-black text-white hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed h-8 text-xs mt-4"
          >
            <FileDown className="h-3 w-3 mr-1.5" />
            Export to CSV
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}




