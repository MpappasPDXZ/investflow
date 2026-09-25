/**
 * React Query hooks for expenses
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api-client';
import type { Expense, ExpenseListResponse } from '../types';

export function useExpenses(propertyId?: string) {
  return useQuery<ExpenseListResponse>({
    queryKey: ['expenses', propertyId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (propertyId) params.append('property_id', propertyId);
      params.append('limit', '1000');
      return apiClient.get<ExpenseListResponse>(`/expenses?${params.toString()}`);
    },
    enabled: !!propertyId,
    refetchOnMount: 'always',
    staleTime: 0,
  });
}

export function useExpensesByYear(propertyId?: string, year?: number) {
  return useQuery<ExpenseListResponse>({
    queryKey: ['expenses', propertyId, 'year', year],
    queryFn: () => {
      const params = new URLSearchParams();
      if (propertyId) params.append('property_id', propertyId);
      params.append('start_date', `${year}-01-01`);
      params.append('end_date', `${year}-12-31`);
      params.append('limit', '1000');
      return apiClient.get<ExpenseListResponse>(`/expenses?${params.toString()}`);
    },
    enabled: !!propertyId && !!year,
    refetchOnMount: 'always',
    staleTime: 0,
    gcTime: 300000,
  });
}

export function useExpense(expenseId: string) {
  return useQuery<Expense>({
    queryKey: ['expense', expenseId],
    queryFn: async () => {
      console.log(`[HOOK] 🔍 useExpense: Fetching expense ${expenseId}`);
      const start = performance.now();
      const data = await apiClient.get<Expense>(`/expenses/${expenseId}`);
      const duration = performance.now() - start;
      console.log(`[HOOK] ✅ useExpense: Loaded expense ${expenseId} in ${duration.toFixed(0)}ms`);
      return data;
    },
    enabled: !!expenseId,
    staleTime: 30000, // Cache for 30 seconds
    gcTime: 60000, // Keep in cache for 60 seconds after unmount
  });
}

async function invalidateExpenseQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  expenseId?: string
) {
  // Await so navigate-after-save does not remount the list on a still-fresh cache
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['expenses'] }),
    queryClient.invalidateQueries({ queryKey: ['expense-summary'] }),
    ...(expenseId
      ? [queryClient.invalidateQueries({ queryKey: ['expense', expenseId] })]
      : []),
  ]);
}

export function useCreateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      property_id: string;
      description: string;
      date: string;
      amount: number;
      vendor?: string;
      expense_type: string;
      expense_category?: string;
      tax_category?: string;
      unit_id?: string;
      notes?: string;
    }) => apiClient.post<Expense>('/expenses', data),
    onSuccess: async () => {
      await invalidateExpenseQueries(queryClient);
    },
  });
}

export function useCreateExpenseWithReceipt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (formData: FormData) =>
      apiClient.upload<Expense>('/expenses/with-receipt', formData),
    onSuccess: async () => {
      await invalidateExpenseQueries(queryClient);
    },
  });
}

export function useUpdateExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Expense> }) =>
      apiClient.put<Expense>(`/expenses/${id}`, data),
    onSuccess: async (_, variables) => {
      await invalidateExpenseQueries(queryClient, variables.id);
    },
  });
}

export function useDeleteExpense() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/expenses/${id}`),
    onSuccess: async () => {
      await invalidateExpenseQueries(queryClient);
    },
  });
}

export function useExpenseReceipt(expenseId: string) {
  return useQuery<{ download_url: string }>({
    queryKey: ['expense-receipt', expenseId],
    queryFn: () => apiClient.get<{ download_url: string }>(`/expenses/${expenseId}/receipt`),
    enabled: !!expenseId,
  });
}

export interface ExpenseSummary {
  yearly_totals: Array<{
    year: number;
    total: number;
    count: number;
    by_type: Record<string, number>;
    by_tax_category: Record<string, number>;
  }>;
  type_totals: Record<string, number>;
  tax_category_totals: Record<string, number>;
  grand_total: number;
  total_count: number;
}

export function useExpenseSummary(propertyId?: string, year?: number) {
  return useQuery<ExpenseSummary>({
    queryKey: ['expense-summary', propertyId, year],
    queryFn: () => {
      const params = new URLSearchParams();
      if (propertyId) params.append('property_id', propertyId);
      if (year) params.append('year', String(year));
      const queryString = params.toString();
      return apiClient.get<ExpenseSummary>(`/expenses/summary${queryString ? `?${queryString}` : ''}`);
    },
    enabled: !!propertyId, // Only fetch when propertyId is provided (required by backend)
    refetchOnMount: 'always',
    staleTime: 0,
  });
}

