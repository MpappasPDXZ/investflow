'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLeases } from '@/lib/hooks/use-leases';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { FileSignature, Plus, FileText, Download, Eye, Trash2, Copy, XCircle } from 'lucide-react';
import Link from 'next/link';

export default function LeasesPage() {
  const router = useRouter();
  const { listLeases, deleteLease } = useLeases();
  const [leases, setLeases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: 'all',
    state: 'all',
  });

  useEffect(() => {
    fetchLeases();
  }, [filters]);

  const fetchLeases = async () => {
    try {
      setLoading(true);
      const response = await listLeases(filters);
      setLeases(response.leases || []);
    } catch (err) {
      console.error('Error fetching leases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this lease?')) return;
    
    try {
      await deleteLease(id);
      fetchLeases();
    } catch (err) {
      console.error('Error deleting lease:', err);
      alert('Failed to delete lease');
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-800 border-gray-300',
      pending_signature: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      active: 'bg-green-100 text-green-800 border-green-300',
      expired: 'bg-red-100 text-red-800 border-red-300',
      terminated: 'bg-red-100 text-red-800 border-red-300',
    };
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium border ${styles[status] || styles.draft}`}>
        {status.replace('_', ' ')}
      </span>
    );
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Managing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <FileSignature className="h-5 w-5" />
            Lease Agreements
          </h1>
        </div>
        <Link href="/leases/create">
          <Button className="bg-black text-white hover:bg-gray-800 h-8 text-xs">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Create Lease
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="w-48">
              <Select
                value={filters.status}
                onValueChange={(value) => setFilters({ ...filters, status: value })}
              >
                <SelectTrigger className="text-sm h-9">
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="pending_signature">Pending Signature</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                  <SelectItem value="terminated">Terminated</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-48">
              <Select
                value={filters.state}
                onValueChange={(value) => setFilters({ ...filters, state: value })}
              >
                <SelectTrigger className="text-sm h-9">
                  <SelectValue placeholder="All states" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All states</SelectItem>
                  <SelectItem value="NE">Nebraska</SelectItem>
                  <SelectItem value="MO">Missouri</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="outline"
              onClick={() => setFilters({ status: '', state: '' })}
              className="h-9 text-xs"
            >
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Leases Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-bold">
            All Leases ({leases.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading leases...</div>
          ) : leases.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p className="text-gray-500 mb-4">No leases found</p>
              <Link href="/leases/create">
                <Button className="bg-black text-white hover:bg-gray-800">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Lease
                </Button>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 font-bold text-gray-700">Property</th>
                    <th className="pb-3 font-bold text-gray-700">Tenants</th>
                    <th className="pb-3 font-bold text-gray-700">Start Date</th>
                    <th className="pb-3 font-bold text-gray-700">End Date</th>
                    <th className="pb-3 font-bold text-gray-700 text-right">Monthly Rent</th>
                    <th className="pb-3 font-bold text-gray-700">Status</th>
                    <th className="pb-3 font-bold text-gray-700 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {leases.map((lease) => (
                    <tr key={lease.id} className="border-b hover:bg-gray-50">
                      <td className="py-3">
                        <div className="font-medium">{lease.property.display_name}</div>
                        <div className="text-xs text-gray-500">{lease.property.address}</div>
                      </td>
                      <td className="py-3">
                        {lease.tenants.map((t: any, i: number) => (
                          <div key={i} className="text-sm">
                            {t.first_name} {t.last_name}
                          </div>
                        ))}
                      </td>
                      <td className="py-3 text-gray-900">
                        {new Date(lease.commencement_date).toLocaleDateString()}
                      </td>
                      <td className="py-3 text-gray-900">
                        {new Date(lease.termination_date).toLocaleDateString()}
                      </td>
                      <td className="py-3 text-right font-medium">
                        ${lease.monthly_rent.toLocaleString()}
                      </td>
                      <td className="py-3">
                        {getStatusBadge(lease.status)}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-1 justify-end">
                          <Link href={`/leases/create?lease_id=${lease.id}`}>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              title="View/Edit Lease"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </Link>
                          
                          {lease.pdf_url && (
                            <a href={lease.pdf_url} target="_blank" rel="noopener noreferrer">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                title="Download PDF"
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            </a>
                          )}
                          
                          {lease.status === 'draft' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(lease.id)}
                              className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
