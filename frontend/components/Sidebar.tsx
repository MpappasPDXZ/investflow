'use client';

import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/use-auth';
import {
  Sidebar as ShadcnSidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from '@/components/ui/sidebar';
import { Building2, Receipt, LogIn, LogOut, Plus, List, FileDown, Home, FileText, User } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isAuthenticated } = useAuth();

  const handleLogout = () => {
    console.log('🚪 [SIDEBAR] Logout clicked');
    logout();
    router.push('/login');
  };

  return (
    <ShadcnSidebar className="border-r">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>InvestFlow</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {/* Login Section */}
              <SidebarMenuItem>
                {isAuthenticated ? (
                  <div className="px-2 py-1.5 text-sm">
                    <div className="font-medium">Logged in as:</div>
                    <div className="text-xs text-gray-600 truncate">{user?.email}</div>
                  </div>
                ) : (
                  <SidebarMenuButton asChild>
                    <Link href="/login">
                      <LogIn className="h-4 w-4" />
                      <span>Login</span>
                    </Link>
                  </SidebarMenuButton>
                )}
              </SidebarMenuItem>

              {isAuthenticated && (
                <>
                  {/* Property Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-xs font-semibold text-gray-500">
                      Property
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/properties/add">
                        <Plus className="h-4 w-4" />
                        <span>Add Property</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/properties">
                        <List className="h-4 w-4" />
                        <span>View Properties</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Rent Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-xs font-semibold text-gray-500">
                      Rent
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/rent/log">
                        <Plus className="h-4 w-4" />
                        <span>Log Rent</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/rent">
                        <List className="h-4 w-4" />
                        <span>View Rent</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Expense Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-xs font-semibold text-gray-500">
                      Expense
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/expenses/add">
                        <Plus className="h-4 w-4" />
                        <span>Add Expense</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/expenses">
                        <List className="h-4 w-4" />
                        <span>View Expenses</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/expenses/export">
                        <FileDown className="h-4 w-4" />
                        <span>Export Expenses</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Documents Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-xs font-semibold text-gray-500">
                      Documents
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/documents/add">
                        <Plus className="h-4 w-4" />
                        <span>Add Document</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/documents">
                        <FileText className="h-4 w-4" />
                        <span>View Documents</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Profile Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-xs font-semibold text-gray-500">
                      Account
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/profile">
                        <User className="h-4 w-4" />
                        <span>Profile</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Logout */}
                  <SidebarMenuItem className="mt-auto pt-4">
                    <Button
                      variant="ghost"
                      className="w-full justify-start"
                      onClick={handleLogout}
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Logout</span>
                    </Button>
                  </SidebarMenuItem>
                </>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </ShadcnSidebar>
  );
}

