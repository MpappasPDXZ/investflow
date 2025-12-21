'use client';

import { useState } from 'react';
import { Upload, FileText, Trash2, Download, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useDocuments, useUploadDocument, useDeleteDocument } from '@/lib/hooks/use-documents';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import type { Document } from '@/lib/types';

const DOCUMENT_TYPES = [
  { value: 'credit_report', label: 'Credit Report' },
  { value: 'identity_report', label: 'Identity Report' },
  { value: 'criminal_check', label: 'Criminal Report' },
  { value: 'eviction_report', label: 'Evictions Report' },
  { value: 'income_insights', label: 'Income Insights' },
  { value: 'income_verification', label: 'Income Verification' },
  { value: 'employment_verification', label: 'Employment Verification' },
  { value: 'reference_check', label: 'Reference Check' },
  { value: 'screening_other', label: 'Other Screening Document' },
];

export default function BackgroundCheckPage() {
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [selectedDocType, setSelectedDocType] = useState<string>('credit_report');
  const [displayName, setDisplayName] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  
  const { data: tenantsData } = useTenants();
  
  // Fetch documents for selected tenant using the proper hook
  const { data: documentsData, isLoading: docsLoading } = useDocuments({
    tenant_id: selectedTenantId || undefined,
  });
  
  const documents = documentsData?.items || [];
  
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  
  const handleUpload = async () => {
    if (!fileToUpload || !selectedTenantId) return;
    setUploading(true);
    try {
      await uploadMutation.mutateAsync({
        file: fileToUpload,
        documentType: selectedDocType,
        displayName: displayName || fileToUpload.name,
        tenantId: selectedTenantId,
      });
      setFileToUpload(null);
      setDisplayName('');
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload document');
    } finally {
      setUploading(false);
    }
  };
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };
  
  const getDocTypeLabel = (type: string) => {
    return DOCUMENT_TYPES.find(t => t.value === type)?.label || type;
  };
  
  const selectedTenant = tenantsData?.tenants.find(t => t.id === selectedTenantId);
  
  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs text-gray-500 mb-1">Viewing:</div>
        <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Background Check Documents
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          Upload and manage tenant screening documents
        </p>
      </div>
      
      {/* Tenant Selection */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-bold">Select Tenant</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-md">
            <Label htmlFor="tenant-select" className="text-xs">Tenant</Label>
            <Select value={selectedTenantId} onValueChange={setSelectedTenantId}>
              <SelectTrigger id="tenant-select">
                <SelectValue placeholder="Choose a tenant..." />
              </SelectTrigger>
              <SelectContent>
                {tenantsData?.tenants.map((tenant) => (
                  <SelectItem key={tenant.id} value={tenant.id}>
                    {tenant.first_name} {tenant.last_name}
                    {tenant.email && ` (${tenant.email})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
      
      {selectedTenantId && (
        <>
          {/* Upload Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-sm font-bold">
                Upload Document for {selectedTenant?.first_name} {selectedTenant?.last_name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="doc-type" className="text-xs">Document Type</Label>
                  <Select value={selectedDocType} onValueChange={setSelectedDocType}>
                    <SelectTrigger id="doc-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DOCUMENT_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <Label htmlFor="display-name" className="text-xs">Display Name (optional)</Label>
                  <Input
                    id="display-name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g., Credit Report - 12/20/2025"
                  />
                </div>
                
                <div className="md:col-span-2">
                  <Label htmlFor="file-upload" className="text-xs">Choose File</Label>
                  <Input
                    id="file-upload"
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.gif,.webp"
                    onChange={(e) => setFileToUpload(e.target.files?.[0] || null)}
                    className="cursor-pointer"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Accepted formats: PDF, JPG, PNG, GIF, WEBP (Max 10MB)
                  </p>
                </div>
                
                <div className="md:col-span-2">
                  <Button
                    onClick={handleUpload}
                    disabled={!fileToUpload || uploading}
                    className="w-full md:w-auto h-8 text-xs"
                  >
                    <Upload className="h-3 w-3 mr-2" />
                    {uploading ? 'Uploading...' : 'Upload Document'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Documents List */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-bold">
                Screening Documents ({documents?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {docsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading documents...</div>
              ) : documents && documents.length > 0 ? (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <FileText className="h-8 w-8 text-blue-600" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm text-gray-900 truncate">
                            {doc.display_name || doc.file_name}
                          </div>
                          <div className="text-xs text-gray-500">
                            {getDocTypeLabel(doc.document_type)} • {formatFileSize(doc.file_size || 0)} • {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <ReceiptViewer
                          documentId={doc.id}
                          fileName={doc.display_name || doc.file_name}
                          fileType={doc.file_type}
                          trigger={
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              title="View"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          }
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm('Are you sure you want to delete this document?')) {
                              deleteMutation.mutate(doc.id);
                            }
                          }}
                          className="h-8 w-8 p-0 text-red-600 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No screening documents uploaded yet.
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

