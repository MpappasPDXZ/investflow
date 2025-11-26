'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks/use-auth';
import { Building2, TrendingUp, DollarSign, FileText, Receipt } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Link from 'next/link';

export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-8 py-16">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            InvestFlow
          </h1>
          <p className="text-xl text-gray-600">
            Professional Property Management & Cash Flow Analysis
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
            <Building2 className="h-8 w-8 text-gray-700 mb-4" />
            <h3 className="font-semibold text-gray-900 mb-2">Properties</h3>
            <p className="text-sm text-gray-600 mb-4">
              Manage your rental properties
            </p>
            <Link href="/properties">
              <Button variant="outline" size="sm" className="w-full bg-black text-white hover:bg-gray-800">
                View Properties
              </Button>
            </Link>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
            <Receipt className="h-8 w-8 text-gray-700 mb-4" />
            <h3 className="font-semibold text-gray-900 mb-2">Expenses</h3>
            <p className="text-sm text-gray-600 mb-4">
              Track and categorize expenses
            </p>
            <Link href="/expenses">
              <Button variant="outline" size="sm" className="w-full bg-black text-white hover:bg-gray-800">
                View Expenses
              </Button>
            </Link>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
            <TrendingUp className="h-8 w-8 text-gray-700 mb-4" />
            <h3 className="font-semibold text-gray-900 mb-2">Analytics</h3>
            <p className="text-sm text-gray-600 mb-4">
              Cash flow and ROI analysis
            </p>
            <Button variant="outline" size="sm" className="w-full bg-black text-white hover:bg-gray-800" disabled>
              Coming Soon
            </Button>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
            <FileText className="h-8 w-8 text-gray-700 mb-4" />
            <h3 className="font-semibold text-gray-900 mb-2">Reports</h3>
            <p className="text-sm text-gray-600 mb-4">
              Generate financial reports
            </p>
            <Button variant="outline" size="sm" className="w-full bg-black text-white hover:bg-gray-800" disabled>
              Coming Soon
            </Button>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-8 border border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Quick Actions</h2>
          <div className="flex gap-4">
            <Link href="/properties/add">
              <Button className="bg-black text-white hover:bg-gray-800">
                Add Property
              </Button>
            </Link>
            <Link href="/expenses/add">
              <Button className="bg-black text-white hover:bg-gray-800">
                Add Expense
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
