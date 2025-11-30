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
  affordabilityPercent: number;
  marketCompetition: number;
}

export default function SetRentAnalysisTab({ propertyId, property }: Props) {
  const [expenses, setExpenses] = useState<ScheduledExpense[]>([]);
  const [revenues, setRevenues] = useState<ScheduledRevenue[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInputs, setShowInputs] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  // User-editable fields
  const [minRent, setMinRent] = useState(1800);
  const [maxRent, setMaxRent] = useState(3000);
  const [rentIncrement, setRentIncrement] = useState(50);

  const isMultiUnit = property?.property_type === 'multi_family' || property?.property_type === 'duplex';

  // Market competition - % of comparable listings at or below this price
  const getMarketCompetition = (monthlyRent: number): number => {
    // Interpolated from histogram data for 3br/2ba listings
    if (monthlyRent <= 1000) return 4;
    if (monthlyRent <= 1100) return 6.5;
    if (monthlyRent <= 1200) return 9;
    if (monthlyRent <= 1300) return 10;
    if (monthlyRent <= 1400) return 11;
    if (monthlyRent <= 1500) return 16.5;
    if (monthlyRent <= 1600) return 22;
    if (monthlyRent <= 1700) return 30;
    if (monthlyRent <= 1800) return 38;
    if (monthlyRent <= 1900) return 48;
    if (monthlyRent <= 2000) return 58;
    if (monthlyRent <= 2100) return 64.5;
    if (monthlyRent <= 2200) return 71;
    if (monthlyRent <= 2300) return 76.5;
    if (monthlyRent <= 2400) return 82;
    if (monthlyRent <= 2500) return 85.5;
    if (monthlyRent <= 2600) return 89;
    if (monthlyRent <= 2700) return 91;
    if (monthlyRent <= 2800) return 93;
    if (monthlyRent <= 2900) return 96.5;
    return 100;
  };

  // Estimate affordability based on rent level
  const estimateAffordability = (monthlyRent: number): number => {
    // Linear interpolation between two segments:
    // Segment 1: $2000 (37%) to $2500 (27%)
    // Segment 2: $2500 (27%) to $3000 (14%)
    
    if (monthlyRent <= 2000) {
      // Below $2000, use 37%
      return 37;
    } else if (monthlyRent <= 2500) {
      // Segment 1: Linear interpolation from $2000 (37%) to $2500 (27%)
      const rentRange = 2500 - 2000; // 500
      const affordRange = 27 - 37; // -10
      const rentDiff = monthlyRent - 2000;
      return 37 + (affordRange * rentDiff / rentRange);
    } else if (monthlyRent <= 3000) {
      // Segment 2: Linear interpolation from $2500 (27%) to $3000 (14%)
      const rentRange = 3000 - 2500; // 500
      const affordRange = 14 - 27; // -13
      const rentDiff = monthlyRent - 2500;
      return 27 + (affordRange * rentDiff / rentRange);
    } else {
      // Above $3000, use 14%
      return 14;
    }
  };

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
      const affordabilityPercent = estimateAffordability(monthlyRent);
      const marketCompetition = getMarketCompetition(monthlyRent);

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
        affordabilityPercent,
        marketCompetition,
      });
    }

    return rows;
  }, [minRent, maxRent, rentIncrement, unitCount, vacancyRate, taxAndInsurance, capex, maintenance, vacancyCosts, annualPI, downPayment, totalRevenue]);

  // Find first row with positive cash flow
  const firstPositiveCashFlowIdx = rentRows.findIndex(r => r.cashFlow > 0);
  
  // Find optimal rent using hidden formula: (Afford % / 3) + (CoC % × 2) - (Market Comp % / 3) - (aggregate change from 2 rows ago)
  // Only consider rows with positive CoC
  const optimalRentIdx = useMemo(() => {
    const positiveCoCRows = rentRows
      .map((row, idx) => ({ row, idx }))
      .filter(({ row }) => row.cocPercent > 0);
    
    if (positiveCoCRows.length === 0) return -1;
    
    const scored = positiveCoCRows.map(({ row, idx }) => {
      // Calculate aggregate change from 2 rows prior
      const twoRowsAgo = idx >= 2 ? rentRows[idx - 2] : null;
      const changeFrom2Ago = twoRowsAgo ? row.marketCompetition - twoRowsAgo.marketCompetition : 0;
      
      return {
        idx,
        score: (row.affordabilityPercent / 2.8) + (row.cocPercent * 2) - (row.marketCompetition / 3) - changeFrom2Ago
      };
    });
    
    const best = scored.reduce((best, current) => 
      current.score > best.score ? current : best
    );
    
    return best.idx;
  }, [rentRows]);

  // Calculate quick rent (90% of optimal, rounded up to nearest $50) for faster rental (within 30 days)
  const quickRentIdx = useMemo(() => {
    if (optimalRentIdx === -1) return -1;
    
    const optimalRent = rentRows[optimalRentIdx].monthlyRent;
    const reducedRent = optimalRent * 0.9;
    const quickRent = Math.ceil(reducedRent / 50) * 50; // Round up to nearest $50
    
    // Find the row that matches this rent amount
    const idx = rentRows.findIndex(r => r.monthlyRent === quickRent);
    return idx;
  }, [rentRows, optimalRentIdx]);

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
        {/* Compact Input Fields - Collapsible */}
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
            Input Parameters
          </button>
          
          {showInputs && (
            <div className="bg-gray-50 border rounded-lg p-3">
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
          )}
        </div>

        {/* Summary Card - Collapsible */}
        <div className="mb-4">
          <button
            onClick={() => setShowSummary(!showSummary)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900 mb-2"
          >
            {showSummary ? (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            )}
            Financial Summary
          </button>
          
          {showSummary && (
            <div className="border-2 rounded-lg p-4 bg-blue-50 border-blue-600">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-xs text-gray-600 mb-1">Unit Count</div>
                  <div className="font-semibold text-blue-700">{unitCount}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">Vacancy Rate</div>
                  <div className="font-semibold text-blue-700">{(vacancyRate * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">Down Payment</div>
                  <div className="font-semibold text-blue-700">${(downPayment / 1000).toFixed(0)}k</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">Annual P&I</div>
                  <div className="font-semibold text-orange-700">${annualPI.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                </div>
              </div>
              
              <div className="border-t mt-4 pt-4">
                <div className="text-xs font-semibold text-gray-700 mb-2">Annual Expenses</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Tax & Insurance</div>
                    <div className="font-semibold text-red-700">${taxAndInsurance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">From scheduled</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">CapEx</div>
                    <div className="font-semibold text-red-700">${capex.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">{expenseTotals.capex > 0 ? 'Scheduled' : 'Default'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Maintenance</div>
                    <div className="font-semibold text-red-700">${maintenance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">{expenseTotals.maintenance > 0 ? 'Scheduled' : 'Default'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Vacancy Costs</div>
                    <div className="font-semibold text-red-700">${vacancyCosts.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">Utilities while vacant</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">P&I</div>
                    <div className="font-semibold text-red-700">${annualPI.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">{expenseTotals.pi > 0 ? 'Scheduled' : 'Calculated'}</div>
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
                <th className="text-right p-2 font-semibold">Afford %</th>
                <th className="text-right p-2 font-semibold">Market %</th>
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
                const isOptimal = idx === optimalRentIdx;
                const isQuickRent = idx === quickRentIdx;
                
                let rowClass = 'border-b border-gray-200 hover:bg-gray-50';
                if (isQuickRent) {
                  rowClass = 'border-2 border-green-600 bg-green-50 hover:bg-green-100';
                } else if (isOptimal) {
                  rowClass = 'border-2 border-blue-600 hover:bg-blue-50';
                }
                
                return (
                  <tr key={idx} className={rowClass}>
                    <td className="p-2 sticky left-0 bg-white">
                      <div className="flex items-center gap-1">
                        {isQuickRent && (
                          <svg className="h-4 w-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        )}
                        {isOptimal && !isQuickRent && (
                          <svg className="h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        <span>${row.monthlyRent.toLocaleString()}</span>
                      </div>
                    </td>
                    <td className="text-right p-2">{row.affordabilityPercent}%</td>
                    <td className="text-right p-2">{row.marketCompetition.toFixed(1)}%</td>
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
