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
import { Building2, Receipt, LogIn, LogOut, Plus, List, FileDown, Home, FileText, User, Lock, Image, Droplet, Banknote, Wallet, FileSignature } from 'lucide-react';
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
          {/* Clickable Logo/Title - 20% larger, goes to profile */}
          <Link href="/profile" className="block px-3 py-4 hover:bg-gray-50 transition-colors rounded-lg cursor-pointer">
            <div className="flex items-center gap-2.5">
              <img 
                src="/logo.png" 
                alt="InvestFlow" 
                className="h-8 w-8 object-contain flex-shrink-0"
              />
              <span className="text-xl font-bold">
                <span className="text-gray-900">Invest</span>
                <span className="text-blue-600">Flow</span>
              </span>
            </div>
          </Link>
          
          <SidebarGroupContent>
            <SidebarMenu>
              {isAuthenticated && (
                <>
                  {/* Property Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-[14px] font-bold text-gray-700">
                      <Home className="h-3.5 w-3.5 inline mr-1" />
                      Property
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/properties/add">
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add Property</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/properties">
                        <List className="h-3.5 w-3.5" />
                        <span>View Properties</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Leases Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-[14px] font-bold text-gray-700">
                      <FileSignature className="h-3.5 w-3.5 inline mr-1" />
                      Leases
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/leases/create">
                        <Plus className="h-3.5 w-3.5" />
                        <span>Create Lease</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/leases">
                        <List className="h-3.5 w-3.5" />
                        <span>View Leases</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Rent Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-[14px] font-bold text-gray-700">
                      <Banknote className="h-3.5 w-3.5 inline mr-1" />
                      Rent
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/rent/log">
                        <Plus className="h-3.5 w-3.5" />
                        <span>Log Rent</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/rent">
                        <List className="h-3.5 w-3.5" />
                        <span>View Rent</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Expense Section */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-[14px] font-bold text-gray-700">
                      <Wallet className="h-3.5 w-3.5 inline mr-1" />
                      Expense
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/expenses/add">
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add Expense</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/expenses">
                        <List className="h-3.5 w-3.5" />
                        <span>View Expenses</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/expenses/export">
                        <FileDown className="h-3.5 w-3.5" />
                        <span>Export Expenses</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Vault Section (Documents & Photos) */}
                  <SidebarMenuItem>
                    <SidebarGroupLabel className="text-[14px] font-bold text-gray-700">
                      <Lock className="h-3 w-3 inline mr-1" />
                      Vault
                    </SidebarGroupLabel>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/documents/add">
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add New</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/documents?type=document">
                        <FileText className="h-3.5 w-3.5" />
                        <span>Documents</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild className="text-[11px]">
                      <Link href="/documents?type=photo">
                        <Image className="h-3.5 w-3.5" />
                        <span>Photos</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>

                  {/* Spacer to push bottom items down */}
                  <div className="flex-1" />

                  {/* Logged in as - at bottom */}
                  <SidebarMenuItem className="mt-auto pt-4 border-t">
                    <div className="px-2 py-1.5 text-xs">
                      <div className="text-gray-500">Logged in as:</div>
                      <div className="text-xs text-gray-900 font-medium truncate">{user?.email}</div>
                    </div>
                  </SidebarMenuItem>

                  {/* Logout */}
                  <SidebarMenuItem>
                    <Button
                      variant="ghost"
                      className="w-full justify-start text-xs"
                      onClick={handleLogout}
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Logout</span>
                    </Button>
                  </SidebarMenuItem>
                </>
              )}
              
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
      </SidebarContent>
    </ShadcnSidebar>
  );
}

