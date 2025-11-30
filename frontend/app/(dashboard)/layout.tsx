'use client';

import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { Sidebar } from '@/components/Sidebar';
import { useAuth } from '@/lib/hooks/use-auth';
import { useRouter } from 'next/navigation';
import { useEffect, memo } from 'react';

function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, loading]); // Remove router from dependencies

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <SidebarProvider>
      <Sidebar />
      <SidebarInset className="flex-1">
        <div className="min-h-screen bg-gray-50">
          {/* Sidebar Toggle Header */}
          <header className="sticky top-0 z-10 flex h-10 items-center gap-2 border-b bg-white px-3">
            <SidebarTrigger className="h-7 w-7" />
          </header>
          <main>
            {children}
          </main>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default memo(DashboardLayout);

