'use client';

import { useEffect, useState } from 'react';
import { useExpenses, useProperties } from '@/lib/hooks/use-expenses';
import { useProperties as usePropertiesHook } from '@/lib/hooks/use-properties';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus } from 'lucide-react';
import Link from 'next/link';
import { format } from 'date-fns';

export default function ExpensesPage() {
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  
  const { data: properties } = usePropertiesHook();
  const { data: expenses, isLoading } = useExpenses(selectedPropertyId || undefined);

  useEffect(() => {
    console.log('📊 [EXPENSES] Page loaded');
    if (expenses) {
      console.log('✅ [EXPENSES] GET /api/v1/expenses - Response:', expenses);
      console.log('📝 [EXPENSES] Backend to PostgreSQL/Lakekeeper: Expenses fetched');
    }
  }, [expenses]);

  const expenseTypeLabels: Record<string, string> = {
    capex: 'Capital Expenditure',
    pandi: 'Principal & Interest',
    utilities: 'Utilities',
    maintenance: 'Maintenance',
    insurance: 'Insurance',
    property_management: 'Property Management',
    other: 'Other',
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Expenses</h1>
          <p className="text-gray-600 mt-1">Track and manage property expenses</p>
        </div>
        <Link href="/expenses/add">
          <Button className="bg-black text-white hover:bg-gray-800">
            <Plus className="h-4 w-4 mr-2" />
            Add Expense
          </Button>
        </Link>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filter by Property
              </label>
              <select
                value={selectedPropertyId}
                onChange={(e) => setSelectedPropertyId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-black"
              >
                <option value="">All Properties</option>
                {properties?.items.map((prop) => (
                  <option key={prop.id} value={prop.id}>
                    {prop.display_name || prop.address_line1 || prop.id}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {selectedPropertyId ? 'Property Expenses' : 'All Expenses'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">Loading expenses...</div>
          ) : expenses?.items.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No expenses found. <Link href="/expenses/add" className="text-blue-600 hover:underline">Add your first expense</Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Receipt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expenses?.items.map((expense) => (
                  <TableRow key={expense.id}>
                    <TableCell className="text-sm">
                      {format(new Date(expense.date), 'MMM dd, yyyy')}
                    </TableCell>
                    <TableCell className="font-medium text-sm">
                      {expense.description}
                    </TableCell>
                    <TableCell className="font-medium text-sm">
                      ${expense.amount.toFixed(2)}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {expenseTypeLabels[expense.expense_type] || expense.expense_type}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {expense.vendor || '-'}
                    </TableCell>
                    <TableCell className="text-sm">
                      {expense.document_storage_id ? (
                        <ReceiptViewer expenseId={expense.id} />
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

