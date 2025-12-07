'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, DollarSign, Calendar, TrendingDown, Percent } from 'lucide-react';
import { useFinancialPerformance } from '@/lib/hooks/use-financial-performance';

interface Props {
  propertyId: string;
  units?: Array<{ id: string; unit_number: string }>;
  isMultiUnit: boolean;
}

export default function FinancialPerformanceTab({ propertyId, units, isMultiUnit }: Props) {
  const [selectedUnitId, setSelectedUnitId] = useState<string>('');
  
  const { data: performance, isLoading, error } = useFinancialPerformance(
    propertyId,
    selectedUnitId || undefined
  );

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-gray-500">Loading financial performance...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="text-red-600">Error loading financial performance</div>
      </div>
    );
  }

  if (!performance) {
    return (
      <div className="p-8">
        <div className="text-gray-500">No financial data available</div>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercent = (value: number | null) => {
    if (value === null) return 'N/A';
    return `${value.toFixed(2)}%`;
  };

  return (
    <div className="space-y-6">
      {/* Unit Selector for Multi-Unit Properties */}
      {isMultiUnit && units && units.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold">Select Unit</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={selectedUnitId} onValueChange={setSelectedUnitId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="All Units (Property Total)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Units (Property Total)</SelectItem>
                {units.map((unit) => (
                  <SelectItem key={unit.id} value={unit.id}>
                    {unit.unit_number}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      )}

      {/* Year-to-Date Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-bold">
            <Calendar className="h-4 w-4" />
            Year-to-Date Performance ({new Date().getFullYear()})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="text-sm text-green-700 font-medium mb-1">Rent Collected</div>
              <div className="text-2xl font-bold text-green-900">
                {formatCurrency(performance.ytd_rent)}
              </div>
            </div>
            
            <div className="p-4 bg-red-50 rounded-lg border border-red-200">
              <div className="text-sm text-red-700 font-medium mb-1">Expenses (excl. Rehab)</div>
              <div className="text-2xl font-bold text-red-900">
                {formatCurrency(performance.ytd_expenses)}
              </div>
            </div>
            
            <div className={`p-4 rounded-lg border ${
              performance.ytd_profit_loss >= 0
                ? 'bg-blue-50 border-blue-200'
                : 'bg-orange-50 border-orange-200'
            }`}>
              <div className={`text-sm font-medium mb-1 flex items-center gap-1 ${
                performance.ytd_profit_loss >= 0 ? 'text-blue-700' : 'text-orange-700'
              }`}>
                {performance.ytd_profit_loss >= 0 ? (
                  <TrendingUp className="h-4 w-4" />
                ) : (
                  <TrendingDown className="h-4 w-4" />
                )}
                Profit / (Loss)
              </div>
              <div className={`text-2xl font-bold ${
                performance.ytd_profit_loss >= 0 ? 'text-blue-900' : 'text-orange-900'
              }`}>
                {formatCurrency(performance.ytd_profit_loss)}
              </div>
            </div>
          </div>
          
          <div className="mt-4 pt-4 border-t text-sm text-gray-600">
            <strong>Note:</strong> Expenses exclude rehab costs, as those are included in P&I financing.
          </div>
        </CardContent>
      </Card>

      {/* Cumulative (All-Time) Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-bold">
            <DollarSign className="h-4 w-4" />
            Cumulative Performance (All-Time)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="text-sm text-green-700 font-medium mb-1">Total Rent Collected</div>
              <div className="text-2xl font-bold text-green-900">
                {formatCurrency(performance.cumulative_rent)}
              </div>
            </div>
            
            <div className="p-4 bg-red-50 rounded-lg border border-red-200">
              <div className="text-sm text-red-700 font-medium mb-1">Total Expenses</div>
              <div className="text-2xl font-bold text-red-900">
                {formatCurrency(performance.cumulative_expenses)}
              </div>
            </div>
            
            <div className={`p-4 rounded-lg border ${
              performance.cumulative_profit_loss >= 0
                ? 'bg-blue-50 border-blue-200'
                : 'bg-orange-50 border-orange-200'
            }`}>
              <div className={`text-sm font-medium mb-1 flex items-center gap-1 ${
                performance.cumulative_profit_loss >= 0 ? 'text-blue-700' : 'text-orange-700'
              }`}>
                {performance.cumulative_profit_loss >= 0 ? (
                  <TrendingUp className="h-4 w-4" />
                ) : (
                  <TrendingDown className="h-4 w-4" />
                )}
                Total Profit / (Loss)
              </div>
              <div className={`text-2xl font-bold ${
                performance.cumulative_profit_loss >= 0 ? 'text-blue-900' : 'text-orange-900'
              }`}>
                {formatCurrency(performance.cumulative_profit_loss)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Cash on Cash Return */}
      {performance.cash_on_cash !== null && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-bold">
              <Percent className="h-4 w-4" />
              Cash on Cash Return
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
              <div className="text-sm text-purple-700 font-medium mb-1">
                (Current Market Value - Purchase Price) / Purchase Price
              </div>
              <div className="text-3xl font-bold text-purple-900">
                {formatPercent(performance.cash_on_cash)}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Last Calculated Timestamp */}
      <div className="text-xs text-gray-500 text-right">
        Last calculated: {new Date(performance.last_calculated_at).toLocaleDateString()}
      </div>
    </div>
  );
}

