'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/hooks/use-auth';
import { apiClient } from '@/lib/api-client';
import { useShares } from '@/lib/hooks/use-shares';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, UserPlus, Users } from 'lucide-react';

interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  tax_rate: number | null;
  mortgage_interest_rate: number | null;
  loc_interest_rate: number | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    tax_rate: '',
    mortgage_interest_rate: '',
    loc_interest_rate: '',
    is_active: true,
  });

  // Sharing state
  const {
    shares,
    sharedWithMe,
    sharedUsers,
    loading: sharesLoading,
    error: sharesError,
    createShare,
    deleteShare,
    fetchShares,
    fetchSharedWithMe,
    fetchSharedUsers,
  } = useShares();
  const [newShareEmail, setNewShareEmail] = useState('');
  const [shareSuccess, setShareSuccess] = useState('');
  const [shareError, setShareError] = useState('');

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      
      // Fetch all data in parallel
      const [profileData] = await Promise.all([
        apiClient.get<UserProfile>('/users/me'),
        fetchShares(),
        fetchSharedWithMe(),
        fetchSharedUsers(),
      ]);
      
      setProfile(profileData);
      setFormData({
        first_name: profileData.first_name || '',
        last_name: profileData.last_name || '',
        tax_rate: profileData.tax_rate?.toString() || '0.22',
        mortgage_interest_rate: profileData.mortgage_interest_rate?.toString() || '0.07',
        loc_interest_rate: profileData.loc_interest_rate?.toString() || '0.07',
        is_active: profileData.is_active ?? true,
      });
    } catch (err) {
      console.error('Failed to fetch profile:', err);
      setError('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<UserProfile>('/users/me');
      setProfile(data);
      setFormData({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        tax_rate: data.tax_rate?.toString() || '0.22', // Use decimal format (0.22 not 22)
        mortgage_interest_rate: data.mortgage_interest_rate?.toString() || '0.07',
        loc_interest_rate: data.loc_interest_rate?.toString() || '0.07',
        is_active: data.is_active ?? true,
      });
    } catch (err) {
      console.error('Failed to fetch profile:', err);
      setError('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setSaving(true);

    try {
      const updateData: any = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        tax_rate: parseFloat(formData.tax_rate) || null,
        mortgage_interest_rate: parseFloat(formData.mortgage_interest_rate) || null,
        loc_interest_rate: parseFloat(formData.loc_interest_rate) || null,
        is_active: formData.is_active,
      };

      const updated = await apiClient.put<UserProfile>('/users/me', updateData);
      setProfile(updated);
      setSuccess(true);
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update profile:', err);
      setError('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleAddShare = async (e: React.FormEvent) => {
    e.preventDefault();
    setShareError('');
    setShareSuccess('');
    
    if (!newShareEmail.trim()) {
      setShareError('Please enter an email address');
      return;
    }

    try {
      await createShare(newShareEmail.trim());
      setNewShareEmail('');
      setShareSuccess(`Successfully added ${newShareEmail}`);
      setTimeout(() => setShareSuccess(''), 3000);
    } catch (err) {
      setShareError(err instanceof Error ? err.message : 'Failed to add share');
    }
  };

  const handleDeleteShare = async (shareId: string, email: string) => {
    if (!confirm(`Remove sharing with ${email}?`)) {
      return;
    }

    try {
      await deleteShare(shareId);
      setShareSuccess(`Removed sharing with ${email}`);
      setTimeout(() => setShareSuccess(''), 3000);
    } catch (err) {
      setShareError(err instanceof Error ? err.message : 'Failed to remove share');
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-gray-500">Loading profile...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-8">
        <div className="text-red-600">Failed to load profile</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* User Profile Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold">User Profile</CardTitle>
            <CardDescription className="text-xs">Manage your account information</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First Name</Label>
                    <Input
                      id="first_name"
                      type="text"
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last Name</Label>
                    <Input
                      id="last_name"
                      type="text"
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={profile.email}
                    disabled
                    className="bg-gray-100"
                  />
                  <p className="text-xs text-gray-500">Email cannot be changed</p>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="tax_rate">Tax Rate</Label>
                    <Input
                      id="tax_rate"
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={formData.tax_rate}
                      onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
                      placeholder="0.22"
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mortgage_interest_rate">30-Year Mortgage Rate</Label>
                    <Input
                      id="mortgage_interest_rate"
                      type="number"
                      step="0.0001"
                      min="0"
                      max="1"
                      value={formData.mortgage_interest_rate}
                      onChange={(e) => setFormData({ ...formData, mortgage_interest_rate: e.target.value })}
                      placeholder="0.07"
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="loc_interest_rate">Line of Credit Rate</Label>
                    <Input
                      id="loc_interest_rate"
                      type="number"
                      step="0.0001"
                      min="0"
                      max="1"
                      value={formData.loc_interest_rate}
                      onChange={(e) => setFormData({ ...formData, loc_interest_rate: e.target.value })}
                      placeholder="0.07"
                      className="font-mono text-sm"
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-500">Enter as decimal between 0 and 1 (e.g., 0.22 for 22%, 0.07 for 7%)</p>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <Label htmlFor="is_active" className="cursor-pointer">
                    Active Account
                  </Label>
                </div>
              </div>

              {error && (
                <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                  {error}
                </div>
              )}

              {success && (
                <div className="text-sm text-green-600 bg-green-50 p-3 rounded">
                  Profile updated successfully!
                </div>
              )}

              <Button
                type="submit"
                className="w-full bg-black text-white hover:bg-gray-800"
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </form>

            <div className="mt-8 pt-8 border-t border-gray-200">
              <div className="text-sm text-gray-600 space-y-2">
                <div>
                  <span className="font-medium">Account ID:</span> {profile.id}
                </div>
                <div>
                  <span className="font-medium">Account Created:</span>{' '}
                  {new Date(profile.created_at).toLocaleDateString()}
                </div>
                <div>
                  <span className="font-medium">Last Updated:</span>{' '}
                  {new Date(profile.updated_at).toLocaleDateString()}
                </div>
                <div>
                  <span className="font-medium">Status:</span>{' '}
                  <span className={profile.is_active ? 'text-green-600' : 'text-red-600'}>
                    {profile.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Property Sharing Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <Users className="h-5 w-5" />
              Property Sharing
            </CardTitle>
            <CardDescription className="text-xs">
              Share your properties with friends. When you add someone&apos;s email, both of you can see each other&apos;s properties.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Add Share Form */}
            <form onSubmit={handleAddShare} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="share_email">Add Friend&apos;s Email</Label>
                <div className="flex gap-2">
                  <Input
                    id="share_email"
                    type="email"
                    placeholder="friend@example.com"
                    value={newShareEmail}
                    onChange={(e) => setNewShareEmail(e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    type="submit"
                    disabled={sharesLoading}
                    className="bg-black text-white hover:bg-gray-800"
                  >
                    <UserPlus className="h-4 w-4 mr-2" />
                    Add
                  </Button>
                </div>
              </div>

              {shareError && (
                <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                  {shareError}
                </div>
              )}

              {shareSuccess && (
                <div className="text-sm text-green-600 bg-green-50 p-3 rounded">
                  {shareSuccess}
                </div>
              )}
            </form>

            {/* Current Shares */}
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-sm text-gray-700 mb-2">
                  People I&apos;m Sharing With ({shares.length})
                </h3>
                {shares.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    You haven&apos;t shared your properties with anyone yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {shares.map((share) => (
                      <div
                        key={share.id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded border"
                      >
                        <div>
                          <div className="font-medium">{share.shared_email}</div>
                          <div className="text-xs text-gray-500">
                            Added {new Date(share.created_at).toLocaleDateString()}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteShare(share.id, share.shared_email)}
                          disabled={sharesLoading}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h3 className="font-semibold text-sm text-gray-700 mb-2">
                  People Sharing With Me ({sharedWithMe.length})
                </h3>
                {sharedWithMe.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No one has shared their properties with you yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {sharedWithMe.map((share) => {
                      // Find the user info from sharedUsers
                      const sharedUser = sharedUsers.find(u => u.id === share.user_id);
                      return (
                        <div
                          key={share.id}
                          className="flex items-center justify-between p-3 bg-blue-50 rounded border border-blue-200"
                        >
                          <div>
                            <div className="font-medium">
                              {sharedUser ? `${sharedUser.first_name} ${sharedUser.last_name}` : 'Unknown User'}
                            </div>
                            <div className="text-sm text-gray-600">
                              {sharedUser?.email || share.user_id}
                            </div>
                            <div className="text-xs text-gray-500">
                              Shared {new Date(share.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div>
                <h3 className="font-semibold text-sm text-gray-700 mb-2">
                  Active Connections ({sharedUsers.length})
                </h3>
                <p className="text-xs text-gray-500 mb-2">
                  You can see properties from these users
                </p>
                {sharedUsers.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No active connections yet. Add someone&apos;s email above to get started!
                  </p>
                ) : (
                  <div className="space-y-2">
                    {sharedUsers.map((user) => (
                      <div
                        key={user.id}
                        className="flex items-center gap-3 p-3 bg-green-50 rounded border border-green-200"
                      >
                        <Users className="h-5 w-5 text-green-600" />
                        <div>
                          <div className="font-medium">
                            {user.first_name} {user.last_name}
                          </div>
                          <div className="text-sm text-gray-600">{user.email}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

