'use client';

import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DollarSign } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  current_monthly_rent: number | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
  downPayment: number;
  percentOfPurchase: number;
  monthlyRent: number;
  unitCount: number;
  annualRent: number;
  vacancyCost: number;
  effectiveAnnualRent: number;
  repairCosts: number;
  taxAndInsurance: number;
  capex: number;
  maintenance: number;
  annualPI: number;
  totalExpenses: number;
  cashFlow: number;
  bankRatio: number;
  cashOnCash: number;
}

export default function RentAnalysisTab({ propertyId, property }: Props) {
  const [expenses, setExpenses] = useState<ScheduledExpense[]>([]);
  const [revenues, setRevenues] = useState<ScheduledRevenue[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInputs, setShowInputs] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  // User-editable fields
  const [downPayment, setDownPayment] = useState(25000);
  const [monthlyRent, setMonthlyRent] = useState(0);
  const [repairFinancingAmount, setRepairFinancingAmount] = useState(0);

  const DOWN_PAYMENT_INCREMENT = 25000;
  const MIN_DOWN_PAYMENT = 25000;
  const LOAN_TERM_YEARS = 30;

  const isMultiUnit = property?.property_type === 'multi_family' || property?.property_type === 'duplex';

  // Calculate monthly P&I payment using standard mortgage formula
  const calculateMonthlyPI = (loanAmount: number, interestRate: number): number => {
    const monthlyRate = interestRate / 12;
    const numPayments = LOAN_TERM_YEARS * 12;
    
    if (loanAmount === 0) return 0;
    
    const payment = loanAmount * 
      (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) / 
      (Math.pow(1 + monthlyRate, numPayments) - 1);
    
    return payment;
  };

  useEffect(() => {
    fetchData();
  }, [propertyId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch expenses, revenues, user profile, and units in parallel
      const fetchPromises: Promise<any>[] = [
        apiClient.get<{ items: ScheduledExpense[] }>(`/scheduled-expenses?property_id=${propertyId}`),
        apiClient.get<{ items: ScheduledRevenue[] }>(`/scheduled-revenue?property_id=${propertyId}`),
        apiClient.get<UserProfile>('/users/me')
      ];

      // Only fetch units if it's a multi-unit property
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
        const fetchedUnits = results[3].items || [];
        setUnits(fetchedUnits);
        
        // Calculate average rent from units with rent
        if (fetchedUnits.length > 0) {
          const unitsWithRent = fetchedUnits.filter((u: Unit) => u.current_monthly_rent);
          if (unitsWithRent.length > 0) {
            const avgRent = unitsWithRent.reduce((sum: number, u: Unit) => sum + (u.current_monthly_rent || 0), 0) / unitsWithRent.length;
            setMonthlyRent(avgRent);
          }
        }
      } else {
        // Single unit - use property rent
        setMonthlyRent(property.current_monthly_rent || 0);
      }
      
      // Set initial down payment from property if available
      if (property.down_payment) {
        setDownPayment(property.down_payment);
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
    };
    
    expenses.forEach(exp => {
      if (exp.expense_type === 'pti') {
        totals.taxAndInsurance += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'capex') {
        totals.capex += exp.calculated_annual_cost || 0;
      } else if (exp.expense_type === 'maintenance') {
        totals.maintenance += exp.calculated_annual_cost || 0;
      }
    });
    
    return totals;
  }, [expenses]);

  // Calculated values based on inputs
  const unitCount = isMultiUnit ? units.length : 1;
  const purchasePrice = property.purchase_price || 0;
  const percentOfPurchase = purchasePrice > 0 ? (downPayment / purchasePrice) * 100 : 0;
  const annualRent = monthlyRent * unitCount * 12;
  const vacancyRate = property.vacancy_rate || 0.07;
  const vacancyCost = annualRent * vacancyRate;
  const effectiveAnnualRent = annualRent - vacancyCost;
  
  // LOC rate from user profile
  const locRate = userProfile?.loc_interest_rate || 0.07;
  const mortgageRate = userProfile?.mortgage_interest_rate || 0.07;
  
  // Repair costs = repair financing amount × LOC rate
  const repairCosts = repairFinancingAmount * locRate;
  
  // Tax and Insurance from scheduled expenses
  const taxAndInsurance = expenseTotals.taxAndInsurance;
  
  // Capital Expenses - default to scheduled, fallback to 8000
  const capex = expenseTotals.capex > 0 ? expenseTotals.capex : 8000;
  
  // Maintenance - default to scheduled, fallback to 3000
  const maintenance = expenseTotals.maintenance > 0 ? expenseTotals.maintenance : 3000;
  
  // Calculate P&I - Simple interest calculation for display
  const loanAmount = purchasePrice - downPayment;
  const annualInterest = loanAmount * mortgageRate;
  
  // Total expenses (excluding P&I for some calculations)
  const totalExpensesExcludingPI = repairCosts + taxAndInsurance + capex + maintenance;
  const totalExpenses = totalExpensesExcludingPI + annualInterest;
  
  // Cash Flow = Effective Annual Rent - Total Expenses
  const cashFlow = effectiveAnnualRent - totalExpenses;
  
  // BANK RATIO (DSCR - Debt Service Coverage Ratio):
  // Adjusted Rents = Rent/Unit × Units × (1 - Vacancy Rate)
  const adjustedRents = effectiveAnnualRent;
  // Operating Expenses = 35% × Adjusted Rents (bank's simplified calculation)
  const operatingExpenses = adjustedRents * 0.35;
  // Net Operating Income = Adjusted Rents - Operating Expenses
  const netOperatingIncome = adjustedRents - operatingExpenses;
  // Interest Expenses (calculated from loan amount)
  const interestExpenses = annualInterest;
  // DSCR = NOI / Interest (must be ≥ 1.2)
  const dscr = interestExpenses > 0 ? netOperatingIncome / interestExpenses : 0;
  
  // Cash on Cash = Cash Flow / Down Payment × 100
  const cashOnCash = downPayment > 0 ? (cashFlow / downPayment) * 100 : 0;

  // Generate table rows for different down payment amounts
  const rentRows: RentRow[] = useMemo(() => {
    const rows: RentRow[] = [];
    
    for (let dp = MIN_DOWN_PAYMENT; dp <= purchasePrice; dp += DOWN_PAYMENT_INCREMENT) {
      const pctOfPurchase = purchasePrice > 0 ? (dp / purchasePrice) * 100 : 0;
      const loan = purchasePrice - dp;
      const annInt = loan * mortgageRate;
      
      const effAnnualRent = annualRent - vacancyCost;
      const tExpExcludingPI = repairCosts + taxAndInsurance + capex + maintenance;
      const tExp = tExpExcludingPI + annInt;
      const cf = effAnnualRent - tExp;
      
      // DSCR calculation
      const adjRents = effAnnualRent;
      const opEx = adjRents * 0.35;
      const noi = adjRents - opEx;
      const rowDSCR = annInt > 0 ? noi / annInt : 0;
      
      const coc = dp > 0 ? (cf / dp) * 100 : 0;
      
      rows.push({
        downPayment: dp,
        percentOfPurchase: pctOfPurchase,
        monthlyRent,
        unitCount,
        annualRent,
        vacancyCost,
        effectiveAnnualRent: effAnnualRent,
        repairCosts,
        taxAndInsurance,
        capex,
        maintenance,
        annualPI: annInt,
        totalExpenses: tExp,
        cashFlow: cf,
        bankRatio: rowDSCR,
        cashOnCash: coc,
      });
    }
    
    return rows;
  }, [purchasePrice, monthlyRent, unitCount, annualRent, vacancyCost, repairCosts, taxAndInsurance, capex, maintenance, mortgageRate]);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-8">
          <div className="text-gray-500">Loading analysis...</div>
        </CardContent>
      </Card>
    );
  }

  const meetsDSCR = dscr >= 1.2;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-bold flex items-center gap-2">
          <DollarSign className="h-4 w-4" />
          Set Down Payment
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
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <Label htmlFor="downPayment" className="text-xs">Down Payment</Label>
                  <Input
                    id="downPayment"
                    type="number"
                    step={25000}
                    min={25000}
                    max={purchasePrice}
                    value={downPayment}
                    onChange={(e) => setDownPayment(Math.max(25000, parseInt(e.target.value) || 25000))}
                    className="text-sm h-8"
                  />
                </div>
                
                <div>
                  <Label className="text-xs">% of Purchase</Label>
                  <Input
                    type="text"
                    value={`${percentOfPurchase.toFixed(1)}%`}
                    disabled
                    className="text-sm h-8 bg-gray-100"
                  />
                </div>
                
                <div>
                  <Label htmlFor="monthlyRent" className="text-xs">Monthly Rent</Label>
                  <Input
                    id="monthlyRent"
                    type="number"
                    step={50}
                    min={0}
                    value={monthlyRent}
                    onChange={(e) => setMonthlyRent(parseFloat(e.target.value) || 0)}
                    className="text-sm h-8"
                  />
                </div>
                
                <div>
                  <Label htmlFor="repairFinancing" className="text-xs">Repair Financing</Label>
                  <Input
                    id="repairFinancing"
                    type="number"
                    step={1000}
                    min={0}
                    value={repairFinancingAmount}
                    onChange={(e) => setRepairFinancingAmount(parseFloat(e.target.value) || 0)}
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
            <div className={`border-2 rounded-lg p-4 ${meetsDSCR ? 'bg-blue-50 border-blue-600' : 'bg-yellow-50 border-yellow-600'}`}>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm mb-4">
                <div>
                  <div className="text-xs text-gray-600 mb-1">Annual Rent (Gross)</div>
                  <div className="font-semibold text-blue-700">${annualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">Vacancy Loss</div>
                  <div className="font-semibold text-red-700">-${vacancyCost.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  <div className="text-xs text-gray-500">{(vacancyRate * 100).toFixed(1)}% of rent</div>
                </div>
                <div className="col-span-2 md:col-span-1">
                  <div className="text-xs text-gray-600 mb-1">Adjusted Rents</div>
                  <div className="font-bold text-blue-700 text-base">${effectiveAnnualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  <div className="text-xs text-gray-500">After vacancy</div>
                </div>
              </div>
              
              <div className="border-t pt-4 mb-4">
                <div className="text-xs font-semibold text-gray-700 mb-2">Bank DSCR Calculation</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm bg-purple-50 p-3 rounded">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Adjusted Rents</div>
                    <div className="font-semibold text-blue-700">${adjustedRents.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Operating Expenses (35%)</div>
                    <div className="font-semibold text-red-700">-${operatingExpenses.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Net Operating Income</div>
                    <div className="font-bold text-blue-700">${netOperatingIncome.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Annual Interest</div>
                    <div className="font-bold text-orange-700">${interestExpenses.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  </div>
                </div>
              </div>
              
              <div className="border-t pt-4 mb-4">
                <div className="text-xs font-semibold text-gray-700 mb-2">Your Actual Expenses</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Repair Costs</div>
                    <div className="font-semibold text-red-700">${repairCosts.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="text-xs text-gray-500">${repairFinancingAmount.toLocaleString()} × {(locRate * 100).toFixed(1)}%</div>
                  </div>
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
                    <div className="text-xs text-gray-600 mb-1">P&I (Financing)</div>
                    <div className="font-bold text-orange-700">${annualInterest.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                  </div>
                </div>
              </div>
              
              <div className="border-t pt-4 grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-xs text-gray-600 mb-1">Your Cash Flow</div>
                  <div className={`font-bold text-lg ${cashFlow > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                    ${cashFlow.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                  </div>
                  <div className="text-xs text-gray-500">With actual expenses</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">DSCR (Bank Ratio)</div>
                  <div className={`font-bold text-lg ${meetsDSCR ? 'text-blue-700' : 'text-red-700'}`}>
                    {dscr.toFixed(2)} {meetsDSCR ? '✓' : '✗'}
                  </div>
                  <div className="text-xs text-gray-500">NOI ÷ P&I (need ≥ 1.20)</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 mb-1">Cash on Cash</div>
                  <div className={`font-bold text-lg ${cashOnCash > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                    {cashOnCash.toFixed(2)}%
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Table of all scenarios */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-300 bg-gray-100">
                <th className="text-left p-2 font-semibold sticky left-0 bg-gray-100 z-10">Down Payment</th>
                <th className="text-right p-2 font-semibold">% Purchase</th>
                <th className="text-right p-2 font-semibold">Annual Rent</th>
                <th className="text-right p-2 font-semibold">Vacancy</th>
                <th className="text-right p-2 font-semibold bg-blue-50">Adjusted Rent</th>
                <th className="text-right p-2 font-semibold">Repairs</th>
                <th className="text-right p-2 font-semibold">Tax & Ins</th>
                <th className="text-right p-2 font-semibold">CapEx</th>
                <th className="text-right p-2 font-semibold">Maint</th>
                <th className="text-right p-2 font-semibold">Prin. & Int</th>
                <th className="text-right p-2 font-semibold bg-blue-50">Cash Flow</th>
                <th className="text-right p-2 font-semibold">DSCR</th>
                <th className="text-right p-2 font-semibold">CoC %</th>
              </tr>
            </thead>
            <tbody>
              {rentRows.map((row, idx) => {
                const isCurrentDP = row.downPayment === downPayment;
                const rowMeetsDSCR = row.bankRatio >= 1.2;
                const hasPositiveCashFlow = row.cashFlow > 0;
                const meetsAllCriteria = rowMeetsDSCR && hasPositiveCashFlow;
                
                // Find the first row that meets all criteria
                const firstOptimalIdx = rentRows.findIndex(r => r.bankRatio >= 1.2 && r.cashFlow > 0);
                const isOptimal = meetsAllCriteria && idx === firstOptimalIdx;
                
                let rowClass = 'border-b border-gray-200 hover:bg-gray-50';
                if (isCurrentDP) {
                  rowClass = 'bg-blue-50 border-2 border-blue-600 font-semibold';
                } else if (isOptimal) {
                  rowClass = 'border-2 border-blue-600 hover:bg-blue-50';
                }
                
                return (
                  <tr 
                    key={idx} 
                    className={rowClass}
                  >
                    <td className="p-2 sticky left-0 bg-white">
                      <div className="flex items-center gap-1">
                        {isOptimal && !isCurrentDP && (
                          <svg className="h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        <span>${(row.downPayment / 1000).toFixed(0)}k</span>
                        {isCurrentDP && <span className="ml-1 text-xs bg-blue-700 text-white px-1 rounded">CURRENT</span>}
                      </div>
                    </td>
                    <td className="text-right p-2">{row.percentOfPurchase.toFixed(1)}%</td>
                    <td className="text-right p-2">${row.annualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2 text-red-700">-${row.vacancyCost.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2 font-semibold bg-blue-50 text-blue-700">${row.effectiveAnnualRent.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">${row.repairCosts.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">${row.taxAndInsurance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">${row.capex.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">${row.maintenance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className="text-right p-2">${row.annualPI.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                    <td className={`text-right p-2 bg-blue-50 font-medium ${row.cashFlow > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      ${row.cashFlow.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className={`text-right p-2 font-bold ${rowMeetsDSCR ? 'text-blue-700' : 'text-red-700'}`}>
                      {row.bankRatio.toFixed(2)}
                      {rowMeetsDSCR && <span className="ml-1">✓</span>}
                    </td>
                    <td className={`text-right p-2 font-bold ${row.cashOnCash > 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      {row.cashOnCash.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        <div className="mt-4 text-xs text-gray-600 space-y-1 bg-gray-50 p-3 rounded">
          <div><strong>Formulas:</strong></div>
          <div>• Annual Rent (Gross) = Monthly Rent × Unit Count × 12</div>
          <div>• Vacancy Loss = Annual Rent × Vacancy Rate</div>
          <div>• <strong>Adjusted Rents = Annual Rent × (1 - Vacancy Rate)</strong></div>
          <div className="mt-2"><strong>Bank DSCR Calculation:</strong></div>
          <div className="ml-4">• Operating Expenses = 35% × Adjusted Rents (bank's simplified estimate)</div>
          <div className="ml-4">• Net Operating Income (NOI) = Adjusted Rents - Operating Expenses</div>
          <div className="ml-4">• Annual Interest = (Purchase Price - Down Payment) × Mortgage Rate</div>
          <div className="ml-4">• <strong className="text-purple-700">DSCR = NOI ÷ Annual Interest (must be ≥ 1.20)</strong></div>
          <div className="mt-2"><strong>Your Actual Cash Flow:</strong></div>
          <div className="ml-4">• Repair Costs = Repair Financing × LOC Rate</div>
          <div className="ml-4">• Tax & Insurance, CapEx, Maintenance = From scheduled expenses</div>
          <div className="ml-4">• <strong>Cash Flow = Adjusted Rents - (All Actual Expenses + Interest)</strong></div>
          <div className="ml-4">• <strong>Cash on Cash = Cash Flow ÷ Down Payment × 100%</strong></div>
        </div>
      </CardContent>
    </Card>
  );
}

