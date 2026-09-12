'use client';

import { useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/use-auth';
import {
  Sidebar as ShadcnSidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from '@/components/ui/sidebar';
import {
  Building2,
  FileSignature,
  Wallet,
  Lock,
  LogIn,
  LogOut,
  Home,
  Plus,
  Users,
  CheckCircle,
  ClipboardList,
  ClipboardCheck,
  Banknote,
  Receipt,
  FileText,
  Image,
  User,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

type HubId = 'properties' | 'leasing' | 'money' | 'vault';

type NavLink = {
  href: string;
  label: string;
  icon: LucideIcon;
  match?: (pathname: string, search: string) => boolean;
};

type Hub = {
  id: HubId;
  label: string;
  icon: LucideIcon;
  href: string;
  match: (pathname: string) => boolean;
  links: NavLink[];
};

const HUBS: Hub[] = [
  {
    id: 'properties',
    label: 'Properties',
    icon: Building2,
    href: '/properties',
    match: (p) => p.startsWith('/properties'),
    links: [
      { href: '/properties', label: 'All properties', icon: Home },
      { href: '/properties/add', label: 'Add property', icon: Plus },
    ],
  },
  {
    id: 'leasing',
    label: 'Leasing',
    icon: FileSignature,
    href: '/leases',
    match: (p) => p.startsWith('/leases') || p.startsWith('/leasing'),
    links: [
      { href: '/leasing/tenants', label: 'Tenant profiles', icon: Users },
      { href: '/leasing/background-check', label: 'Background check', icon: CheckCircle },
      { href: '/leasing/application', label: 'Application', icon: ClipboardList },
      { href: '/leases', label: 'Leases', icon: FileSignature },
      { href: '/leasing/inspections', label: 'Inspections', icon: ClipboardCheck },
    ],
  },
  {
    id: 'money',
    label: 'Money',
    icon: Wallet,
    href: '/rent',
    match: (p) => p.startsWith('/rent') || p.startsWith('/expenses'),
    links: [
      { href: '/rent', label: 'Rent ledger', icon: Banknote },
      { href: '/expenses', label: 'Expenses', icon: Receipt },
      { href: '/rent/log', label: 'Log rent', icon: Plus },
      { href: '/expenses/add', label: 'Add expense', icon: Plus },
    ],
  },
  {
    id: 'vault',
    label: 'Vault',
    icon: Lock,
    href: '/documents',
    match: (p) => p.startsWith('/documents'),
    links: [
      {
        href: '/documents?type=document',
        label: 'Documents',
        icon: FileText,
        match: (pathname, search) =>
          pathname.startsWith('/documents') &&
          !pathname.startsWith('/documents/add') &&
          !search.includes('type=photo'),
      },
      {
        href: '/documents?type=photo',
        label: 'Photos',
        icon: Image,
        match: (pathname, search) =>
          pathname.startsWith('/documents') &&
          !pathname.startsWith('/documents/add') &&
          search.includes('type=photo'),
      },
      { href: '/documents/add', label: 'Upload', icon: Plus },
    ],
  },
];

function linkIsActive(link: NavLink, pathname: string, search: string): boolean {
  if (link.match) return link.match(pathname, search);

  const [pathOnly] = link.href.split('?');
  if (pathOnly === '/properties') return pathname === '/properties';
  if (pathOnly === '/rent') {
    return pathname === '/rent' || pathname.startsWith('/rent/export');
  }
  if (pathOnly === '/expenses') {
    return (
      pathname === '/expenses' ||
      pathname.startsWith('/expenses/export') ||
      /^\/expenses\/[^/]+\/edit/.test(pathname)
    );
  }
  if (pathOnly === '/leases') {
    return pathname === '/leases' || pathname.startsWith('/leases/');
  }
  return pathname === pathOnly || pathname.startsWith(`${pathOnly}/`);
}

export function SidebarInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, logout, isAuthenticated } = useAuth();
  const search = searchParams?.toString() ? `?${searchParams.toString()}` : '';

  const activeHub = useMemo(
    () => HUBS.find((hub) => hub.match(pathname)) ?? null,
    [pathname],
  );

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <ShadcnSidebar className="border-r">
      <SidebarContent className="flex flex-col">
        <SidebarGroup className="flex-1">
          <Link
            href="/profile"
            className="mx-2 mt-2 mb-3 flex items-center gap-2.5 rounded-lg px-3 py-3 transition-colors hover:bg-gray-50"
          >
            <img
              src="/logo.png"
              alt="InvestFlow"
              className="h-8 w-8 flex-shrink-0 object-contain"
            />
            <span className="text-lg font-bold tracking-tight">
              <span className="text-gray-900">Invest</span>
              <span className="text-blue-600">Flow</span>
            </span>
          </Link>

          <SidebarGroupContent>
            <SidebarMenu className="gap-1 px-1">
              {isAuthenticated &&
                HUBS.map((hub) => {
                  const HubIcon = hub.icon;
                  const isHubActive = activeHub?.id === hub.id;

                  return (
                    <div key={hub.id} className="space-y-1">
                      <SidebarMenuItem>
                        <SidebarMenuButton
                          asChild
                          isActive={isHubActive}
                          className={cn(
                            'h-10 text-sm font-medium',
                            isHubActive &&
                              'bg-blue-50 text-blue-900 hover:bg-blue-50 hover:text-blue-900',
                          )}
                        >
                          <Link href={hub.href}>
                            <HubIcon className="h-4 w-4" />
                            <span>{hub.label}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>

                      {isHubActive && (
                        <div className="mx-2 mb-2 rounded-lg border border-gray-200 bg-gray-50/80 p-1.5">
                          <div className="px-2 pb-1 pt-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                            In {hub.label}
                          </div>
                          <div className="space-y-0.5">
                            {hub.links.map((link) => {
                              const LinkIcon = link.icon;
                              const active = linkIsActive(link, pathname, search);
                              return (
                                <SidebarMenuItem key={link.href + link.label}>
                                  <SidebarMenuButton
                                    asChild
                                    isActive={active}
                                    className={cn(
                                      'h-8 text-[12px]',
                                      active && 'bg-white text-gray-900 shadow-sm',
                                    )}
                                  >
                                    <Link href={link.href}>
                                      <LinkIcon className="h-3.5 w-3.5" />
                                      <span>{link.label}</span>
                                    </Link>
                                  </SidebarMenuButton>
                                </SidebarMenuItem>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

              {!isAuthenticated && (
                <SidebarMenuItem>
                  <SidebarMenuButton asChild>
                    <Link href="/login">
                      <LogIn className="h-4 w-4" />
                      <span>Login</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {isAuthenticated && (
          <div className="mt-auto border-t px-3 py-3">
            <Link
              href="/profile"
              className={cn(
                'mb-2 flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors hover:bg-gray-50',
                pathname.startsWith('/profile') && 'bg-gray-50 font-medium',
              )}
            >
              <User className="h-4 w-4 text-gray-500" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium text-gray-900">
                  {user?.email ?? 'Profile'}
                </div>
                <div className="text-[10px] text-gray-500">Account</div>
              </div>
            </Link>
            <Button
              variant="ghost"
              className="h-8 w-full justify-start text-xs text-gray-600"
              onClick={handleLogout}
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Log out</span>
            </Button>
          </div>
        )}
      </SidebarContent>
    </ShadcnSidebar>
  );
}
