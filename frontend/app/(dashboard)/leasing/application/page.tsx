'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Download, Upload, FileText, Eye, Trash2 } from 'lucide-react';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useDocuments, useUploadDocument, useDeleteDocument } from '@/lib/hooks/use-documents';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import type { Document } from '@/lib/types';

export default function RentalApplicationPage() {
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [displayName, setDisplayName] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);

  const { data: tenantsData } = useTenants();

  // Get selected tenant to find property_id
  const tenantForPropertyId = tenantsData?.tenants.find(t => t.id === selectedTenantId);

  // Fetch documents for selected tenant
  const { data: documentsData, isLoading: docsLoading } = useDocuments({
    property_id: tenantForPropertyId?.property_id || '',
    tenant_id: selectedTenantId || undefined,
    document_type: 'rental_application',
  });

  const documents = documentsData?.items || [];

  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();

  const handleDownloadNebraska = () => {
    // Download the Nebraska form from the root
    window.open('/Nebraska-Residential-Rental-Application.pdf', '_blank');
  };

  const handleDownloadMissouri = () => {
    // Download the Missouri form from the root
    window.open('/Missouri-Residential-Rental-Application.pdf', '_blank');
  };

  const handleDownloadShowingForm = () => {
    // Download the self-guided showing form from the public folder
    window.open('/self_guided_showing_form.pdf', '_blank');
  };

  const handleUpload = async () => {
    if (!fileToUpload || !selectedTenantId) return;
    setUploading(true);
    try {
      await uploadMutation.mutateAsync({
        file: fileToUpload,
        documentType: 'rental_application',
        displayName: displayName || fileToUpload.name,
        tenantId: selectedTenantId,
      });
      setFileToUpload(null);
      setDisplayName('');
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload application');
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const selectedTenant = tenantsData?.tenants.find(t => t.id === selectedTenantId);

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs text-gray-500 mb-1">Viewing:</div>
        <h1 className="text-lg font-bold text-gray-900">Rental Applications</h1>
        <p className="text-sm text-gray-600 mt-1">
          Download blank application forms to send to prospective tenants, then upload completed applications
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Download Forms Section */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Download className="h-4 w-4 text-blue-600" />
              Download Blank Forms
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between p-2.5 border border-gray-200 rounded hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <FileText className="h-4 w-4 text-gray-600 shrink-0" />
                <span className="text-xs font-medium text-gray-900 truncate">Nebraska Residential Rental Application</span>
              </div>
              <Button
                onClick={handleDownloadNebraska}
                size="sm"
                variant="outline"
                className="h-7 text-xs px-2 shrink-0"
              >
                <Download className="h-3 w-3 mr-1" />
                Download
              </Button>
            </div>

            <div className="flex items-center justify-between p-2.5 border border-gray-200 rounded hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <FileText className="h-4 w-4 text-gray-600 shrink-0" />
                <span className="text-xs font-medium text-gray-900 truncate">Missouri Residential Rental Application</span>
              </div>
              <Button
                onClick={handleDownloadMissouri}
                size="sm"
                variant="outline"
                className="h-7 text-xs px-2 shrink-0"
              >
                <Download className="h-3 w-3 mr-1" />
                Download
              </Button>
            </div>

            <div className="flex items-center justify-between p-2.5 border border-gray-200 rounded hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <FileText className="h-4 w-4 text-gray-600 shrink-0" />
                <span className="text-xs font-medium text-gray-900 truncate">Self-Guided Showing Agreement</span>
              </div>
              <Button
                onClick={handleDownloadShowingForm}
                size="sm"
                variant="outline"
                className="h-7 text-xs px-2 shrink-0"
              >
                <Download className="h-3 w-3 mr-1" />
                Download
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Tenant Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold">Select Tenant</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      </div>

      {selectedTenantId && (
        <>
          {/* Upload Section */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-sm font-bold">
                Upload Application for {selectedTenant?.first_name} {selectedTenant?.last_name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="display-name" className="text-xs">Display Name (optional)</Label>
                  <Input
                    id="display-name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g., Rental Application - 12/20/2025"
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
                    {uploading ? 'Uploading...' : 'Upload Application'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Applications List */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-sm font-bold">
                Rental Applications ({documents?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {docsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading applications...</div>
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
                            {formatFileSize(doc.file_size || 0)} • {new Date(doc.created_at).toLocaleDateString()}
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
                            if (confirm('Are you sure you want to delete this application?')) {
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
                  No rental applications uploaded yet.
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Quick Tips */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm font-bold">Quick Tips</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-xs text-gray-700">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">1.</span>
              <span>Download the appropriate state form and send it to your prospective tenant via email or text</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">2.</span>
              <span>Have the tenant complete the form and return it to you (email, photo, or physical copy)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">3.</span>
              <span>Upload the completed application to your Vault for record-keeping and review</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">4.</span>
              <span>Tag the document with the property address and tenant name for easy organization</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

