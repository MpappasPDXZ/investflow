/**
 * Custom hook for managing property sharing
 */
'use client';

import { useState, useCallback } from 'react';
import { apiClient } from '../api-client';
import { UserShare, SharedUser } from '../types';

export interface UseSharesReturn {
  shares: UserShare[];
  sharedWithMe: UserShare[];
  sharedUsers: SharedUser[];
  loading: boolean;
  error: string | null;
  createShare: (email: string) => Promise<void>;
  deleteShare: (shareId: string) => Promise<void>;
  fetchShares: () => Promise<void>;
  fetchSharedWithMe: () => Promise<void>;
  fetchSharedUsers: () => Promise<void>;
}

export function useShares(): UseSharesReturn {
  const [shares, setShares] = useState<UserShare[]>([]);
  const [sharedWithMe, setSharedWithMe] = useState<UserShare[]>([]);
  const [sharedUsers, setSharedUsers] = useState<SharedUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchShares = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<UserShare[]>('/users/me/shares');
      setShares(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch shares';
      setError(errorMessage);
      console.error('Failed to fetch shares:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSharedWithMe = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<UserShare[]>('/users/me/shares/shared-with-me');
      setSharedWithMe(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch shared-with-me';
      setError(errorMessage);
      console.error('Failed to fetch shared-with-me:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSharedUsers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<SharedUser[]>('/users/shared');
      setSharedUsers(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch shared users';
      setError(errorMessage);
      console.error('Failed to fetch shared users:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const createShare = useCallback(async (email: string) => {
    try {
      setLoading(true);
      setError(null);
      await apiClient.post<UserShare>('/users/me/shares', { shared_email: email });
      // Refresh the shares list
      await fetchShares();
      await fetchSharedUsers();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create share';
      setError(errorMessage);
      console.error('Failed to create share:', err);
      throw err; // Re-throw to allow caller to handle
    } finally {
      setLoading(false);
    }
  }, [fetchShares, fetchSharedUsers]);

  const deleteShare = useCallback(async (shareId: string) => {
    try {
      setLoading(true);
      setError(null);
      await apiClient.delete(`/users/me/shares/${shareId}`);
      // Refresh the shares list
      await fetchShares();
      await fetchSharedUsers();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete share';
      setError(errorMessage);
      console.error('Failed to delete share:', err);
      throw err; // Re-throw to allow caller to handle
    } finally {
      setLoading(false);
    }
  }, [fetchShares, fetchSharedUsers]);

  return {
    shares,
    sharedWithMe,
    sharedUsers,
    loading,
    error,
    createShare,
    deleteShare,
    fetchShares,
    fetchSharedWithMe,
    fetchSharedUsers,
  };
}






