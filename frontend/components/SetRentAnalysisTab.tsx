'use client';

import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Home } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  current_monthly_rent: number | null;
}

interface Property {
  id: string;
  purchase_price?: number;
  down_payment?: number;
  unit_count?: number;
  vacancy_rate?: number;
  property_type?: string;
  current_monthly_rent?: number;
}

interface ScheduledExpense {
  id: string;
  property_id: string;
  expense_type: string;
  calculated_annual_cost?: number;
}

interface ScheduledRevenue {
  id: string;
  property_id: string;
  calculated_annual_amount?: number;
}

interface UserProfile {
  id: string;
  loc_interest_rate?: number;
  mortgage_interest_rate?: number;
}

interface Props {
  propertyId: string;
  property: Property;
}

interface RentRow {
  monthlyRent: number;
  unitCount: number;
  annualRent: number;
  vacancyCost: number;
  effectiveAnnualRent: number;
  annualExpenses: number;
  downPayment: number;
  cashFlow: number;
  cocPercent: number;
  revenueSchedule: number;
  totalReturnDollars: number;
  totalReturnPercent: number;
}

export default function SetRentAnalysisTab({ propertyId, property }: Props) {
  const [expenses, setExpenses] = useState<ScheduledExpense[]>([]);
  const [revenues, setRevenues] = useState<ScheduledRevenue[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInputs, setShowInputs] = useState(false);

  const isMultiUnit = property?.property_type === 'multi_family' || property?.property_type === 'duplex';

  // Get current rent from property or units
  const getCurrentRent = (): number => {
    if (isMultiUnit && units.length > 0) {
      // For multi-unit, use average rent of units with rent set
      const rentsWithValues = units
        .map(u => u.current_monthly_rent)
        .filter((r): r is number => r !== null && r > 0);
      
      if (rentsWithValues.length > 0) {
        return Math.round(rentsWithValues.reduce((sum, r) => sum + r, 0) / rentsWithValues.length);
      }
    }
    
    // For single-family or if no unit rents are set, use property's current_monthly_rent
    if (property?.current_monthly_rent != null) {
      const rentValue = property.current_monthly_rent as string | number;
      const rent = typeof rentValue === 'string' 
        ? parseFloat(String(rentValue).replace(/[$,]/g, ''))
        : Number(rentValue);
      
      if (!isNaN(rent) && rent > 0) {
        return Math.round(rent);
      }
    }
    
    // Default to $1400 if no rent is set anywhere
    return 1400;
  };

  // Initialize with current rent if available, otherwise default
  const getInitialRent = () => {
    if (property?.current_monthly_rent != null) {
      const rentValue = property.current_monthly_rent as string | number;
      const rent = typeof rentValue === 'string' 
        ? parseFloat(String(rentValue).replace(/[$,]/g, ''))
        : Number(rentValue);
      
      if (!isNaN(rent) && rent > 0) {
        return Math.round(rent);
      }
    }
    return 1400;
  };
  
  const initialRent = getInitialRent();
  
  // User-editable fields - defaults to current rent ± $400
  // IMPORTANT: Use Number() to ensure we're doing numeric addition, not string concatenation
  const [minRent, setMinRent] = useState(Number(initialRent) - 400);
  const [maxRent, setMaxRent] = useState(Number(initialRent) + 400);
  const [rentIncrement, setRentIncrement] = useState(50);

  // Update min/max rent to current rent ± $400 when property or units change
  useEffect(() => {
    const currentRent = getCurrentRent();
    console.log('Setting rent range for current rent:', currentRent, 'min:', currentRent - 400, 'max:', currentRent + 400);
    setMinRent(Number(currentRent) - 400);
    setMaxRent(Number(currentRent) + 400);
  }, [units, loading, property?.current_monthly_rent]);

  useEffect(() => {
    fetchData();
  }, [propertyId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const fetchPromises: Promise<any>[] = [
        apiClient.get<{ items: ScheduledExpense[] }>(`/scheduled-expenses?property_id=${propertyId}`),
        apiClient.get<{ items: ScheduledRevenue[] }>(`/scheduled-revenue?property_id=${propertyId}`),
        apiClient.get<UserProfile>('/users/me')
      ];

      if (isMultiUnit) {
        fetchPromises.push(
          apiClient.get<{ items: Unit[] }>(`/units?property_id=${propertyId}`)
        );
      }

      const results = await Promise.all(fetchPromises);
      
      setExpenses(results[0].items || []);
      setRevenues(results[1].items || []);
      setUserProfile(results[2]);
      
      if (isMultiUnit && results[3]) {
        setUnits(results[3].items || []);
      }
    } catch (err) {
      console.error('Error fetching rent analysis data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate expense totals by category
  const expenseTotals = useMemo(() => {
    const totals = {
      taxAndInsurance: 0,
      capex: 0,
      maintenance: 0,
      pi: 0,
      vacancy: 0,
    };
    
    expenses.forEach(exp => {
      if (exp.expense_type === 'pti') {
        totals.taxAndInsurance += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'capex') {
        totals.capex += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'maintenance') {
        totals.maintenance += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'pi') {
        totals.pi += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'vacancy') {
        totals.vacancy += exp.calculated_annual_cost || 0;
      }
    });
    
    return totals;
  }, [expenses]);

  const totalRevenue = revenues.reduce((sum, r) => sum + (r.calculated_annual_amount || 0), 0);
  
  const unitCount = isMultiUnit ? units.length : 1;
  const vacancyRate = property.vacancy_rate || 0.07;
  const purchasePrice = property.purchase_price || 0;
  const downPayment = property.down_payment || 0;
  const mortgageRate = userProfile?.mortgage_interest_rate || 0.07;
  
  // Use scheduled P&I if available, otherwise calculate it
  let annualPI = expenseTotals.pi;
  if (annualPI === 0) {
    // Calculate P&I payment using mortgage amortization formula
    const loanAmount = purchasePrice - downPayment;
    const monthlyRate = mortgageRate / 12;
    const numPayments = 30 * 12; // 30 year loan
    const monthlyPI = loanAmount > 0 ? loanAmount * 
      (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) / 
      (Math.pow(1 + monthlyRate, numPayments) - 1) : 0;
    annualPI = monthlyPI * 12;
  }
  
  // Tax and Insurance from scheduled expenses
  const taxAndInsurance = expenseTotals.taxAndInsurance;
  
  // Capital Expenses - default to scheduled, fallback to 8000
  const capex = expenseTotals.capex > 0 ? expenseTotals.capex : 8000;
  
  // Maintenance - default to scheduled, fallback to 3000
  const maintenance = expenseTotals.maintenance > 0 ? expenseTotals.maintenance : 3000;
  
  // Vacancy costs (utilities while vacant) from scheduled expenses
  const vacancyCosts = expenseTotals.vacancy;

  // Generate rent analysis rows
  const rentRows: RentRow[] = useMemo(() => {
    const rows: RentRow[] = [];

    // Generate rows for different rent amounts
    for (let monthlyRent = minRent; monthlyRent <= maxRent; monthlyRent += rentIncrement) {
      const annualRent = monthlyRent * unitCount * 12;
      const vacancyCost = annualRent * vacancyRate;
      const effectiveAnnualRent = annualRent - vacancyCost;
      
      const annualExpenses = taxAndInsurance + capex + maintenance + vacancyCosts + annualPI;
      const cashFlow = effectiveAnnualRent - annualExpenses;
      const cocPercent = downPayment > 0 ? (cashFlow / downPayment) * 100 : 0;
      const totalReturnDollars = (effectiveAnnualRent + totalRevenue) - annualExpenses;
      const totalReturnPercent = downPayment > 0 ? (totalReturnDollars / downPayment) * 100 : 0;

      rows.push({
        monthlyRent,
        unitCount,
        annualRent,
        vacancyCost,
        effectiveAnnualRent,
        annualExpenses,
        downPayment,
        cashFlow,
        cocPercent,
        revenueSchedule: totalRevenue,
        totalReturnDollars,
        totalReturnPercent,
      });
    }

    return rows;
  }, [minRent, maxRent, rentIncrement, unitCount, vacancyRate, taxAndInsurance, capex, maintenance, vacancyCosts, annualPI, downPayment, totalRevenue]);

  // Find the row that matches current monthly rent
  const currentRentIdx = useMemo(() => {
    const currentRent = getCurrentRent();
    return rentRows.findIndex(r => r.monthlyRent === currentRent);
  }, [rentRows]);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-8">
          <div className="text-gray-500">Loading rent analysis...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-bold flex items-center gap-2">
          <Home className="h-4 w-4" />
          Set Rent
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Combined Input Parameters and Financial Summary - Collapsible */}
        <div className="mb-4">
          <button
            onClick={() => setShowInputs(!showInputs)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900 mb-2"
          >
            {showInputs ? (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            )}
            Input Parameters & Summary
          </button>
          
          {showInputs && (
            <div className="space-y-4">
              {/* Input Parameters Section */}
              <div className="bg-gray-50 border rounded-lg p-3">
                <div className="text-xs text-gray-600 mb-2">
                  Range automatically set to Current Rent ± $400
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label htmlFor="minRent" className="text-xs">Min Monthly Rent</Label>
                    <Input
                      id="minRent"
                      type="number"
                      step={50}
                      min={0}
                      value={minRent}
                      onChange={(e) => setMinRent(parseInt(e.target.value) || 1800)}
                      className="text-sm h-8"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="maxRent" className="text-xs">Max Monthly Rent</Label>
                    <Input
                      id="maxRent"
                      type="number"
                      step={50}
                      min={minRent}
                      value={maxRent}
                      onChange={(e) => setMaxRent(parseInt(e.target.value) || 3000)}
                      className="text-sm h-8"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="rentIncrement" className="text-xs">Increment</Label>
                    <Input
                      id="rentIncrement"
                      type="number"
                      step={10}
                      min={10}
                      value={rentIncrement}
                      onChange={(e) => setRentIncrement(parseInt(e.target.value) || 50)}
                      className="text-sm h-8"
                    />
                  </div>
                </div>
              </div>

              {/* Financial Summary Section */}
              <div className="border-2 rounded-lg p-4 bg-blue-50 border-blue-600">
                <div className="text-center">
                  <div className="text-xs text-gray-600 mb-1">Current Monthly Rent</div>
                  <div className="font-bold text-3xl text-blue-700">${getCurrentRent().toLocaleString()}</div>
                  <div className="text-xs text-gray-500 mt-1">From property screen</div>
                  <div className="text-xs text-gray-700 mt-3 pt-3 border-t border-blue-200">
                    💡 Compare this rate to market comps at{' '}
                    <a 
                      href="https://www.rentometer.com/" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 underline font-semibold"
                    >
                      Rentometer.com
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-300 bg-gray-100">
                <th className="text-left p-2 font-semibold sticky left-0 bg-gray-100 z-10">Monthly Rent</th>
                <th className="text-right p-2 font-semibold">Units</th>
                <th className="text-right p-2 font-semibold">Annual Rent</th>
                <th className="text-right p-2 font-semibold">Vacancy</th>
                <th className="text-right p-2 font-semibold bg-blue-50">Adjusted Rent</th>
                <th className="text-right p-2 font-semibold">Expenses</th>
                <th className="text-right p-2 font-semibold bg-blue-50">Cash Flow</th>
                <th className="text-right p-2 font-semibold">CoC %</th>
                <th className="text-right p-2 font-semibold">Revenue</th>
                <th className="text-right p-2 font-semibold">Total Return</th>
                <th className="text-right p-2 font-semibold">Total %</th>
              </tr>
            </thead>
            <tbody>
              {rentRows.map((row, idx) => {
                const isCurrentRent = idx === currentRentIdx;
                
                let rowClass = 'border-b border-gray-200 hover:bg-gray-50';
                if (isCurrentRent) {
                  rowClass = 'border-2 border-blue-600 bg-blue-50 hover:bg-blue-100';
                }
                
                return (
                  <tr key={idx} className={rowClass}>
                    <td className="p-2 sticky left-0 bg-white">
                      <div className="flex items-center gap-1">
                        {isCurrentRent && (
                          <svg className="h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        <span>${row.monthlyRent.toLocaleString()}</span>
                      </div>
                    </td>
                    <td className="text-right p-2">{row.unitCount}</td>
                    <td className="text-right p-2">${row.annualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">-${row.vacancyCost.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2 font-semibold bg-blue-50 text-blue-700">${row.effectiveAnnualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">-${row.annualExpenses.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className={`text-right p-2 bg-blue-50 font-medium ${row.cashFlow > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      ${row.cashFlow.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className={`text-right p-2 font-bold ${row.cocPercent > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      {row.cocPercent.toFixed(2)}%
                    </td>
                    <td className="text-right p-2">${row.revenueSchedule.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className={`text-right p-2 font-medium ${row.totalReturnDollars > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      ${row.totalReturnDollars.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className={`text-right p-2 font-bold ${row.totalReturnPercent > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      {row.totalReturnPercent.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        <div className="mt-4 text-xs text-gray-600 space-y-1 bg-gray-50 p-3 rounded">
          <div><strong>Formulas:</strong></div>
          <div>• Annual Rent = Monthly Rent × Unit Count × 12</div>
          <div>• Vacancy (Lost Rent) = Annual Rent × Vacancy Rate</div>
          <div>• <strong>Adjusted Rent = Annual Rent - Vacancy (Lost Rent)</strong></div>
          <div>• Annual Expenses = Tax & Ins + CapEx + Maintenance + Vacancy Costs + P&I</div>
          <div className="ml-4 text-xs text-gray-500">Note: Vacancy Costs = utilities/costs while unit is vacant</div>
          <div>• <strong>Cash Flow = Adjusted Rent - Annual Expenses</strong></div>
          <div>• <strong>Cash on Cash % = Cash Flow ÷ Down Payment × 100%</strong></div>
          <div>• Revenue = Scheduled revenue (appreciation, principal paydown, etc.)</div>
          <div>• Total Return = (Adjusted Rent + Revenue) - Annual Expenses</div>
          <div>• Total % = Total Return ÷ Down Payment × 100%</div>
        </div>
      </CardContent>
    </Card>
  );
}
