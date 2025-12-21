'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/**
 * Redirect /leases/create to /leases
 * This page is kept for backward compatibility with existing links.
 * All lease creation/editing is now handled on the main /leases page.
 */
export default function LeaseCreateRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  useEffect(() => {
    // Preserve any query parameters (like lease_id or property_id)
    const params = searchParams.toString();
    const destination = params ? `/leases?${params}` : '/leases';
    router.replace(destination);
  }, [router, searchParams]);
  
  return (
    <div className="flex items-center justify-center h-[calc(100vh-200px)]">
      <div className="text-center text-gray-500">
        <p>Redirecting to leases...</p>
      </div>
    </div>
  );
}
