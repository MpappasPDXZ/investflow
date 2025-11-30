'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks/use-auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function RegisterPage() {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [taxRate, setTaxRate] = useState('');
  const [mortgageRate, setMortgageRate] = useState('');
  const [locRate, setLocRate] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    // Validate tax rate if provided
    let taxRateValue: number | undefined = undefined;
    if (taxRate) {
      const parsed = parseFloat(taxRate);
      if (isNaN(parsed) || parsed < 0 || parsed > 1) {
        setError('Tax rate must be a number between 0 and 1 (e.g., 0.22 for 22%)');
        setLoading(false);
        return;
      }
      taxRateValue = parsed;
    }
    
    let mortgageRateValue: number | undefined = undefined;
    if (mortgageRate) {
      const parsed = parseFloat(mortgageRate);
      if (isNaN(parsed) || parsed < 0 || parsed > 1) {
        setError('Mortgage rate must be a number between 0 and 1 (e.g., 0.07 for 7%)');
        setLoading(false);
        return;
      }
      mortgageRateValue = parsed;
    }
    
    let locRateValue: number | undefined = undefined;
    if (locRate) {
      const parsed = parseFloat(locRate);
      if (isNaN(parsed) || parsed < 0 || parsed > 1) {
        setError('LOC rate must be a number between 0 and 1 (e.g., 0.07 for 7%)');
        setLoading(false);
        return;
      }
      locRateValue = parsed;
    }

    console.log('📝 [REGISTER] Form submitted');
    console.log('📧 Email:', email);
    console.log('👤 First Name:', firstName);
    console.log('👤 Last Name:', lastName);
    console.log('🔒 Password length:', password.length);
    console.log('💰 Tax Rate:', taxRateValue);
    console.log('💰 Mortgage Rate:', mortgageRateValue);
    console.log('💰 LOC Rate:', locRateValue);
    
    const result = await register(email, password, firstName, lastName, taxRateValue, mortgageRateValue, locRateValue);
    
    if (result.success) {
      console.log('✅ [REGISTER] Registration successful, redirecting...');
      router.push('/profile');
    } else {
      console.error('❌ [REGISTER] Registration failed:', result.error);
      setError(result.error || 'Registration failed');
    }
    
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Investment Cash Flow (ICF)</CardTitle>
          <CardDescription>Create a new account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firstName">First Name</Label>
                <Input
                  id="firstName"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastName">Last Name</Label>
                <Input
                  id="lastName"
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="taxRate">Tax Rate</Label>
                <Input
                  id="taxRate"
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={taxRate}
                  onChange={(e) => setTaxRate(e.target.value)}
                  placeholder="0.22"
                  className="font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mortgageRate">Mortgage Rate</Label>
                <Input
                  id="mortgageRate"
                  type="number"
                  step="0.0001"
                  min="0"
                  max="1"
                  value={mortgageRate}
                  onChange={(e) => setMortgageRate(e.target.value)}
                  placeholder="0.07"
                  className="font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="locRate">LOC Rate</Label>
                <Input
                  id="locRate"
                  type="number"
                  step="0.0001"
                  min="0"
                  max="1"
                  value={locRate}
                  onChange={(e) => setLocRate(e.target.value)}
                  placeholder="0.07"
                  className="font-mono text-sm"
                />
              </div>
            </div>
            <p className="text-xs text-gray-500">Enter rates as decimal (e.g., 0.22 for 22%, 0.07 for 7%)</p>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="font-mono text-sm"
              />
              <p className="text-xs text-gray-500">Must be at least 8 characters</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="font-mono text-sm"
              />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                {error}
              </div>
            )}
            <Button
              type="submit"
              className="w-full bg-black text-white hover:bg-gray-800"
              disabled={loading}
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
            <div className="text-center text-sm text-gray-600">
              Already have an account?{' '}
              <Link href="/login" className="text-black hover:underline font-medium">
                Sign in
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

