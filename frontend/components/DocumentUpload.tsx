'use client';

import { useState, useCallback } from 'react';
import { useUploadDocument } from '@/lib/hooks/use-documents';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { 
  Upload, 
  FileText, 
  Image, 
  X, 
  Check, 
  Loader2,
  AlertCircle
} from 'lucide-react';

interface DocumentUploadProps {
  propertyId?: string;
  unitId?: string;
  documentType?: 'receipt' | 'lease' | 'screening' | 'invoice' | 'other';
  onUploadSuccess?: (document: { id: string; file_name: string }) => void;
  onUploadError?: (error: string) => void;
  compact?: boolean;
  hideReceiptOption?: boolean;  // Hide receipt option (for Documents page - receipts go in Expenses)
}

const ACCEPTED_FILE_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
];

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function DocumentUpload({
  propertyId,
  unitId,
  documentType: defaultDocType = 'receipt',
  onUploadSuccess,
  onUploadError,
  compact = false,
  hideReceiptOption = false,
}: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState(defaultDocType);
  const [validationError, setValidationError] = useState<string | null>(null);
  
  const uploadMutation = useUploadDocument();

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
      return 'Invalid file type. Please upload PDF, JPEG, PNG, GIF, or WebP files only.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File too large. Maximum size is 10MB.';
    }
    return null;
  };

  const handleFile = useCallback((file: File) => {
    const error = validateFile(file);
    if (error) {
      setValidationError(error);
      return;
    }

    setValidationError(null);
    setSelectedFile(file);

    // Create preview for images
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setPreview(null);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, [handleFile]);

  const handleClear = () => {
    setSelectedFile(null);
    setPreview(null);
    setValidationError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      const result = await uploadMutation.mutateAsync({
        file: selectedFile,
        documentType,
        propertyId,
        unitId,
      });

      onUploadSuccess?.(result.document);
      handleClear();
    } catch (err) {
      const errorMessage = (err as Error).message;
      onUploadError?.(errorMessage);
    }
  };

  const isImage = selectedFile?.type.startsWith('image/');
  const isPdf = selectedFile?.type === 'application/pdf';

  if (compact) {
    return (
      <div className="space-y-2">
        <Label className="text-sm font-medium">Upload Document</Label>
        <input
          type="file"
          accept={ACCEPTED_FILE_TYPES.join(',')}
          onChange={handleFileSelect}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200 cursor-pointer"
        />
        {validationError && (
          <p className="text-sm text-red-600">{validationError}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative border-2 border-dashed rounded-lg p-8 transition-all duration-200 cursor-pointer
          ${isDragging 
            ? 'border-blue-500 bg-blue-50' 
            : selectedFile 
              ? 'border-green-400 bg-green-50' 
              : 'border-gray-300 hover:border-gray-400 bg-gray-50 hover:bg-gray-100'
          }
        `}
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept={ACCEPTED_FILE_TYPES.join(',')}
          onChange={handleFileSelect}
          className="hidden"
        />

        {selectedFile ? (
          <div className="flex items-center justify-center gap-4">
            {preview ? (
              <img 
                src={preview} 
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
            <div className="text-left">
              <p className="font-medium text-gray-900 truncate max-w-[200px]">
                {selectedFile.name}
              </p>
              <p className="text-sm text-gray-500">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClear();
                }}
                className="text-sm text-red-600 hover:text-red-800 mt-1 flex items-center gap-1"
              >
                <X className="h-3 w-3" />
                Remove
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center">
            <Upload className="h-12 w-12 mx-auto text-gray-400 mb-3" />
            <p className="text-sm font-medium text-gray-700">
              Drag and drop a file here, or click to browse
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PDF, JPEG, PNG, GIF, WebP (max 10MB)
            </p>
          </div>
        )}
      </div>

      {/* Validation Error */}
      {validationError && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {validationError}
        </div>
      )}

      {/* Upload Error */}
      {uploadMutation.isError && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {(uploadMutation.error as Error).message}
        </div>
      )}

      {/* Document Type Selector */}
      <div>
        <Label htmlFor="doc-type" className="text-sm font-medium">
          Document Type
        </Label>
        <select
          id="doc-type"
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value as typeof documentType)}
          className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {!hideReceiptOption && <option value="receipt">Receipt</option>}
          <option value="lease">Lease</option>
          <option value="screening">Screening</option>
          <option value="invoice">Invoice</option>
          <option value="other">Other</option>
        </select>
      </div>

      {/* Upload Button */}
      <Button
        onClick={handleUpload}
        disabled={!selectedFile || uploadMutation.isPending}
        className="w-full bg-black text-white hover:bg-gray-800"
      >
        {uploadMutation.isPending ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Uploading...
          </>
        ) : uploadMutation.isSuccess ? (
          <>
            <Check className="h-4 w-4 mr-2" />
            Uploaded!
          </>
        ) : (
          <>
            <Upload className="h-4 w-4 mr-2" />
            Upload Document
          </>
        )}
      </Button>
    </div>
  );
}

