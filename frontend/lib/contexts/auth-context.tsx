/**
 * Authentication Context Provider
 */
'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../api-client';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string, firstName: string, lastName: string, taxRate?: number, mortgageRate?: number, locRate?: number) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isAuthenticated: boolean;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on mount (only once!)
    const token = localStorage.getItem('auth_token');
    if (token) {
      fetchUserInfo();
    } else {
      setLoading(false);
    }
  }, []); // Empty dependency array - runs once on mount

  const fetchUserInfo = async () => {
    try {
      const userData = await apiClient.get<User>('/users/me');
      console.log('✅ [AUTH] User info fetched:', userData);
      setUser(userData);
    } catch (error) {
      console.error('❌ [AUTH] Failed to fetch user info:', error);
      localStorage.removeItem('auth_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    console.log('🔐 [AUTH] Logging in:', email);
    try {
      const response = await apiClient.post<{ access_token: string }>('/auth/login', {
        email,
        password,
      });
      
      console.log('✅ [AUTH] Login successful');
      localStorage.setItem('auth_token', response.access_token);
      await fetchUserInfo();
      
      return { success: true };
    } catch (error) {
      console.error('❌ [AUTH] Login failed:', error);
      return { success: false, error: (error as Error).message };
    }
  };

  const register = async (email: string, password: string, firstName: string, lastName: string, taxRate?: number, mortgageRate?: number, locRate?: number) => {
    console.log('📝 [AUTH] Registering user:', email);
    
    const payload: any = {
      email,
      password,
      first_name: firstName,
      last_name: lastName,
    };
    
    if (taxRate !== undefined) {
      payload.tax_rate = taxRate;
    }
    if (mortgageRate !== undefined) {
      payload.mortgage_interest_rate = mortgageRate;
    }
    if (locRate !== undefined) {
      payload.loc_interest_rate = locRate;
    }
    
    try {
      const response = await apiClient.post<{ access_token: string }>('/auth/register', payload);
      
      console.log('✅ [AUTH] Registration successful');
      localStorage.setItem('auth_token', response.access_token);
      await fetchUserInfo();
      
      return { success: true };
    } catch (error) {
      console.error('❌ [AUTH] Registration failed:', error);
      return { success: false, error: (error as Error).message };
    }
  };

  const logout = () => {
    console.log('🚪 [AUTH] Logging out');
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  const refreshUser = async () => {
    await fetchUserInfo();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        isAuthenticated: !!user,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

