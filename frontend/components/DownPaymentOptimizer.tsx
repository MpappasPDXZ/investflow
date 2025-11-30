'use client';

import { useState, useMemo, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  current_monthly_rent: number | null;
  is_active: boolean;
}

interface ScheduledExpense {
  id: string;
  property_id: string;
  expense_type: string;
  calculated_annual_cost: number;
  is_active: boolean;
}

interface UserProfile {
  loc_interest_rate: number | null;
  mortgage_interest_rate: number | null;
}

interface Props {
  propertyId: string;
  purchasePrice: number;
  vacancyRate: number;
}

interface DownPaymentScenario {
  downPayment: number;
  downPaymentPercent: number;
  loanAmount: number;
  monthlyPI: number;
  annualPI: number;
  monthlyRent: number;
  annualRent: number;
  vacancyCost: number;
  effectiveAnnualRent: number;
  repairCosts: number;
  taxAndInsurance: number;
  capex: number;
  maintenance: number;
  totalExpenses: number;
  totalExpensesExcludingPI: number;
  cashFlow: number;
  bankRatio: number;
  cashOnCash: number;
}

export default function DownPaymentOptimizer({
  propertyId,
  purchasePrice,
  vacancyRate: propVacancyRate
}: Props) {
  const [loading, setLoading] = useState(true);
  const [inputsExpanded, setInputsExpanded] = useState(true);
  
  // Data from API
  const [units, setUnits] = useState<Unit[]>([]);
  const [scheduledExpenses, setScheduledExpenses] = useState<ScheduledExpense[]>([]);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  
  // User-adjustable parameters
  const [monthlyRentPerUnit, setMonthlyRentPerUnit] = useState(0);
  const [vacancyRate, setVacancyRate] = useState(propVacancyRate || 0.07);
  const [repairFinancing, setRepairFinancing] = useState(0);
  const [mortgageRate, setMortgageRate] = useState(0.07);
  const [locRate, setLocRate] = useState(0.07);
  const [capexOverride, setCapexOverride] = useState<number | null>(null);
  const [maintenanceOverride, setMaintenanceOverride] = useState<number | null>(null);
  
  const DOWN_PAYMENT_INCREMENT = 25000;
  const MIN_DOWN_PAYMENT = 25000;
  const LOAN_TERM_YEARS = 30;
  const BANK_EXPENSE_RATIO = 0.35; // 35% of annual rent for bank underwriting
  
  // Fetch data on mount
  useEffect(() => {
    fetchData();
  }, [propertyId]);
  
  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch units
      const unitsResponse = await apiClient.get<{items: Unit[], total: number}>(
        `/units?property_id=${propertyId}`
      );
      setUnits(unitsResponse.items.filter(u => u.is_active));
      
      // Fetch scheduled expenses
      const expensesResponse = await apiClient.get<{items: ScheduledExpense[], total: number}>(
        `/scheduled-expenses?property_id=${propertyId}`
      );
      setScheduledExpenses(expensesResponse.items.filter(e => e.is_active));
      
      // Fetch user profile
      const profileResponse = await apiClient.get<UserProfile>('/users/me');
      setUserProfile(profileResponse);
      
      // Set defaults from fetched data
      if (unitsResponse.items.length > 0) {
        const avgRent = unitsResponse.items
          .filter(u => u.current_monthly_rent && u.is_active)
          .reduce((sum, u) => sum + (u.current_monthly_rent || 0), 0) / 
          unitsResponse.items.filter(u => u.current_monthly_rent && u.is_active).length;
        setMonthlyRentPerUnit(avgRent || 0);
      }
      
      if (profileResponse.mortgage_interest_rate) {
        setMortgageRate(profileResponse.mortgage_interest_rate);
      }
      if (profileResponse.loc_interest_rate) {
        setLocRate(profileResponse.loc_interest_rate);
      }
      
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  // Calculate monthly P&I payment
  const calculateMonthlyPI = (loanAmount: number, rate: number): number => {
    if (loanAmount === 0) return 0;
    const monthlyRate = rate / 12;
    const numPayments = LOAN_TERM_YEARS * 12;
    const payment = loanAmount * 
      (monthlyRate * Math.pow(1 + monthlyRate, numPayments)) / 
      (Math.pow(1 + monthlyRate, numPayments) - 1);
    return payment;
  };
  
  // Calculate expense categories from scheduled expenses
  const expenseCategories = useMemo(() => {
    const categories = {
      capex: 0,
      maintenance: 0,
      taxAndInsurance: 0,
      other: 0
    };
    
    scheduledExpenses.forEach(exp => {
      const amount = exp.calculated_annual_cost || 0;
      switch (exp.expense_type) {
        case 'capex':
          categories.capex += amount;
          break;
        case 'maintenance':
        case 'vacancy':
          categories.maintenance += amount;
          break;
        case 'pti':
          categories.taxAndInsurance += amount;
          break;
        default:
          categories.other += amount;
      }
    });
    
    return categories;
  }, [scheduledExpenses]);
  
  // Calculate scenarios
  const scenarios: DownPaymentScenario[] = useMemo(() => {
    const scenarios: DownPaymentScenario[] = [];
    
    // Unit count
    const unitCount = Math.max(1, units.length);
    
    // Monthly rent per unit (user input)
    const monthlyRent = monthlyRentPerUnit;
    
    // Annual rent before vacancy
    const grossAnnualRent = monthlyRent * unitCount * 12;
    
    // Vacancy cost
    const vacancyCost = grossAnnualRent * vacancyRate;
    
    // Effective annual rent (after vacancy)
    const effectiveAnnualRent = grossAnnualRent - vacancyCost;
    
    // Repair costs (financing amount × LOC rate)
    const repairCosts = repairFinancing * locRate;
    
    // Tax and Insurance from scheduled expenses
    const taxAndInsurance = expenseCategories.taxAndInsurance;
    
    // CapEx - default to scheduled, fallback to 8000
    const capex = capexOverride !== null ? capexOverride : 
                  (expenseCategories.capex > 0 ? expenseCategories.capex : 8000);
    
    // Maintenance - default to scheduled, fallback to 3000  
    const maintenance = maintenanceOverride !== null ? maintenanceOverride :
                        (expenseCategories.maintenance > 0 ? expenseCategories.maintenance : 3000);
    
    // Generate scenarios
    for (let downPayment = MIN_DOWN_PAYMENT; downPayment <= purchasePrice; downPayment += DOWN_PAYMENT_INCREMENT) {
      const downPaymentPercent = (downPayment / purchasePrice) * 100;
      
      // Skip if less than 10% down
      if (downPaymentPercent < 10) continue;
      
      const loanAmount = purchasePrice - downPayment;
      const monthlyPI = calculateMonthlyPI(loanAmount, mortgageRate);
      const annualPI = monthlyPI * 12;
      
      // Total expenses excluding P&I for bank ratio
      const totalExpensesExcludingPI = repairCosts + taxAndInsurance + capex + maintenance + vacancyCost;
      
      // Total expenses including P&I
      const totalExpenses = totalExpensesExcludingPI + annualPI;
      
      // Cash flow = Effective Annual Rent - Total Expenses
      const cashFlow = effectiveAnnualRent - totalExpenses;
      
      // Bank Ratio = (Annual Rent - Vacancy) / ((Annual Rent × 35%) + P&I)
      const bankRatioDenominator = (grossAnnualRent * BANK_EXPENSE_RATIO) + annualPI;
      const bankRatio = bankRatioDenominator > 0 ? effectiveAnnualRent / bankRatioDenominator : 0;
      
      // Cash on Cash = Cash Flow / Down Payment
      const cashOnCash = downPayment > 0 ? (cashFlow / downPayment) * 100 : 0;
      
      scenarios.push({
        downPayment,
        downPaymentPercent,
        loanAmount,
        monthlyPI,
        annualPI,
        monthlyRent,
        annualRent: grossAnnualRent,
        vacancyCost,
        effectiveAnnualRent,
        repairCosts,
        taxAndInsurance,
        capex,
        maintenance,
        totalExpenses,
        totalExpensesExcludingPI,
        cashFlow,
        bankRatio,
        cashOnCash
      });
    }
    
    return scenarios;
  }, [
    units,
    monthlyRentPerUnit,
    vacancyRate,
    repairFinancing,
    mortgageRate,
    locRate,
    purchasePrice,
    expenseCategories,
    capexOverride,
    maintenanceOverride
  ]);
  
  // Find best scenarios
  const bestCoCScenario = scenarios.length > 0 ? scenarios.reduce((best, current) => 
    current.cashOnCash > best.cashOnCash ? current : best
  ) : null;
  
  const qualifyingScenarios = scenarios.filter(s => s.bankRatio >= 1.2);
  const bestQualifyingScenario = qualifyingScenarios.length > 0 ?
    qualifyingScenarios.reduce((best, current) => 
      current.cashOnCash > best.cashOnCash ? current : best
    ) : null;
  
  const unitCount = Math.max(1, units.length);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-500">Loading data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Collapsible Input Section */}
      <div className="bg-white border rounded-lg">
        <button
          onClick={() => setInputsExpanded(!inputsExpanded)}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
        >
          <h3 className="font-semibold text-lg">Adjust Parameters</h3>
          {inputsExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-500" />
          )}
        </button>
        
        {inputsExpanded && (
          <div className="p-4 border-t bg-gray-50">
            <div className="grid grid-cols-4 gap-4">
              <div>
                <Label className="text-sm">Monthly Rent per Unit</Label>
                <Input
                  type="number"
                  step="50"
                  value={monthlyRentPerUnit}
                  onChange={(e) => setMonthlyRentPerUnit(parseFloat(e.target.value) || 0)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">Units: {unitCount}</p>
              </div>
              
              <div>
                <Label className="text-sm">Vacancy Rate</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={vacancyRate}
                  onChange={(e) => setVacancyRate(parseFloat(e.target.value) || 0)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">e.g., 0.07 for 7%</p>
              </div>
              
              <div>
                <Label className="text-sm">Repair Financing</Label>
                <Input
                  type="number"
                  step="1000"
                  value={repairFinancing}
                  onChange={(e) => setRepairFinancing(parseFloat(e.target.value) || 0)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">LOC amount</p>
              </div>
              
              <div>
                <Label className="text-sm">Mortgage Rate</Label>
                <Input
                  type="number"
                  step="0.001"
                  value={mortgageRate}
                  onChange={(e) => setMortgageRate(parseFloat(e.target.value) || 0.07)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">e.g., 0.07 for 7%</p>
              </div>
              
              <div>
                <Label className="text-sm">LOC Rate</Label>
                <Input
                  type="number"
                  step="0.001"
                  value={locRate}
                  onChange={(e) => setLocRate(parseFloat(e.target.value) || 0.07)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">Interest rate</p>
              </div>
              
              <div>
                <Label className="text-sm">CapEx (optional)</Label>
                <Input
                  type="number"
                  step="100"
                  placeholder={expenseCategories.capex > 0 ? expenseCategories.capex.toFixed(0) : "8000"}
                  value={capexOverride ?? ''}
                  onChange={(e) => setCapexOverride(e.target.value ? parseFloat(e.target.value) : null)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">Default: {expenseCategories.capex > 0 ? expenseCategories.capex.toFixed(0) : "8000"}</p>
              </div>
              
              <div>
                <Label className="text-sm">Maintenance (optional)</Label>
                <Input
                  type="number"
                  step="100"
                  placeholder={expenseCategories.maintenance > 0 ? expenseCategories.maintenance.toFixed(0) : "3000"}
                  value={maintenanceOverride ?? ''}
                  onChange={(e) => setMaintenanceOverride(e.target.value ? parseFloat(e.target.value) : null)}
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">Default: {expenseCategories.maintenance > 0 ? expenseCategories.maintenance.toFixed(0) : "3000"}</p>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Best Scenarios Summary */}
      {bestQualifyingScenario && (
        <div className="bg-green-50 border-2 border-green-600 rounded-lg p-4">
          <h3 className="font-bold text-green-900 mb-2">✅ Best Bank-Qualifying Scenario</h3>
          <p className="text-sm">
            <strong>${bestQualifyingScenario.downPayment.toLocaleString()}</strong> down ({bestQualifyingScenario.downPaymentPercent.toFixed(1)}%) • 
            Bank Ratio: <strong>{bestQualifyingScenario.bankRatio.toFixed(2)}</strong> • 
            CoC: <strong>{bestQualifyingScenario.cashOnCash.toFixed(2)}%</strong>
          </p>
        </div>
      )}
      
      {/* Scenarios Table */}
      <div className="bg-white border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-gray-100 border-b-2 border-gray-300">
                <th className="p-2 text-left whitespace-nowrap sticky left-0 bg-gray-100 z-10">Down Payment</th>
                <th className="p-2 text-left whitespace-nowrap">% of Purchase</th>
                <th className="p-2 text-right whitespace-nowrap">Monthly Rent</th>
                <th className="p-2 text-right whitespace-nowrap">Unit Count</th>
                <th className="p-2 text-right whitespace-nowrap">Annual Rent</th>
                <th className="p-2 text-right whitespace-nowrap bg-red-50">Vacancy</th>
                <th className="p-2 text-right whitespace-nowrap bg-red-50">Repairs</th>
                <th className="p-2 text-right whitespace-nowrap bg-red-50">Tax & Ins</th>
                <th className="p-2 text-right whitespace-nowrap bg-red-50">CapEx</th>
                <th className="p-2 text-right whitespace-nowrap bg-red-50">Maint</th>
                <th className="p-2 text-right whitespace-nowrap bg-yellow-50">Annual P&I</th>
                <th className="p-2 text-right whitespace-nowrap bg-blue-50">Cash Flow</th>
                <th className="p-2 text-right whitespace-nowrap bg-purple-100 font-bold">Bank Ratio</th>
                <th className="p-2 text-right whitespace-nowrap bg-green-100 font-bold">CoC %</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((scenario, idx) => {
                const isBestCoC = bestCoCScenario && scenario.downPayment === bestCoCScenario.downPayment;
                const isBestQualifying = bestQualifyingScenario && scenario.downPayment === bestQualifyingScenario.downPayment;
                const meetsBank = scenario.bankRatio >= 1.2;
                
                let rowClass = 'border-b hover:bg-gray-50';
                if (isBestQualifying) {
                  rowClass = 'bg-green-100 border-2 border-green-600 font-semibold';
                } else if (isBestCoC) {
                  rowClass = 'bg-blue-100 border-2 border-blue-500';
                }
                
                return (
                  <tr key={idx} className={rowClass}>
                    <td className="p-2 sticky left-0 bg-inherit">
                      ${scenario.downPayment.toLocaleString()}
                      {isBestQualifying && <span className="ml-2 text-xs bg-green-700 text-white px-1 rounded">BEST</span>}
                    </td>
                    <td className="p-2">{scenario.downPaymentPercent.toFixed(1)}%</td>
                    <td className="p-2 text-right">${scenario.monthlyRent.toLocaleString()}</td>
                    <td className="p-2 text-right">{unitCount}</td>
                    <td className="p-2 text-right">${scenario.annualRent.toLocaleString()}</td>
                    <td className="p-2 text-right bg-red-50 text-red-700">${scenario.vacancyCost.toLocaleString()}</td>
                    <td className="p-2 text-right bg-red-50 text-red-700">${scenario.repairCosts.toLocaleString()}</td>
                    <td className="p-2 text-right bg-red-50 text-red-700">${scenario.taxAndInsurance.toLocaleString()}</td>
                    <td className="p-2 text-right bg-red-50 text-red-700">${scenario.capex.toLocaleString()}</td>
                    <td className="p-2 text-right bg-red-50 text-red-700">${scenario.maintenance.toLocaleString()}</td>
                    <td className="p-2 text-right bg-yellow-50 text-orange-700">${scenario.annualPI.toLocaleString()}</td>
                    <td className={`p-2 text-right bg-blue-50 font-medium ${scenario.cashFlow > 0 ? 'text-green-700' : 'text-red-700'}`}>
                      ${scenario.cashFlow.toLocaleString()}
                    </td>
                    <td className={`p-2 text-right bg-purple-100 font-bold ${meetsBank ? 'text-green-700' : 'text-red-700'}`}>
                      {scenario.bankRatio.toFixed(2)}
                      {meetsBank && <span className="ml-1">✓</span>}
                    </td>
                    <td className={`p-2 text-right bg-green-100 font-bold ${scenario.cashOnCash > 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {scenario.cashOnCash.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Legend */}
      <div className="bg-gray-50 border rounded-lg p-3 text-xs space-y-1">
        <div><strong>Bank Ratio Formula:</strong> (Annual Rent - Vacancy) ÷ ((Annual Rent × 35%) + P&I) ≥ 1.2</div>
        <div><strong>Cash on Cash:</strong> (Cash Flow ÷ Down Payment) × 100</div>
        <div><strong>Cash Flow:</strong> Effective Annual Rent - Total Expenses (including P&I)</div>
        <div className="text-purple-700 font-medium">✓ = Meets bank requirement (ratio ≥ 1.2)</div>
      </div>
    </div>
  );
}
