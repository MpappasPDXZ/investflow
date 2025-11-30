'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FileText, Download, ExternalLink, ZoomIn, ZoomOut, X, Loader2 } from 'lucide-react';

interface ReceiptViewerProps {
  expenseId?: string;
  documentId?: string;
  downloadUrl?: string;
  fileName?: string;
  fileType?: string;
  trigger?: React.ReactNode;
}

export function ReceiptViewer({ 
  expenseId, 
  documentId,
  downloadUrl: propDownloadUrl, 
  fileName,
  fileType,
  trigger 
}: ReceiptViewerProps) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(propDownloadUrl || null);
  const [loading, setLoading] = useState(!propDownloadUrl);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    async function fetchReceipt() {
      if (propDownloadUrl) {
        setDownloadUrl(propDownloadUrl);
        setLoading(false);
        return;
      }

      try {
        let response: { download_url: string };
        
        if (expenseId) {
          response = await apiClient.get<{ download_url: string }>(
            `/expenses/${expenseId}/receipt`
          );
        } else if (documentId) {
          response = await apiClient.get<{ download_url: string }>(
            `/documents/${documentId}/download`
          );
        } else {
          throw new Error('No expense ID or document ID provided');
        }
        
        setDownloadUrl(response.download_url);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    if ((expenseId || documentId) && !propDownloadUrl) {
      fetchReceipt();
    }
  }, [expenseId, documentId, propDownloadUrl]);

  const isImage = downloadUrl?.match(/\.(jpg|jpeg|png|gif|webp)/i) || 
                  fileType?.startsWith('image/');
  const isPdf = downloadUrl?.match(/\.pdf/i) || 
                fileType === 'application/pdf';

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => setZoom(1);

  if (loading) {
    return <span className="text-gray-400 text-sm">Loading...</span>;
  }

  if (error || !downloadUrl) {
    return <span className="text-red-500 text-sm">No receipt</span>;
  }

  const displayName = fileName || 
    (isImage ? 'Image' : isPdf ? 'PDF' : 'Document');

  const TriggerButton = trigger || (
    <button
      onClick={() => setIsOpen(true)}
      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm font-medium transition-colors"
    >
      <FileText className="h-4 w-4" />
      View
    </button>
  );

  return (
    <>
      <div onClick={() => setIsOpen(true)} className="cursor-pointer inline-block">
        {TriggerButton}
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-5xl w-[95vw] h-[90vh] flex flex-col p-0">
          <DialogHeader className="px-6 py-4 border-b bg-gray-50 flex flex-row items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-lg font-semibold">
              <FileText className="h-5 w-5" />
              {displayName}
            </DialogTitle>
            <div className="flex items-center gap-2">
              {isImage && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleZoomOut}
                    disabled={zoom <= 0.5}
                  >
                    <ZoomOut className="h-4 w-4" />
                  </Button>
                  <span className="text-sm text-gray-600 min-w-[4rem] text-center">
                    {Math.round(zoom * 100)}%
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleZoomIn}
                    disabled={zoom >= 3}
                  >
                    <ZoomIn className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResetZoom}
                  >
                    Reset
                  </Button>
                </>
              )}
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex"
              >
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Open
                </Button>
              </a>
              <a href={downloadUrl} download className="inline-flex">
                <Button variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-1" />
                  Download
                </Button>
              </a>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-auto bg-gray-100 flex items-center justify-center p-4">
            {isImage ? (
              <div 
                className="transition-transform duration-200 ease-out"
                style={{ transform: `scale(${zoom})` }}
              >
                <img
                  src={downloadUrl}
                  alt={displayName}
                  className="max-w-full h-auto rounded-lg shadow-lg"
                  style={{ maxHeight: '80vh' }}
                />
              </div>
            ) : isPdf ? (
              <iframe
                src={`${downloadUrl}#view=FitH`}
                className="w-full h-full rounded-lg shadow-lg bg-white"
                title={displayName}
              />
            ) : (
              <div className="text-center text-gray-500">
                <FileText className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                <p className="mb-4">Preview not available for this file type</p>
                <a href={downloadUrl} download>
                  <Button>
                    <Download className="h-4 w-4 mr-2" />
                    Download File
                  </Button>
                </a>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Simpler inline link version for tables
export function ReceiptLink({ 
  expenseId,
  documentId 
}: { 
  expenseId?: string;
  documentId?: string;
}) {
  return (
    <ReceiptViewer 
      expenseId={expenseId} 
      documentId={documentId}
      trigger={
        <span className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm cursor-pointer">
          <FileText className="h-3.5 w-3.5" />
          View
        </span>
      }
    />
  );
}
