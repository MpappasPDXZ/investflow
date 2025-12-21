'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DollarSign, Minus, Equal } from 'lucide-react';
import { useFinancialPerformance } from '@/lib/hooks/use-financial-performance';

interface Props {
  propertyId: string;
  units?: Array<{ id: string; unit_number: string }>;
  isMultiUnit: boolean;
}

export default function FinancialPerformanceTab({ propertyId, units, isMultiUnit }: Props) {
  const [selectedUnitId, setSelectedUnitId] = useState<string>('all');
  
  const { data: performance, isLoading, error } = useFinancialPerformance(
    propertyId,
    selectedUnitId !== 'all' ? selectedUnitId : undefined
  );

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-gray-500 text-sm">Loading financial performance...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="text-red-600 text-sm">Error loading financial performance</div>
      </div>
    );
  }

  if (!performance) {
    return (
      <div className="p-8">
        <div className="text-gray-500 text-sm">No financial data available</div>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatPercent = (value: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(numValue)) return 'N/A';
    return `${numValue.toFixed(2)}%`;
  };

  return (
    <div className="space-y-4">
      {/* Unit Selector for Multi-Unit Properties */}
      {isMultiUnit && units && units.length > 0 && (
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Unit</label>
          <Select value={selectedUnitId} onValueChange={setSelectedUnitId}>
            <SelectTrigger className="w-full max-w-md">
              <SelectValue placeholder="All Units (Property Total)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Units (Property Total)</SelectItem>
              {units.map((unit) => (
                <SelectItem key={unit.id} value={unit.id}>
                  {unit.unit_number}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Year-to-Date Card */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold">Year-to-Date ({new Date().getFullYear()})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {/* Rent Collected */}
            <div className="flex justify-between items-center py-1.5 border-b">
              <span className="text-xs text-gray-600">Rent Collected</span>
              <span className="text-xs font-medium text-gray-900">{formatCurrency(performance.ytd_rent)}</span>
            </div>
            
            {/* Minus label */}
            <div className="flex items-center gap-1.5 py-0.5">
              <Minus className="h-2.5 w-2.5 text-gray-400" />
              <span className="text-[10px] text-gray-500 font-medium">Less: Expenses</span>
            </div>
            
            {/* PITI */}
            {performance.ytd_piti > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">PITI</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_piti)})</span>
              </div>
            )}
            
            {/* Utilities */}
            {performance.ytd_utilities > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Utilities</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_utilities)})</span>
              </div>
            )}
            
            {/* Maintenance */}
            {performance.ytd_maintenance > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Maintenance</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_maintenance)})</span>
              </div>
            )}
            
            {/* CapEx */}
            {performance.ytd_capex > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">CapEx</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_capex)})</span>
              </div>
            )}
            
            {/* Insurance */}
            {performance.ytd_insurance > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Insurance</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_insurance)})</span>
              </div>
            )}
            
            {/* Property Management */}
            {performance.ytd_property_management > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Property Mgmt</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_property_management)})</span>
              </div>
            )}
            
            {/* Other */}
            {performance.ytd_other > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Other</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.ytd_other)})</span>
              </div>
            )}
            
            {/* Total Expenses */}
            <div className="flex justify-between items-center py-1.5 border-t border-b font-medium">
              <span className="text-xs text-gray-700">Total Expenses</span>
              <span className="text-xs text-red-600">({formatCurrency(performance.ytd_expenses)})</span>
            </div>
            
            {/* Equals label */}
            <div className="flex items-center gap-1.5 py-0.5">
              <Equal className="h-2.5 w-2.5 text-gray-400" />
              <span className="text-[10px] text-gray-500 font-medium">Equals:</span>
            </div>
            
            {/* Profit/Loss */}
            <div className={`flex justify-between items-center p-2 rounded ${
              performance.ytd_profit_loss >= 0
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <span className={`text-xs font-bold ${
                performance.ytd_profit_loss >= 0 ? 'text-green-700' : 'text-red-700'
              }`}>
                Profit / (Loss)
              </span>
              <span className={`text-base font-bold ${
                performance.ytd_profit_loss >= 0 ? 'text-green-900' : 'text-red-900'
              }`}>
                {formatCurrency(performance.ytd_profit_loss)}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Cumulative (All-Time) Card */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold">Cumulative (All-Time)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {/* Rent Collected */}
            <div className="flex justify-between items-center py-1.5 border-b">
              <span className="text-xs text-gray-600">Rent Collected</span>
              <span className="text-xs font-medium text-gray-900">{formatCurrency(performance.cumulative_rent)}</span>
            </div>
            
            {/* Minus label */}
            <div className="flex items-center gap-1.5 py-0.5">
              <Minus className="h-2.5 w-2.5 text-gray-400" />
              <span className="text-[10px] text-gray-500 font-medium">Less: Expenses</span>
            </div>
            
            {/* PITI */}
            {performance.cumulative_piti > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">PITI</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_piti)})</span>
              </div>
            )}
            
            {/* Utilities */}
            {performance.cumulative_utilities > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Utilities</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_utilities)})</span>
              </div>
            )}
            
            {/* Maintenance */}
            {performance.cumulative_maintenance > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Maintenance</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_maintenance)})</span>
              </div>
            )}
            
            {/* CapEx */}
            {performance.cumulative_capex > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">CapEx</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_capex)})</span>
              </div>
            )}
            
            {/* Insurance */}
            {performance.cumulative_insurance > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Insurance</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_insurance)})</span>
              </div>
            )}
            
            {/* Property Management */}
            {performance.cumulative_property_management > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Property Mgmt</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_property_management)})</span>
              </div>
            )}
            
            {/* Other */}
            {performance.cumulative_other > 0 && (
              <div className="flex justify-between items-center pl-4">
                <span className="text-xs text-gray-600">Other</span>
                <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_other)})</span>
              </div>
            )}
            
            {/* Total Expenses */}
            <div className="flex justify-between items-center py-1.5 border-t border-b font-medium">
              <span className="text-xs text-gray-700">Total Expenses</span>
              <span className="text-xs text-red-600">({formatCurrency(performance.cumulative_expenses)})</span>
            </div>
            
            {/* Equals label */}
            <div className="flex items-center gap-1.5 py-0.5">
              <Equal className="h-2.5 w-2.5 text-gray-400" />
              <span className="text-[10px] text-gray-500 font-medium">Equals:</span>
            </div>
            
            {/* Profit/Loss */}
            <div className={`flex justify-between items-center p-2 rounded ${
              performance.cumulative_profit_loss >= 0
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <span className={`text-xs font-bold ${
                performance.cumulative_profit_loss >= 0 ? 'text-green-700' : 'text-red-700'
              }`}>
                Profit / (Loss)
              </span>
              <span className={`text-base font-bold ${
                performance.cumulative_profit_loss >= 0 ? 'text-green-900' : 'text-red-900'
              }`}>
                {formatCurrency(performance.cumulative_profit_loss)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cash on Cash Return - Full Width */}
      {performance.cash_on_cash !== null && performance.cash_on_cash !== undefined && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold">Cash on Cash Return</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {/* Main Value */}
              <div className="flex justify-between items-center pb-2 border-b">
                <span className="text-xs text-gray-600">Cash on Cash %</span>
                <span className="text-xl font-bold text-purple-900">{formatPercent(performance.cash_on_cash)}</span>
              </div>
              
              {/* Formula Breakdown with Actual Values */}
              <div className="text-[10px] text-gray-700 space-y-1 bg-gray-50 p-3 rounded">
                <div className="font-semibold mb-2">Formulas with Actual Values:</div>
                <div>• <strong>Annual Rent</strong> = YTD Rent Annualized ({formatCurrency(performance.ytd_rent)})</div>
                <div>• <strong>Vacancy (Lost Rent)</strong> = Calculated in vacancy expenses</div>
                <div>• <strong>Adjusted Rent</strong> = Annual Rent - Vacancy</div>
                <div>• <strong>Annual Expenses</strong> = Tax & Ins + CapEx + Maintenance + Vacancy Costs + P&I ({formatCurrency(performance.ytd_expenses)})</div>
                <div className="ml-4 text-[9px] text-gray-500">
                  Tax & Ins ({formatCurrency(performance.ytd_insurance)}) + 
                  CapEx ({formatCurrency(performance.ytd_capex)}) + 
                  Maintenance ({formatCurrency(performance.ytd_maintenance)}) + 
                  Vacancy/Utilities ({formatCurrency(performance.ytd_utilities)}) + 
                  P&I ({formatCurrency(performance.ytd_piti)}) + 
                  Other ({formatCurrency(performance.ytd_other)})
                </div>
                <div>• <strong>Cash Flow</strong> = Adjusted Rent - Annual Expenses = <strong>{formatCurrency(performance.ytd_profit_loss)}</strong></div>
                <div className="pt-1 border-t border-gray-300 mt-2">
                  <strong>• Cash on Cash % = Cash Flow ÷ Cash Invested × 100%</strong>
                </div>
                <div className="ml-4 text-[9px] text-gray-600 italic">
                  = {formatCurrency(performance.ytd_profit_loss)} ÷ Cash Invested × 100% = {formatPercent(performance.cash_on_cash)}
                </div>
                <div className="mt-2 pt-2 border-t border-gray-300">
                  <div className="text-[9px] text-gray-500 italic">
                    Note: Uses manually entered Cash Invested (down payment + cash rehab costs)
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Note */}
      <div className="text-[10px] text-gray-500 italic">
        <strong>Note:</strong> Rehab expenses are excluded from this calculation as they are included in P&I financing.
      </div>
    </div>
  );
}
