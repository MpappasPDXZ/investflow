'use client';

import { Suspense } from 'react';
import { SidebarInner } from './SidebarInner';

/** Suspense boundary required for useSearchParams in the hub nav. */
export function Sidebar() {
  return (
    <Suspense
      fallback={
        <div className="flex h-svh w-[16rem] flex-col border-r bg-background p-4">
          <div className="h-8 w-32 animate-pulse rounded bg-gray-100" />
        </div>
      }
    >
      <SidebarInner />
    </Suspense>
  );
}
