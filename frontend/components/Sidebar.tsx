'use client';

import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/use-auth';
import { memo, useState } from 'react';
import {
  Sidebar as ShadcnSidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  SidebarFooter,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar';
import { 
  Building2, 
  Receipt, 
  LogIn, 
  LogOut, 
  Plus, 
  Table, 
  FileDown, 
  Zap, 
  FolderOpen,
  DollarSign,
  ChevronRight,
  User,
} from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

interface NavSection {
  title: string;
  icon: React.ElementType;
  items: {
    title: string;
    href: string;
    icon?: React.ElementType;
  }[];
}

function SidebarComponent() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isAuthenticated } = useAuth();
  const { state } = useSidebar();
  
  // Track which sections are open
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    property: true,
    rent: true,
    expense: true,
    documents: true,
  });

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const navSections: NavSection[] = [
    {
      title: 'Property',
      icon: Building2,
      items: [
        { title: 'Add', href: '/properties/add', icon: Plus },
        { title: 'View', href: '/properties', icon: Table },
      ],
    },
    {
      title: 'Rent',
      icon: DollarSign,
      items: [
        { title: 'Log', href: '/rent/log', icon: Plus },
        { title: 'View', href: '/rent', icon: Table },
      ],
    },
    {
      title: 'Expenses',
      icon: Receipt,
      items: [
        { title: 'Add', href: '/expenses/add', icon: Plus },
        { title: 'View', href: '/expenses', icon: Table },
        { title: 'Export', href: '/expenses/export', icon: FileDown },
      ],
    },
    {
      title: 'Documents',
      icon: FolderOpen,
      items: [
        { title: 'View', href: '/documents', icon: Table },
      ],
    },
  ];

  const toggleSection = (key: string) => {
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const isActiveLink = (href: string) => pathname === href;
  const isSectionActive = (section: NavSection) => 
    section.items.some(item => pathname === item.href || pathname.startsWith(item.href + '/'));

  return (
    <ShadcnSidebar collapsible="icon" className="border-r">
      {/* Header with App Logo */}
      <SidebarHeader className="border-b">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/" className="flex items-center gap-2">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-blue-600 text-white">
                  <Zap className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold">InvestFlow</span>
                  <span className="text-xs text-muted-foreground">Property Manager</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {isAuthenticated && (
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {navSections.map((section) => {
                  const sectionKey = section.title.toLowerCase();
                  const isOpen = openSections[sectionKey];
                  const Icon = section.icon;
                  const sectionActive = isSectionActive(section);
                  
                  return (
                    <Collapsible
                      key={section.title}
                      open={isOpen}
                      onOpenChange={() => toggleSection(sectionKey)}
                      className="group/collapsible"
                    >
                      <SidebarMenuItem>
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton 
                            tooltip={section.title}
                            isActive={sectionActive && state === 'collapsed'}
                          >
                            <Icon className="size-4" />
                            <span>{section.title}</span>
                            <ChevronRight className={`ml-auto size-4 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`} />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <SidebarMenuSub>
                            {section.items.map((item) => {
                              const ItemIcon = item.icon;
                              return (
                                <SidebarMenuSubItem key={item.href}>
                                  <SidebarMenuSubButton 
                                    asChild 
                                    isActive={isActiveLink(item.href)}
                                    size="sm"
                                    className="justify-start"
                                  >
                                    <Link href={item.href} className="flex items-center gap-2" title={item.title}>
                                      {ItemIcon && <ItemIcon className="size-2.5" />}
                                      <span className="text-xs">{item.title}</span>
                                    </Link>
                                  </SidebarMenuSubButton>
                                </SidebarMenuSubItem>
                              );
                            })}
                          </SidebarMenuSub>
                        </CollapsibleContent>
                      </SidebarMenuItem>
                    </Collapsible>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      {/* Footer with User Info */}
      <SidebarFooter className="border-t">
        <SidebarMenu>
          {isAuthenticated ? (
            <>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip={user?.email || 'Profile'} size="sm">
                  <Link href="/profile" className="flex items-center gap-2">
                    <div className="flex size-6 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600">
                      {user?.email?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div className="flex flex-col leading-none">
                      <span className="text-xs font-medium truncate max-w-[120px]">
                        {user?.first_name || user?.email?.split('@')[0] || 'User'}
                      </span>
                      <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                        {user?.email}
                      </span>
                    </div>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Logout" onClick={handleLogout} size="sm">
                  <LogOut className="size-4" />
                  <span>Logout</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </>
          ) : (
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Login" size="sm">
                <Link href="/login">
                  <LogIn className="size-4" />
                  <span>Login</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </ShadcnSidebar>
  );
}

export const Sidebar = memo(SidebarComponent);
