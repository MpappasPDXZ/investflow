'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useProperties } from '@/lib/hooks/use-properties';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api-client';
import { Camera, Upload, X, FileText, Image, Loader2, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const DOCUMENT_TYPES = [
  { value: "lease", label: "Lease" },
  { value: "background_check", label: "Background Check" },
  { value: "contract", label: "Contract" },
  { value: "invoice", label: "Invoice" },
  { value: "inspection", label: "Inspection" },
  { value: "photo", label: "Property Photo" },
  { value: "other", label: "Other" },
];

// iOS-friendly accept string
const FILE_ACCEPT = 'image/*,application/pdf,.pdf,.jpg,.jpeg,.png,.gif,.webp,.heic,.heif';

export default function AddDocumentPage() {
  const router = useRouter();
  const { data: propertiesData } = useProperties();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    property_id: 'unassigned',
    display_name: '',
    document_type: 'other',
  });
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);

  const properties = propertiesData?.items || [];

  // Create preview for selected file
  useEffect(() => {
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setFilePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  }, [file]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    if (selectedFile) {
      // Validate file type
      const allowedTypes = [
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'image/heic',
        'image/heif',
      ];
      
      if (!allowedTypes.includes(selectedFile.type) && !selectedFile.name.match(/\.(heic|heif)$/i)) {
        setError('Invalid file type. Please upload PDF, JPEG, PNG, GIF, WebP, or HEIC files.');
        return;
      }
      
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError('File too large. Maximum size is 10MB.');
        return;
      }
      
      setError('');
      setFile(selectedFile);
    }
  };

  const clearFile = () => {
    setFile(null);
    setFilePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file) {
      setError('Please select a file to upload');
      return;
    }
    
    setError('');
    setLoading(true);

    try {
      const uploadFormData = new FormData();
      uploadFormData.append('file', file);
      uploadFormData.append('document_type', formData.document_type);
      
      if (formData.property_id && formData.property_id !== 'unassigned') {
        uploadFormData.append('property_id', formData.property_id);
      }
      
      if (formData.display_name.trim()) {
        uploadFormData.append('display_name', formData.display_name.trim());
      }

      await apiClient.upload('/documents/upload', uploadFormData);
      
      router.push('/documents');
    } catch (err) {
      console.error('Error uploading document:', err);
      setError((err as Error).message || 'Failed to upload document');
    } finally {
      setLoading(false);
    }
  };

  const isPdf = file?.type === 'application/pdf';

  return (
    <div className="p-4">
      <div className="mb-4">
        <Link href="/documents" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-2">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Documents
        </Link>
        <h1 className="text-lg md:text-xl font-bold text-gray-900">Add Document</h1>
        <p className="text-xs md:text-sm text-gray-600 mt-0.5">Upload a new document or property photo</p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm">Document Details</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* File Upload - Prominent at top */}
            <div>
              <Label className="text-xs md:text-sm">File *</Label>
              <div className="mt-2">
                {file ? (
                  // File Selected Preview
                  <div className="border-2 border-green-300 bg-green-50 rounded-lg p-4">
                    <div className="flex items-center gap-3">
                      {filePreview ? (
                        <img 
                          src={filePreview} 
                          alt="Preview" 
                          className="h-20 w-20 object-cover rounded-lg shadow-sm"
                        />
                      ) : isPdf ? (
                        <div className="h-20 w-20 bg-red-100 rounded-lg flex items-center justify-center">
                          <FileText className="h-10 w-10 text-red-600" />
                        </div>
                      ) : (
                        <div className="h-20 w-20 bg-gray-200 rounded-lg flex items-center justify-center">
                          <FileText className="h-10 w-10 text-gray-500" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{file.name}</p>
                        <p className="text-sm text-gray-500">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={clearFile}
                        className="h-10 w-10 p-0 text-gray-500 hover:text-red-600"
                      >
                        <X className="h-5 w-5" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  // File Upload Area
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 active:bg-gray-50 transition-colors"
                  >
                    <div className="flex flex-col items-center gap-3">
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-blue-100 rounded-full">
                          <Camera className="h-6 w-6 text-blue-600" />
                        </div>
                        <div className="p-3 bg-gray-100 rounded-full">
                          <Upload className="h-6 w-6 text-gray-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-700">
                        Tap to take photo or upload file
                      </p>
                      <p className="text-xs text-gray-500">
                        PDF, JPEG, PNG, GIF, WebP, HEIC (max 10MB)
                      </p>
                    </div>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={FILE_ACCEPT}
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>
            </div>

            {/* Form Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="document_type" className="text-xs md:text-sm">Document Type *</Label>
                <select
                  id="document_type"
                  value={formData.document_type}
                  onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
                  required
                  className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                >
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <Label htmlFor="property_id" className="text-xs md:text-sm">Property</Label>
                <select
                  id="property_id"
                  value={formData.property_id}
                  onChange={(e) => setFormData({ ...formData, property_id: e.target.value })}
                  className="w-full px-3 py-2.5 md:py-2 border border-gray-300 rounded-md text-base md:text-sm mt-1 min-h-[44px]"
                >
                  <option value="unassigned">Unassigned</option>
                  {properties.map((prop) => (
                    <option key={prop.id} value={prop.id}>
                      {prop.display_name || prop.address_line1 || 'Property'}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="md:col-span-2">
                <Label htmlFor="display_name" className="text-xs md:text-sm">Display Name (optional)</Label>
                <Input
                  id="display_name"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="text-base md:text-sm mt-1 min-h-[44px]"
                  placeholder="e.g., Front of house, Signed lease 2024"
                />
                <p className="text-xs text-gray-500 mt-1">
                  If left empty, the original filename will be used
                </p>
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">
                {error}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button
                type="submit"
                className="bg-black text-white hover:bg-gray-800 min-h-[48px] flex-1 sm:flex-none"
                disabled={loading || !file}
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Document
                  </>
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="min-h-[48px]"
                onClick={() => router.back()}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

