'use client';

import { useState, useEffect, useRef } from 'react';
import { apiClient } from '@/lib/api-client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FileText, Download, ExternalLink, ZoomIn, ZoomOut, X, Loader2, RotateCcw } from 'lucide-react';

interface ReceiptViewerProps {
  expenseId?: string;
  documentId?: string;
  downloadUrl?: string;
  fileName?: string;
  fileType?: string;
  trigger?: React.ReactNode;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function ReceiptViewer({ 
  expenseId, 
  documentId,
  downloadUrl: propDownloadUrl, 
  fileName,
  fileType,
  trigger,
  defaultOpen = false,
  onOpenChange,
}: ReceiptViewerProps) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(propDownloadUrl || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // Sync with defaultOpen prop
  useEffect(() => {
    setIsOpen(defaultOpen);
  }, [defaultOpen]);
  const [zoom, setZoom] = useState(1);
  const [imageLoading, setImageLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // LAZY LOADING: Only fetch when dialog opens
  useEffect(() => {
    async function fetchReceipt() {
      if (propDownloadUrl) {
        setDownloadUrl(propDownloadUrl);
        setLoading(false);
        return;
      }

      if (!isOpen) {
        return; // Don't fetch until user opens the dialog
      }

      if (downloadUrl) {
        return; // Already fetched
      }

      setLoading(true);
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

    fetchReceipt();
  }, [isOpen, expenseId, documentId, propDownloadUrl, downloadUrl]);

  // Reset zoom when dialog opens
  useEffect(() => {
    if (isOpen) {
      setZoom(1);
      setImageLoading(true);
    }
  }, [isOpen]);

  const isImage = downloadUrl?.match(/\.(jpg|jpeg|png|gif|webp|heic|heif)/i) || 
                  fileType?.startsWith('image/');
  const isPdf = downloadUrl?.match(/\.pdf/i) || 
                fileType === 'application/pdf';

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => setZoom(1);

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

      <Dialog open={isOpen} onOpenChange={(open) => {
        setIsOpen(open);
        onOpenChange?.(open);
      }}>
        <DialogContent className="max-w-5xl w-[95vw] h-[90vh] md:h-[85vh] flex flex-col p-0 gap-0">
          {/* Header - Responsive */}
          <DialogHeader className="px-4 md:px-6 py-3 md:py-4 border-b bg-gray-50 shrink-0">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <DialogTitle className="flex items-center gap-2 text-base md:text-lg font-semibold truncate">
                <FileText className="h-5 w-5 shrink-0" />
                <span className="truncate">{displayName}</span>
              </DialogTitle>
              
              {/* Action buttons - scrollable on mobile */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 -mx-1 px-1">
                {isImage && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleZoomOut}
                      disabled={zoom <= 0.5}
                      className="h-9 w-9 p-0 shrink-0"
                    >
                      <ZoomOut className="h-4 w-4" />
                    </Button>
                    <span className="text-sm text-gray-600 min-w-[3rem] text-center shrink-0">
                      {Math.round(zoom * 100)}%
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleZoomIn}
                      disabled={zoom >= 3}
                      className="h-9 w-9 p-0 shrink-0"
                    >
                      <ZoomIn className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleResetZoom}
                      className="h-9 px-2 shrink-0"
                    >
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                  </>
                )}
                <a
                  href={downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0"
                >
                  <Button variant="outline" size="sm" className="h-9 px-3">
                    <ExternalLink className="h-4 w-4 md:mr-1" />
                    <span className="hidden md:inline">Open</span>
                  </Button>
                </a>
                <a href={downloadUrl} download className="inline-flex shrink-0">
                  <Button variant="outline" size="sm" className="h-9 px-3">
                    <Download className="h-4 w-4 md:mr-1" />
                    <span className="hidden md:inline">Download</span>
                  </Button>
                </a>
              </div>
            </div>
          </DialogHeader>

          {/* Content - Touch-friendly with native scroll/zoom on mobile */}
          <div 
            ref={containerRef}
            className="flex-1 overflow-auto bg-gray-100 flex items-start md:items-center justify-center p-2 md:p-4 touch-pan-x touch-pan-y"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            {loading ? (
              <div className="flex flex-col items-center justify-center gap-3 py-12">
                <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
                <p className="text-gray-500">Loading document...</p>
              </div>
            ) : error || !downloadUrl ? (
              <div className="flex flex-col items-center justify-center gap-3 py-12">
                <FileText className="h-16 w-16 text-red-400" />
                <p className="text-red-500">Failed to load document</p>
                <p className="text-sm text-gray-500">{error || 'No download URL available'}</p>
              </div>
            ) : isImage ? (
              <div 
                className="transition-transform duration-200 ease-out w-full flex justify-center"
                style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
              >
                {imageLoading && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                  </div>
                )}
                <img
                  src={downloadUrl}
                  alt={displayName}
                  className="max-w-full h-auto rounded-lg shadow-lg"
                  style={{ 
                    maxHeight: zoom === 1 ? '100%' : 'none',
                    opacity: imageLoading ? 0 : 1,
                    transition: 'opacity 0.2s'
                  }}
                  onLoad={() => setImageLoading(false)}
                  onError={() => setImageLoading(false)}
                />
              </div>
            ) : isPdf ? (
              <div className="w-full h-full flex flex-col">
                {/* On iOS, PDFs in iframes can be problematic, offer download as fallback */}
                <div className="md:hidden text-center py-8">
                  <FileText className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                  <p className="text-gray-600 mb-4">PDF preview works best on desktop</p>
                  <div className="flex flex-col gap-3 items-center">
                    <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
                      <Button className="min-h-[44px]">
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Open in New Tab
                      </Button>
                    </a>
                    <a href={downloadUrl} download>
                      <Button variant="outline" className="min-h-[44px]">
                        <Download className="h-4 w-4 mr-2" />
                        Download PDF
                      </Button>
                    </a>
                  </div>
                </div>
                {/* Desktop PDF viewer */}
                <iframe
                  src={`${downloadUrl}#view=FitH`}
                  className="hidden md:block w-full h-full rounded-lg shadow-lg bg-white"
                  title={displayName}
                />
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                <FileText className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                <p className="mb-4">Preview not available for this file type</p>
                <a href={downloadUrl} download>
                  <Button className="min-h-[44px]">
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
