'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

interface ReceiptViewerProps {
  expenseId: string;
}

export function ReceiptViewer({ expenseId }: ReceiptViewerProps) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReceipt() {
      try {
        const response = await apiClient.get<{ download_url: string }>(
          `/expenses/${expenseId}/receipt`
        );
        setDownloadUrl(response.download_url);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    if (expenseId) {
      fetchReceipt();
    }
  }, [expenseId]);

  if (loading) {
    return <span className="text-gray-400">Loading...</span>;
  }

  if (error || !downloadUrl) {
    return <span className="text-red-500">Error loading receipt</span>;
  }

  const isImage = downloadUrl.match(/\.(jpg|jpeg|png|gif|webp)$/i);
  const isPdf = downloadUrl.match(/\.pdf$/i);

  return (
    <div className="inline-block">
      {isImage ? (
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline"
        >
          View Image
        </a>
      ) : isPdf ? (
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline"
        >
          View PDF
        </a>
      ) : (
        <a
          href={downloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline"
        >
          Download
        </a>
      )}
    </div>
  );
}

