'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, Edit2, Trash2, Check, X, ChevronDown, ChevronRight, DollarSign, TrendingUp, Zap } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

// Interface matches EXACT backend field order: ACTUAL table schema
// id, property_id, expense_type, item_name, purchase_price, depreciation_rate,
// count, annual_cost, principal, interest_rate, notes, created_at, updated_at, is_active
interface ScheduledExpense {
  id: string;
  property_id: string;
  expense_type: string;
  item_name: string;
  purchase_price?: number;
  depreciation_rate?: number;
  count?: number;
  annual_cost?: number;
  principal?: number;
  interest_rate?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  calculated_annual_cost?: number; // Computed field (not in table)
}

// Interface matches EXACT backend field order: ACTUAL table schema
// id, property_id, revenue_type, item_name, annual_amount, appreciation_rate,
// property_value, value_added_amount, notes, created_at, updated_at, is_active
interface ScheduledRevenue {
  id: string;
  property_id: string;
  revenue_type: string;
  item_name: string;
  annual_amount?: number;
  appreciation_rate?: number;
  property_value?: number;
  value_added_amount?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  calculated_annual_amount?: number; // Computed field (not in table)
}

interface Props {
  propertyId: string;
  purchasePrice: number;
}

// Common items lookup by expense type
const expenseItemExamples = {
  capex: [
    'Refrigerator', 'Dishwasher', 'Washer/Dryer', 'Stove/Oven', 'Microwave',
    'Water Heater', 'HVAC System', 'Furnace', 'Air Conditioner',
    'Roof', 'Windows', 'Siding', 'Flooring', 'Carpet',
    'Paint (Interior)', 'Paint (Exterior)', 'Kitchen Cabinets',
    'Garage Door', 'Fence', 'Deck'
  ],
  maintenance: [
    'Lawn Care & Landscaping', 'Snow Removal', 'Sprinkler System Maintenance',
    'HVAC Maintenance', 'Gutter Cleaning', 'Pest Control',
    'Pool Maintenance', 'Septic System Pumping', 'Chimney Cleaning',
    'Pressure Washing', 'Window Cleaning', 'Tree Trimming',
    'Roof Inspection', 'Driveway Sealing', 'Fence Repair',
    'Appliance Maintenance', 'Water Heater Maintenance', 
    'Smoke Detector Batteries', 'General Repairs', 'Painting Touch-ups'
  ],
  pti: [
    'Property Tax', 'Homeowners Insurance', 'Flood Insurance',
    'Landlord Insurance', 'Umbrella Insurance', 'HOA Fees'
  ],
  pi: [
    'Mortgage', 'Line of Credit', 'Home Equity Loan', 'Construction Loan'
  ]
};

// Helper to get placeholder text based on expense type
const getItemNamePlaceholder = (expenseType: string): string => {
  const examples = expenseItemExamples[expenseType as keyof typeof expenseItemExamples] || [];
  if (examples.length >= 3) {
    return `e.g., ${examples.slice(0, 3).join(', ')}`;
  }
  return 'Enter item name';
};

export default function ScheduledFinancialsTab({ propertyId, purchasePrice }: Props) {
  // State for expenses
  const [expenses, setExpenses] = useState<ScheduledExpense[]>([]);
  const [loadingExpenses, setLoadingExpenses] = useState(false);
  const [showAddExpense, setShowAddExpense] = useState(false);
  const [editingExpenseId, setEditingExpenseId] = useState<string | null>(null);
  const [collapsedExpenseSections, setCollapsedExpenseSections] = useState<Set<string>>(
    new Set(['capex', 'maintenance', 'vacancy', 'pti', 'pi'])
  );
  const [expenseForm, setExpenseForm] = useState({
    expense_type: '',
    item_name: '',
    purchase_price: '',
    depreciation_rate: '',
    count: '1',
    annual_cost: '',
    principal: '',
    interest_rate: '',
  });

  // State for revenue
  const [revenues, setRevenues] = useState<ScheduledRevenue[]>([]);
  const [loadingRevenues, setLoadingRevenues] = useState(false);
  const [showAddRevenue, setShowAddRevenue] = useState(false);
  const [editingRevenueId, setEditingRevenueId] = useState<string | null>(null);
  const [revenueForm, setRevenueForm] = useState({
    revenue_type: '',
    item_name: '',
    annual_amount: '',
    appreciation_rate: '0.025',
    property_value: purchasePrice.toString(),
    value_added_amount: '',
  });

  // State for template
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [templatePreview, setTemplatePreview] = useState<{
    expenses: any[];
    revenue: any[];
    scaling_factors: any;
  } | null>(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [selectedExpenses, setSelectedExpenses] = useState<Set<number>>(new Set());
  const [selectedRevenue, setSelectedRevenue] = useState<Set<number>>(new Set());

  // Fetch expenses and revenues on mount
  useEffect(() => {
    fetchExpenses();
    fetchRevenues();
  }, [propertyId]);

  const fetchExpenses = async () => {
    try {
      setLoadingExpenses(true);
      const response = await apiClient.get<{ items: ScheduledExpense[]; total: number }>(
        `/scheduled-expenses?property_id=${propertyId}`
      );
      setExpenses(response.items);
    } catch (err) {
      console.error('❌ [EXPENSES] Error:', err);
    } finally {
      setLoadingExpenses(false);
    }
  };

  const fetchRevenues = async () => {
    try {
      setLoadingRevenues(true);
      const response = await apiClient.get<{ items: ScheduledRevenue[]; total: number }>(
        `/scheduled-revenue?property_id=${propertyId}`
      );
      setRevenues(response.items);
    } catch (err) {
      console.error('❌ [REVENUE] Error:', err);
    } finally {
      setLoadingRevenues(false);
    }
  };

  // Expense handlers
  const handleAddExpense = async () => {
    try {
      // VALIDATION: Required fields
      if (!expenseForm.expense_type) {
        alert('Please select an expense type');
        return;
      }
      if (!expenseForm.item_name || expenseForm.item_name.trim() === '') {
        alert('Please enter an item name');
        return;
      }
      
      // Build payload in EXACT backend field order (matching ACTUAL table schema)
      // id, property_id, expense_type, item_name, purchase_price, depreciation_rate,
      // count, annual_cost, principal, interest_rate, notes, created_at, updated_at, is_active
      const payload: any = {
        property_id: propertyId, // REQUIRED
        expense_type: expenseForm.expense_type, // REQUIRED
        item_name: expenseForm.item_name.trim(), // REQUIRED
      };

      if (expenseForm.expense_type === 'capex') {
        payload.purchase_price = parseFloat(expenseForm.purchase_price);
        payload.depreciation_rate = parseFloat(expenseForm.depreciation_rate);
        payload.count = parseInt(expenseForm.count);
      } else if (expenseForm.expense_type === 'pti' || expenseForm.expense_type === 'maintenance') {
        payload.annual_cost = parseFloat(expenseForm.annual_cost);
      } else if (expenseForm.expense_type === 'pi') {
        payload.principal = parseFloat(expenseForm.principal);
        payload.interest_rate = parseFloat(expenseForm.interest_rate);
      }

      // Build ordered payload respecting ACTUAL backend table schema order
      // id, property_id, expense_type, item_name, purchase_price, depreciation_rate,
      // count, annual_cost, principal, interest_rate, notes, created_at, updated_at, is_active
      const BACKEND_FIELD_ORDER = [
        "id", "property_id", "expense_type", "item_name", "purchase_price", "depreciation_rate",
        "count", "annual_cost", "principal", "interest_rate", "notes",
        "created_at", "updated_at", "is_active"
      ];
      
      const orderedPayload: any = {};
      for (const field of BACKEND_FIELD_ORDER) {
        if (field in payload) {
          orderedPayload[field] = payload[field];
        }
      }
      // Add any extra fields that might not be in the order list
      for (const key of Object.keys(payload)) {
        if (!BACKEND_FIELD_ORDER.includes(key) && !orderedPayload.hasOwnProperty(key)) {
          orderedPayload[key] = payload[key];
        }
      }

      console.log('📝 [EXPENSE] Creating expense with ordered payload:', orderedPayload);
      console.log('📝 [EXPENSE] Payload field order:', Object.keys(orderedPayload));
      const isPIExpense = expenseForm.expense_type === 'pi';
      await apiClient.post('/scheduled-expenses', orderedPayload);
      resetExpenseForm();
      await fetchExpenses();
      
      // If P&I expense, fetch revenues to show principal paydown
      if (isPIExpense) {
        // Wait a moment for backend to create the revenue, then fetch
        setTimeout(async () => {
          try {
            // Fetch revenues directly to get the latest data
            const revenuesResponse = await apiClient.get<{ items: ScheduledRevenue[]; total: number }>(
              `/scheduled-revenue?property_id=${propertyId}`
            );
            // Also update state
            await fetchRevenues();
            
            // Find the principal paydown revenue that was automatically created
            const principalPaydown = revenuesResponse.items.find(
              r => r.revenue_type === 'principal_paydown' && r.is_active
            );
            if (principalPaydown && principalPaydown.annual_amount) {
              const principalPaydownFormatted = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              }).format(principalPaydown.annual_amount);
              alert(`✅ P&I expense created!\n\nPrincipal paydown (automatically added to scheduled revenue): ${principalPaydownFormatted}/year`);
            }
          } catch (err) {
            console.error('❌ [REVENUE] Error fetching principal paydown:', err);
          }
        }, 500);
      }
    } catch (err) {
      console.error('❌ [EXPENSE] Error creating:', err);
      alert(`Failed to create expense: ${(err as Error).message}`);
    }
  };

  const handleEditExpense = async (expenseId: string) => {
    try {
      const payload: any = {
        item_name: expenseForm.item_name,
      };

      const expense = expenses.find(e => e.id === expenseId);
      const isPIExpense = expense?.expense_type === 'pi';
      if (expense?.expense_type === 'capex') {
        payload.purchase_price = parseFloat(expenseForm.purchase_price);
        payload.depreciation_rate = parseFloat(expenseForm.depreciation_rate);
        payload.count = parseInt(expenseForm.count);
      } else if (expense?.expense_type === 'pti' || expense?.expense_type === 'maintenance') {
        payload.annual_cost = parseFloat(expenseForm.annual_cost);
      } else if (expense?.expense_type === 'pi') {
        payload.principal = parseFloat(expenseForm.principal);
        payload.interest_rate = parseFloat(expenseForm.interest_rate);
      }

      await apiClient.put(`/scheduled-expenses/${expenseId}`, payload);
      resetExpenseForm();
      await fetchExpenses();
      
      // If P&I expense was updated, fetch revenues to show principal paydown
      if (isPIExpense) {
        // Wait a moment for backend to update the revenue, then fetch
        setTimeout(async () => {
          try {
            // Fetch revenues directly to get the latest data
            const revenuesResponse = await apiClient.get<{ items: ScheduledRevenue[]; total: number }>(
              `/scheduled-revenue?property_id=${propertyId}`
            );
            // Also update state
            await fetchRevenues();
            
            // Find the principal paydown revenue that was automatically updated
            const principalPaydown = revenuesResponse.items.find(
              r => r.revenue_type === 'principal_paydown' && r.is_active
            );
            if (principalPaydown && principalPaydown.annual_amount) {
              const principalPaydownFormatted = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              }).format(principalPaydown.annual_amount);
              alert(`✅ P&I expense updated!\n\nPrincipal paydown (automatically updated in scheduled revenue): ${principalPaydownFormatted}/year`);
            }
          } catch (err) {
            console.error('❌ [REVENUE] Error fetching principal paydown:', err);
          }
        }, 500);
      }
    } catch (err) {
      console.error('❌ [EXPENSE] Error updating:', err);
      alert(`Failed to update expense: ${(err as Error).message}`);
    }
  };

  const handleDeleteExpense = async (expenseId: string, itemName: string) => {
    if (!confirm(`Delete ${itemName}?`)) return;
    try {
      await apiClient.delete(`/scheduled-expenses/${expenseId}`);
      fetchExpenses();
    } catch (err) {
      console.error('❌ [EXPENSE] Error deleting:', err);
      alert(`Failed to delete expense: ${(err as Error).message}`);
    }
  };

  const startEditExpense = (expense: ScheduledExpense) => {
    setEditingExpenseId(expense.id);
    setExpenseForm({
      expense_type: expense.expense_type,
      item_name: expense.item_name,
      purchase_price: expense.purchase_price?.toString() || '',
      depreciation_rate: expense.depreciation_rate?.toString() || '',
      count: expense.count?.toString() || '1',
      annual_cost: expense.annual_cost?.toString() || '',
      principal: expense.principal?.toString() || '',
      interest_rate: expense.interest_rate?.toString() || '',
    });
    setShowAddExpense(false);
    setShowAddRevenue(false);
  };

  const resetExpenseForm = () => {
    setExpenseForm({
      expense_type: '',
      item_name: '',
      purchase_price: '',
      depreciation_rate: '',
      count: '1',
      annual_cost: '',
      principal: '',
      interest_rate: '',
    });
    setEditingExpenseId(null);
    setShowAddExpense(false);
  };

  // Revenue handlers
  const handleAddRevenue = async () => {
    try {
      // Build payload in EXACT backend field order (matching SCHEDULED_REVENUE_FIELD_ORDER)
      // id, property_id, revenue_type, item_name, notes, is_active,
      // annual_amount, appreciation_rate, property_value, value_added_amount, created_at, updated_at
      const payload: any = {
        property_id: propertyId,
        revenue_type: revenueForm.revenue_type,
        item_name: revenueForm.item_name,
      };

      if (revenueForm.revenue_type === 'principal_paydown') {
        payload.annual_amount = parseFloat(revenueForm.annual_amount);
      } else if (revenueForm.revenue_type === 'appreciation') {
        payload.appreciation_rate = parseFloat(revenueForm.appreciation_rate);
        payload.property_value = parseFloat(revenueForm.property_value);
      } else if (revenueForm.revenue_type === 'value_added') {
        payload.value_added_amount = parseFloat(revenueForm.value_added_amount);
      }

      // Build ordered payload respecting ACTUAL backend table schema order
      // id, property_id, revenue_type, item_name, annual_amount, appreciation_rate,
      // property_value, value_added_amount, notes, created_at, updated_at, is_active
      const BACKEND_FIELD_ORDER = [
        "id", "property_id", "revenue_type", "item_name", "annual_amount", "appreciation_rate",
        "property_value", "value_added_amount", "notes",
        "created_at", "updated_at", "is_active"
      ];
      
      const orderedPayload: any = {};
      for (const field of BACKEND_FIELD_ORDER) {
        if (field in payload) {
          orderedPayload[field] = payload[field];
        }
      }
      // Add any extra fields that might not be in the order list
      for (const key of Object.keys(payload)) {
        if (!BACKEND_FIELD_ORDER.includes(key) && !orderedPayload.hasOwnProperty(key)) {
          orderedPayload[key] = payload[key];
        }
      }

      console.log('📝 [REVENUE] Creating revenue with ordered payload:', orderedPayload);
      console.log('📝 [REVENUE] Payload field order:', Object.keys(orderedPayload));
      await apiClient.post('/scheduled-revenue', orderedPayload);
      resetRevenueForm();
      fetchRevenues();
    } catch (err) {
      console.error('❌ [REVENUE] Error creating:', err);
      alert(`Failed to create revenue: ${(err as Error).message}`);
    }
  };

  const handleEditRevenue = async (revenueId: string) => {
    try {
      const payload: any = {
        item_name: revenueForm.item_name,
      };

      const revenue = revenues.find(r => r.id === revenueId);
      if (revenue?.revenue_type === 'principal_paydown') {
        payload.annual_amount = parseFloat(revenueForm.annual_amount);
      } else if (revenue?.revenue_type === 'appreciation') {
        payload.appreciation_rate = parseFloat(revenueForm.appreciation_rate);
        payload.property_value = parseFloat(revenueForm.property_value);
      } else if (revenue?.revenue_type === 'value_added') {
        payload.value_added_amount = parseFloat(revenueForm.value_added_amount);
      }

      await apiClient.put(`/scheduled-revenue/${revenueId}`, payload);
      resetRevenueForm();
      fetchRevenues();
    } catch (err) {
      console.error('❌ [REVENUE] Error updating:', err);
      alert(`Failed to update revenue: ${(err as Error).message}`);
    }
  };

  const handleDeleteRevenue = async (revenueId: string, itemName: string) => {
    if (!confirm(`Delete ${itemName}?`)) return;
    try {
      await apiClient.delete(`/scheduled-revenue/${revenueId}`);
      fetchRevenues();
    } catch (err) {
      console.error('❌ [REVENUE] Error deleting:', err);
      alert(`Failed to delete revenue: ${(err as Error).message}`);
    }
  };

  const startEditRevenue = (revenue: ScheduledRevenue) => {
    setEditingRevenueId(revenue.id);
    setRevenueForm({
      revenue_type: revenue.revenue_type,
      item_name: revenue.item_name,
      annual_amount: revenue.annual_amount?.toString() || '',
      appreciation_rate: revenue.appreciation_rate?.toString() || '0.025',
      property_value: revenue.property_value?.toString() || purchasePrice.toString(),
      value_added_amount: revenue.value_added_amount?.toString() || '',
    });
    setShowAddExpense(false);
    setShowAddRevenue(false);
  };

  const resetRevenueForm = () => {
    setRevenueForm({
      revenue_type: '',
      item_name: '',
      annual_amount: '',
      appreciation_rate: '0.025',
      property_value: purchasePrice.toString(),
      value_added_amount: '',
    });
    setEditingRevenueId(null);
    setShowAddRevenue(false);
  };

  // Calculate totals
  const totalExpenses = expenses.reduce((sum, exp) => sum + (exp.calculated_annual_cost || 0), 0);
  const totalRevenue = revenues.reduce((sum, rev) => sum + (rev.calculated_annual_amount || 0), 0);

  // Toggle collapse state
  const toggleExpenseSection = (type: string) => {
    setCollapsedExpenseSections(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const loadTemplatePreview = async () => {
    try {
      setLoadingTemplate(true);
      // Get the template preview (we'll create a new endpoint for this)
      const response = await apiClient.get<{
        expenses: any[];
        revenue: any[];
        scaling_factors: any;
      }>(`/scheduled-financials/preview-template/${propertyId}`);
      
      setTemplatePreview(response);
      // Select all items by default
      setSelectedExpenses(new Set(response.expenses.map((_, idx) => idx)));
      setSelectedRevenue(new Set(response.revenue.map((_, idx) => idx)));
    } catch (err) {
      console.error('❌ [TEMPLATE] Error loading preview:', err);
      alert(`Failed to load template preview: ${(err as Error).message}`);
    } finally {
      setLoadingTemplate(false);
    }
  };

  const handleOpenTemplateModal = () => {
    setShowTemplateModal(true);
    loadTemplatePreview();
  };

  const toggleExpense = (index: number) => {
    setSelectedExpenses(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const toggleRevenue = (index: number) => {
    setSelectedRevenue(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleApplyTemplate = async () => {
    if (!templatePreview) return;

    try {
      setApplyingTemplate(true);
      
      // Filter selected items
      const selectedExpenseItems = templatePreview.expenses.filter((_, idx) => selectedExpenses.has(idx));
      const selectedRevenueItems = templatePreview.revenue.filter((_, idx) => selectedRevenue.has(idx));
      
      // Apply template with selected items
      const response = await apiClient.post<{
        message: string;
        property_id: string;
        expenses_created: number;
        revenue_created: number;
      }>(`/scheduled-financials/apply-template/${propertyId}`, {
        expenses: selectedExpenseItems,
        revenue: selectedRevenueItems
      });
      
      console.log('✅ [TEMPLATE] Applied:', response);
      alert(`Template applied successfully!\n${response.expenses_created} expenses and ${response.revenue_created} revenue items added.`);
      
      // Refresh data
      fetchExpenses();
      fetchRevenues();
      
      // Close modal and reset
      setShowTemplateModal(false);
      setTemplatePreview(null);
    } catch (err) {
      console.error('❌ [TEMPLATE] Error:', err);
      alert(`Failed to apply template: ${(err as Error).message}`);
    } finally {
      setApplyingTemplate(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Auto Apply */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-base font-bold text-gray-900">Scheduled Financials</h2>
          <p className="text-xs text-gray-500 mt-0.5">Manage recurring expenses and revenue projections</p>
        </div>
        <Button
          variant="outline"
          onClick={handleOpenTemplateModal}
          className="h-8 text-xs border-blue-600 text-blue-600 hover:bg-blue-50"
        >
          <Zap className="h-3 w-3 mr-1.5" />
          Auto-Apply Template
        </Button>
      </div>

      {/* EXPENSES SECTION */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              Scheduled Expenses
            </CardTitle>
            {!showAddExpense && !editingExpenseId && !editingRevenueId && (
              <Button
                onClick={() => {
                  setShowAddExpense(true);
                  setShowAddRevenue(false);
                }}
                size="sm"
                className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
              >
                <Plus className="h-3 w-3 mr-1" />
                Add Expense
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loadingExpenses ? (
            <div className="text-gray-500 py-4">Loading expenses...</div>
          ) : (
            <div className="space-y-4">
              {/* Add Expense Form */}
              {showAddExpense && (
                <Card className="bg-blue-50 border-blue-200">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Add New Expense</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <Label>Expense Type *</Label>
                        <Select
                          value={expenseForm.expense_type}
                          onValueChange={(value) => setExpenseForm({ ...expenseForm, expense_type: value })}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="capex">Capital Expense (CapEx)</SelectItem>
                            <SelectItem value="maintenance">Maintenance</SelectItem>
                            <SelectItem value="pti">Property Tax & Insurance (PTI)</SelectItem>
                            <SelectItem value="pi">Principal & Interest (P&I)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label>Item Name *</Label>
                        <Input
                          value={expenseForm.item_name}
                          onChange={(e) => setExpenseForm({ ...expenseForm, item_name: e.target.value })}
                          placeholder={getItemNamePlaceholder(expenseForm.expense_type)}
                        />
                        {expenseForm.expense_type && (
                          <p className="text-xs text-gray-500 mt-1">
                            Common: {expenseItemExamples[expenseForm.expense_type as keyof typeof expenseItemExamples]?.slice(0, 5).join(', ')}
                          </p>
                        )}
                      </div>

                      {/* CapEx Fields */}
                      {expenseForm.expense_type === 'capex' && (
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <Label>Purchase Price</Label>
                            <Input
                              type="number"
                              step="0.01"
                              value={expenseForm.purchase_price}
                              onChange={(e) => setExpenseForm({ ...expenseForm, purchase_price: e.target.value })}
                            />
                          </div>
                          <div>
                            <Label>Depreciation/Year (decimal)</Label>
                            <Input
                              type="number"
                              step="0.001"
                              max="0.999"
                              value={expenseForm.depreciation_rate}
                              onChange={(e) => setExpenseForm({ ...expenseForm, depreciation_rate: e.target.value })}
                              placeholder="e.g., 0.075"
                            />
                          </div>
                          <div>
                            <Label>Count</Label>
                            <Input
                              type="number"
                              min="1"
                              value={expenseForm.count}
                              onChange={(e) => setExpenseForm({ ...expenseForm, count: e.target.value })}
                            />
                          </div>
                        </div>
                      )}

                      {/* PTI or Maintenance Fields */}
                      {(expenseForm.expense_type === 'pti' || expenseForm.expense_type === 'maintenance') && (
                        <div>
                          <Label>Annual Cost</Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={expenseForm.annual_cost}
                            onChange={(e) => setExpenseForm({ ...expenseForm, annual_cost: e.target.value })}
                          />
                        </div>
                      )}

                      {/* P&I Fields */}
                      {expenseForm.expense_type === 'pi' && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label>Principal</Label>
                            <Input
                              type="number"
                              step="0.01"
                              value={expenseForm.principal}
                              onChange={(e) => setExpenseForm({ ...expenseForm, principal: e.target.value })}
                            />
                          </div>
                          <div>
                            <Label>Interest Rate (decimal)</Label>
                            <Input
                              type="number"
                              step="0.001"
                              max="0.999"
                              value={expenseForm.interest_rate}
                              onChange={(e) => setExpenseForm({ ...expenseForm, interest_rate: e.target.value })}
                              placeholder="e.g., 0.065"
                            />
                          </div>
                        </div>
                      )}

                      <div className="flex gap-2 pt-2">
                        <Button
                          onClick={handleAddExpense}
                          disabled={!expenseForm.expense_type || !expenseForm.item_name}
                          size="sm"
                          className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
                        >
                          <Check className="h-3 w-3 mr-1" />
                          Save
                        </Button>
                        <Button
                          variant="outline"
                          onClick={resetExpenseForm}
                          size="sm"
                          className="h-8 text-xs"
                        >
                          <X className="h-3 w-3 mr-1" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Expenses List */}
              {expenses.length === 0 && !showAddExpense ? (
                <div className="text-gray-500 py-8 text-center">
                  No expenses scheduled. Click "Add Expense" to get started.
                </div>
              ) : (
                <>
                  {['capex', 'maintenance', 'vacancy', 'pti', 'pi']
                    .map((type) => ({
                      type,
                      expenses: expenses.filter(e => e.expense_type === type),
                      total: expenses.filter(e => e.expense_type === type)
                        .reduce((sum, exp) => sum + (exp.calculated_annual_cost || 0), 0)
                    }))
                    .filter(({ expenses }) => expenses.length > 0)
                    .sort((a, b) => b.total - a.total)
                    .map(({ type, expenses: typeExpenses, total: sectionTotal }) => {
                    const typeLabel = type === 'capex' ? 'Capital Expenses' : 
                                     type === 'maintenance' ? 'Maintenance' :
                                     type === 'vacancy' ? 'Vacancy Costs' :
                                     type === 'pti' ? 'PTI (Tax & Insurance)' : 
                                     'P&I (Financing)';
                    const isCollapsed = collapsedExpenseSections.has(type);

                    return (
                      <div key={type} className="space-y-2">
                        <button
                          onClick={() => toggleExpenseSection(type)}
                          className="flex items-center justify-between w-full text-left hover:bg-gray-50 px-2 py-1 rounded"
                        >
                          <div className="flex items-center gap-2">
                            {isCollapsed ? (
                              <ChevronRight className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )}
                            <h3 className="text-sm text-gray-700">{typeLabel}</h3>
                            <span className="text-xs text-gray-500">({typeExpenses.length})</span>
                          </div>
                          <div className="text-sm font-semibold text-red-700">
                            ${sectionTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </button>
                        {!isCollapsed && (
                          <div className="space-y-2 ml-6">
                            {typeExpenses.map((expense) => (
                            <div key={expense.id}>
                              {editingExpenseId === expense.id ? (
                                /* Edit Mode */
                                <Card className="bg-blue-50 border-blue-200">
                                  <CardContent className="pt-4">
                                    <div className="space-y-3">
                                      <div>
                                        <Label>Item Name *</Label>
                                        <Input
                                          value={expenseForm.item_name}
                                          onChange={(e) => setExpenseForm({ ...expenseForm, item_name: e.target.value })}
                                        />
                                      </div>

                                      {expense.expense_type === 'capex' && (
                                        <div className="grid grid-cols-3 gap-3">
                                          <div>
                                            <Label>Purchase Price</Label>
                                            <Input
                                              type="number"
                                              step="0.01"
                                              value={expenseForm.purchase_price}
                                              onChange={(e) => setExpenseForm({ ...expenseForm, purchase_price: e.target.value })}
                                            />
                                          </div>
                                          <div>
                                            <Label>Depreciation (decimal)</Label>
                                            <Input
                                              type="number"
                                              step="0.001"
                                              max="0.999"
                                              value={expenseForm.depreciation_rate}
                                              onChange={(e) => setExpenseForm({ ...expenseForm, depreciation_rate: e.target.value })}
                                              placeholder="e.g., 0.075"
                                            />
                                          </div>
                                          <div>
                                            <Label>Count</Label>
                                            <Input
                                              type="number"
                                              min="1"
                                              value={expenseForm.count}
                                              onChange={(e) => setExpenseForm({ ...expenseForm, count: e.target.value })}
                                            />
                                          </div>
                                        </div>
                                      )}

                                      {(expense.expense_type === 'pti' || expense.expense_type === 'maintenance') && (
                                        <div>
                                          <Label>Annual Cost</Label>
                                          <Input
                                            type="number"
                                            step="0.01"
                                            value={expenseForm.annual_cost}
                                            onChange={(e) => setExpenseForm({ ...expenseForm, annual_cost: e.target.value })}
                                          />
                                        </div>
                                      )}

                                      {expense.expense_type === 'pi' && (
                                        <div className="grid grid-cols-2 gap-3">
                                          <div>
                                            <Label>Principal</Label>
                                            <Input
                                              type="number"
                                              step="0.01"
                                              value={expenseForm.principal}
                                              onChange={(e) => setExpenseForm({ ...expenseForm, principal: e.target.value })}
                                            />
                                          </div>
                                          <div>
                                            <Label>Interest Rate (decimal)</Label>
                                            <Input
                                              type="number"
                                              step="0.001"
                                              max="0.999"
                                              value={expenseForm.interest_rate}
                                              onChange={(e) => setExpenseForm({ ...expenseForm, interest_rate: e.target.value })}
                                              placeholder="e.g., 0.065"
                                            />
                                          </div>
                                        </div>
                                      )}

                                      <div className="flex gap-2 pt-2">
                                        <Button
                                          onClick={() => handleEditExpense(expense.id)}
                                          disabled={!expenseForm.item_name}
                                          size="sm"
                                          className="bg-black text-white hover:bg-gray-800 h-7 text-xs"
                                        >
                                          <Check className="h-3 w-3 mr-1" />
                                          Save
                                        </Button>
                                        <Button
                                          variant="outline"
                                          onClick={resetExpenseForm}
                                          size="sm"
                                          className="h-7 text-xs"
                                        >
                                          <X className="h-3 w-3 mr-1" />
                                          Cancel
                                        </Button>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ) : (
                                /* View Mode */
                                <div className="flex justify-between items-center py-1.5 px-2 bg-gray-50 rounded">
                                  <div className="flex-1">
                                    <div className="text-sm font-medium">{expense.item_name}</div>
                                    {expense.expense_type === 'capex' && (
                                      <div className="text-xs text-gray-600">
                                        ${expense.purchase_price?.toLocaleString()} × {expense.depreciation_rate?.toFixed(3)} × {expense.count}
                                      </div>
                                    )}
                                    {(expense.expense_type === 'pti' || expense.expense_type === 'maintenance') && expense.annual_cost && (
                                      <div className="text-xs text-gray-600">
                                        Annual: ${expense.annual_cost?.toLocaleString()}
                                      </div>
                                    )}
                                    {expense.expense_type === 'pi' && (
                                      <div className="text-xs text-gray-600">
                                        ${expense.principal?.toLocaleString()} × {expense.interest_rate?.toFixed(3)}
                                      </div>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <div className="text-right text-sm font-semibold text-red-700">
                                      ${expense.calculated_annual_cost?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    </div>
                                    <div className="flex gap-0.5">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => startEditExpense(expense)}
                                        className="h-6 w-6 p-0"
                                      >
                                        <Edit2 className="h-3 w-3" />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDeleteExpense(expense.id, expense.item_name)}
                                        className="h-6 w-6 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                      >
                                        <Trash2 className="h-3 w-3" />
                                      </Button>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  
                  {/* Total Expenses */}
                  <div className="flex justify-between items-center p-3 bg-red-100 rounded font-bold">
                    <div>Total Annual Expenses</div>
                    <div className="text-red-700">${totalExpenses.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* REVENUE SECTION */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Scheduled Revenue
            </CardTitle>
            {!showAddRevenue && !editingRevenueId && !editingExpenseId && (
              <Button
                onClick={() => {
                  setShowAddRevenue(true);
                  setShowAddExpense(false);
                }}
                size="sm"
                className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
              >
                <Plus className="h-3 w-3 mr-1" />
                Add Revenue
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loadingRevenues ? (
            <div className="text-gray-500 py-4">Loading revenue...</div>
          ) : (
            <div className="space-y-4">
              {/* Add Revenue Form */}
              {showAddRevenue && (
                <Card className="bg-green-50 border-green-200">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Add New Revenue</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <Label>Revenue Type *</Label>
                        <Select
                          value={revenueForm.revenue_type}
                          onValueChange={(value) => setRevenueForm({ ...revenueForm, revenue_type: value })}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="principal_paydown">Principal Paydown</SelectItem>
                            <SelectItem value="appreciation">Appreciation</SelectItem>
                            <SelectItem value="value_added">Value Added</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label>Item Name *</Label>
                        <Input
                          value={revenueForm.item_name}
                          onChange={(e) => setRevenueForm({ ...revenueForm, item_name: e.target.value })}
                          placeholder={
                            revenueForm.revenue_type === 'principal_paydown' ? 'e.g., Mortgage, Line of Credit' :
                            revenueForm.revenue_type === 'appreciation' ? 'e.g., Property Appreciation, Market Growth' :
                            revenueForm.revenue_type === 'value_added' ? 'e.g., Kitchen Remodel, New Deck' :
                            'Enter item name'
                          }
                        />
                      </div>

                      {/* Principal Paydown Fields */}
                      {revenueForm.revenue_type === 'principal_paydown' && (
                        <div>
                          <Label>Annual Amount</Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={revenueForm.annual_amount}
                            onChange={(e) => setRevenueForm({ ...revenueForm, annual_amount: e.target.value })}
                          />
                        </div>
                      )}

                      {/* Appreciation Fields */}
                      {revenueForm.revenue_type === 'appreciation' && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label>Property Value</Label>
                            <Input
                              type="number"
                              step="0.01"
                              value={revenueForm.property_value}
                              onChange={(e) => setRevenueForm({ ...revenueForm, property_value: e.target.value })}
                            />
                          </div>
                          <div>
                            <Label>Appreciation Rate (decimal)</Label>
                            <Input
                              type="number"
                              step="0.001"
                              max="0.999"
                              value={revenueForm.appreciation_rate}
                              onChange={(e) => setRevenueForm({ ...revenueForm, appreciation_rate: e.target.value })}
                              placeholder="Default: 0.025"
                            />
                          </div>
                        </div>
                      )}

                      {/* Value Added Fields */}
                      {revenueForm.revenue_type === 'value_added' && (
                        <div>
                          <Label>Value Added Amount</Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={revenueForm.value_added_amount}
                            onChange={(e) => setRevenueForm({ ...revenueForm, value_added_amount: e.target.value })}
                          />
                        </div>
                      )}

                      <div className="flex gap-2 pt-2">
                        <Button
                          onClick={handleAddRevenue}
                          disabled={!revenueForm.revenue_type || !revenueForm.item_name}
                          size="sm"
                          className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
                        >
                          <Check className="h-3 w-3 mr-1" />
                          Save
                        </Button>
                        <Button
                          variant="outline"
                          onClick={resetRevenueForm}
                          size="sm"
                          className="h-8 text-xs"
                        >
                          <X className="h-3 w-3 mr-1" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Revenue List */}
              {revenues.length === 0 && !showAddRevenue ? (
                <div className="text-gray-500 py-8 text-center">
                  No revenue scheduled. Click "Add Revenue" to get started.
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    {revenues
                      .sort((a, b) => (b.calculated_annual_amount || 0) - (a.calculated_annual_amount || 0))
                      .map((revenue) => (
                      <div key={revenue.id}>
                        {editingRevenueId === revenue.id ? (
                          /* Edit Mode */
                          <Card className="bg-green-50 border-green-200">
                            <CardContent className="pt-4">
                              <div className="space-y-3">
                                <div>
                                  <Label>Item Name *</Label>
                                  <Input
                                    value={revenueForm.item_name}
                                    onChange={(e) => setRevenueForm({ ...revenueForm, item_name: e.target.value })}
                                  />
                                </div>

                                {revenue.revenue_type === 'principal_paydown' && (
                                  <div>
                                    <Label>Annual Amount</Label>
                                    <Input
                                      type="number"
                                      step="0.01"
                                      value={revenueForm.annual_amount}
                                      onChange={(e) => setRevenueForm({ ...revenueForm, annual_amount: e.target.value })}
                                    />
                                  </div>
                                )}

                                {revenue.revenue_type === 'appreciation' && (
                                  <div className="grid grid-cols-2 gap-3">
                                    <div>
                                      <Label>Property Value</Label>
                                      <Input
                                        type="number"
                                        step="0.01"
                                        value={revenueForm.property_value}
                                        onChange={(e) => setRevenueForm({ ...revenueForm, property_value: e.target.value })}
                                      />
                                    </div>
                                    <div>
                                      <Label>Appreciation Rate (decimal)</Label>
                                      <Input
                                        type="number"
                                        step="0.001"
                                        max="0.999"
                                        value={revenueForm.appreciation_rate}
                                        onChange={(e) => setRevenueForm({ ...revenueForm, appreciation_rate: e.target.value })}
                                        placeholder="Default: 0.025"
                                      />
                                    </div>
                                  </div>
                                )}

                                {revenue.revenue_type === 'value_added' && (
                                  <div>
                                    <Label>Value Added Amount</Label>
                                    <Input
                                      type="number"
                                      step="0.01"
                                      value={revenueForm.value_added_amount}
                                      onChange={(e) => setRevenueForm({ ...revenueForm, value_added_amount: e.target.value })}
                                    />
                                  </div>
                                )}

                                <div className="flex gap-2 pt-2">
                                  <Button
                                    onClick={() => handleEditRevenue(revenue.id)}
                                    disabled={!revenueForm.item_name}
                                    size="sm"
                                    className="bg-black text-white hover:bg-gray-800 h-7 text-xs"
                                  >
                                    <Check className="h-3 w-3 mr-1" />
                                    Save
                                  </Button>
                                  <Button
                                    variant="outline"
                                    onClick={resetRevenueForm}
                                    size="sm"
                                    className="h-7 text-xs"
                                  >
                                    <X className="h-3 w-3 mr-1" />
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        ) : (
                          /* View Mode */
                          <div className="flex justify-between items-center py-1.5 px-2 bg-gray-50 rounded">
                            <div className="flex-1">
                              <div className="text-sm font-medium">{revenue.item_name}</div>
                              {revenue.revenue_type === 'appreciation' && (
                                <div className="text-xs text-gray-600">
                                  ${revenue.property_value?.toLocaleString()} × {revenue.appreciation_rate?.toFixed(3)}
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="text-right text-sm font-semibold text-green-700">
                                ${revenue.calculated_annual_amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </div>
                              <div className="flex gap-0.5">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => startEditRevenue(revenue)}
                                  className="h-6 w-6 p-0"
                                >
                                  <Edit2 className="h-3 w-3" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeleteRevenue(revenue.id, revenue.item_name)}
                                  className="h-6 w-6 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Total Revenue */}
                  <div className="flex justify-between items-center p-3 bg-green-100 rounded font-bold">
                    <div>Total Annual Revenue</div>
                    <div className="text-green-700">${totalRevenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* NET INCOME */}
      {(expenses.length > 0 || revenues.length > 0) && (
        <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-200">
          <CardContent className="pt-6">
            <div className="flex justify-between items-center text-xl font-bold">
              <div>Net Annual Income</div>
              <div className={totalRevenue - totalExpenses >= 0 ? 'text-green-700' : 'text-red-700'}>
                ${(totalRevenue - totalExpenses).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template Modal */}
      <Dialog open={showTemplateModal} onOpenChange={setShowTemplateModal}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Auto-Apply Template</DialogTitle>
            <p className="text-xs text-gray-600 mt-1">
              Select which items to add from <strong>316 S 50th Ave</strong> template (scaled to your property)
            </p>
          </DialogHeader>
          
          <div className="flex-1 overflow-y-auto space-y-4 py-4">
            {loadingTemplate ? (
              <div className="text-center py-8 text-gray-500">Loading template...</div>
            ) : templatePreview ? (
              <>
                {/* Expenses Checklist */}
                {templatePreview.expenses.length > 0 && (
                  <div className="border rounded-lg">
                    <div className="bg-gray-50 px-4 py-2 border-b flex justify-between items-center">
                      <h4 className="text-sm font-semibold text-gray-900">
                        Scheduled Expenses ({selectedExpenses.size}/{templatePreview.expenses.length} selected)
                      </h4>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => setSelectedExpenses(new Set(templatePreview.expenses.map((_, idx) => idx)))}
                        >
                          Select All
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => setSelectedExpenses(new Set())}
                        >
                          Deselect All
                        </Button>
                      </div>
                    </div>
                    <div className="divide-y max-h-64 overflow-y-auto">
                      {templatePreview.expenses.map((expense, idx) => (
                        <div key={idx} className="flex items-start gap-3 p-3 hover:bg-gray-50">
                          <Checkbox
                            checked={selectedExpenses.has(idx)}
                            onCheckedChange={() => toggleExpense(idx)}
                            className="mt-0.5"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-gray-900">{expense.item_name}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded uppercase">
                                {expense.expense_type}
                              </span>
                            </div>
                            <div className="text-[10px] text-gray-500 mt-0.5">
                              {expense.expense_type === 'capex' && expense.purchase_price && (
                                <>Purchase: ${expense.purchase_price.toFixed(2)} | Depreciation: {(expense.depreciation_rate || 0) * 100}%/yr</>
                              )}
                              {expense.expense_type === 'maintenance' && expense.annual_cost && (
                                <>Annual Cost: ${expense.annual_cost.toFixed(2)}</>
                              )}
                              {expense.expense_type === 'pti' && expense.annual_cost && (
                                <>Annual Cost: ${expense.annual_cost.toFixed(2)}</>
                              )}
                              {expense.expense_type === 'pi' && expense.principal && (
                                <>Principal: ${expense.principal.toFixed(2)} | Rate: {(expense.interest_rate || 0) * 100}%</>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Revenue Checklist */}
                {templatePreview.revenue.length > 0 && (
                  <div className="border rounded-lg">
                    <div className="bg-gray-50 px-4 py-2 border-b flex justify-between items-center">
                      <h4 className="text-sm font-semibold text-gray-900">
                        Scheduled Revenue ({selectedRevenue.size}/{templatePreview.revenue.length} selected)
                      </h4>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => setSelectedRevenue(new Set(templatePreview.revenue.map((_, idx) => idx)))}
                        >
                          Select All
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs"
                          onClick={() => setSelectedRevenue(new Set())}
                        >
                          Deselect All
                        </Button>
                      </div>
                    </div>
                    <div className="divide-y">
                      {templatePreview.revenue.map((rev, idx) => (
                        <div key={idx} className="flex items-start gap-3 p-3 hover:bg-gray-50">
                          <Checkbox
                            checked={selectedRevenue.has(idx)}
                            onCheckedChange={() => toggleRevenue(idx)}
                            className="mt-0.5"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-gray-900">{rev.item_name}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded uppercase">
                                {rev.revenue_type}
                              </span>
                            </div>
                            <div className="text-[10px] text-gray-500 mt-0.5">
                              {rev.revenue_type === 'appreciation' && rev.property_value && (
                                <>Property Value: ${rev.property_value.toFixed(2)} | Rate: {(rev.appreciation_rate || 0) * 100}%/yr</>
                              )}
                              {rev.revenue_type === 'principal_paydown' && rev.annual_amount && (
                                <>Annual Amount: ${rev.annual_amount.toFixed(2)}</>
                              )}
                              {rev.revenue_type === 'value_added' && rev.value_added_amount && (
                                <>Value Added: ${rev.value_added_amount.toFixed(2)}</>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Scaling Info */}
                {templatePreview.scaling_factors && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <h4 className="text-xs font-semibold text-blue-900 mb-1">Scaling Factors:</h4>
                    <div className="text-[10px] text-blue-800 grid grid-cols-4 gap-2">
                      <div>Price: {templatePreview.scaling_factors.price_ratio?.toFixed(2)}x</div>
                      <div>Beds: {templatePreview.scaling_factors.beds_ratio?.toFixed(2)}x</div>
                      <div>Baths: {templatePreview.scaling_factors.baths_ratio?.toFixed(2)}x</div>
                      <div>Sq Ft: {templatePreview.scaling_factors.sqft_ratio?.toFixed(2)}x</div>
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>
          
          <DialogFooter className="border-t pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowTemplateModal(false);
                setTemplatePreview(null);
              }}
              disabled={applyingTemplate}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
            <Button
              onClick={handleApplyTemplate}
              disabled={applyingTemplate || !templatePreview || (selectedExpenses.size === 0 && selectedRevenue.size === 0)}
              className="bg-blue-600 text-white hover:bg-blue-700 h-8 text-xs"
            >
              <Zap className="h-3 w-3 mr-1.5" />
              {applyingTemplate ? 'Applying...' : `Apply ${selectedExpenses.size + selectedRevenue.size} Items`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

