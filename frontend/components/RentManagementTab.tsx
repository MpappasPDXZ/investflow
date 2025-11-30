'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Home, Save, AlertCircle } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  current_monthly_rent: number | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Property {
  id: string;
  vacancy_rate: number;
  property_type?: string;
  current_monthly_rent?: number;
}

interface Props {
  propertyId: string;
  property: Property;
  onPropertyUpdate: () => void;
}

export default function RentManagementTab({ propertyId, property, onPropertyUpdate }: Props) {
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [vacancyRate, setVacancyRate] = useState((property.vacancy_rate * 100).toFixed(1));
  const [rentChanges, setRentChanges] = useState<{ [key: string]: string }>({});
  const [singleUnitRent, setSingleUnitRent] = useState(property.current_monthly_rent?.toString() || '');

  const isMultiUnit = property.property_type === 'multi_family' || property.property_type === 'duplex';

  useEffect(() => {
    if (isMultiUnit) {
      fetchUnits();
    }
  }, [propertyId, isMultiUnit]);

  const fetchUnits = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${propertyId}`);
      setUnits(response.items);
      
      // Initialize rent changes with current values
      const initialRents: { [key: string]: string } = {};
      response.items.forEach(unit => {
        initialRents[unit.id] = unit.current_monthly_rent?.toString() || '';
      });
      setRentChanges(initialRents);
    } catch (err) {
      console.error('❌ [RENT] Error fetching units:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRentChange = (unitId: string, value: string) => {
    setRentChanges(prev => ({
      ...prev,
      [unitId]: value
    }));
  };

  const handleSaveAll = async () => {
    try {
      setSaving(true);

      // Update property vacancy rate
      await apiClient.put(`/properties/${propertyId}`, {
        vacancy_rate: parseFloat(vacancyRate) / 100
      });

      if (isMultiUnit) {
        // Update all units
        const updatePromises = units.map(unit => {
          const newRent = rentChanges[unit.id];
          if (newRent !== undefined && newRent !== '') {
            return apiClient.put(`/units/${unit.id}`, {
              current_monthly_rent: parseFloat(newRent)
            });
          }
          return Promise.resolve();
        });

        await Promise.all(updatePromises);
        console.log('✅ [RENT] All units updated successfully');
        await fetchUnits();
      } else {
        // Update single-unit property
        if (singleUnitRent) {
          await apiClient.put(`/properties/${propertyId}`, {
            current_monthly_rent: parseFloat(singleUnitRent)
          });
          console.log('✅ [RENT] Property rent updated successfully');
        }
      }

      onPropertyUpdate();
      alert('All rent details updated successfully!');
    } catch (err) {
      console.error('❌ [RENT] Error saving:', err);
      alert(`Failed to save rent changes: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const totalMonthlyRent = isMultiUnit
    ? units.reduce((sum, unit) => {
        const rent = parseFloat(rentChanges[unit.id] || '0');
        return sum + (isNaN(rent) ? 0 : rent);
      }, 0)
    : parseFloat(singleUnitRent || '0');

  const annualRent = totalMonthlyRent * 12;
  const effectiveAnnualRent = annualRent * (1 - parseFloat(vacancyRate || '0') / 100);

  return (
    <div className="space-y-6">
      {/* Vacancy Rate Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            Vacancy Rate
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="max-w-xs">
              <Label htmlFor="vacancy_rate">Expected Vacancy Rate (%)</Label>
              <Input
                id="vacancy_rate"
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={vacancyRate}
                onChange={(e) => setVacancyRate(e.target.value)}
                className="text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">
                Used to calculate effective annual rent (default: 7%)
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Rent Management Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Home className="h-4 w-4" />
            {isMultiUnit ? 'Unit Rent' : 'Monthly Rent'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-gray-500 py-4">Loading units...</div>
          ) : (
            <div className="space-y-4">
              {isMultiUnit ? (
                <>
                  {units.length === 0 ? (
                    <div className="text-gray-500 py-8 text-center">
                      No units found. Add units in the Details & Units tab first.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {units.map((unit) => (
                        <div key={unit.id} className="flex items-center gap-4 p-3 bg-gray-50 rounded">
                          <div className="flex-1">
                            <div className="font-medium text-sm">{unit.unit_number}</div>
                            {unit.bedrooms !== null && unit.bathrooms !== null && (
                              <div className="text-xs text-gray-600">
                                {unit.bedrooms} bed, {unit.bathrooms} bath
                                {unit.square_feet && ` • ${unit.square_feet.toLocaleString()} sq ft`}
                              </div>
                            )}
                          </div>
                          <div className="w-48">
                            <Label htmlFor={`rent_${unit.id}`} className="text-xs">Monthly Rent</Label>
                            <Input
                              id={`rent_${unit.id}`}
                              type="number"
                              step="0.01"
                              min="0"
                              value={rentChanges[unit.id] || ''}
                              onChange={(e) => handleRentChange(unit.id, e.target.value)}
                              placeholder="Enter rent"
                              className="text-sm"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="max-w-xs">
                  <Label htmlFor="single_unit_rent">Monthly Rent</Label>
                  <Input
                    id="single_unit_rent"
                    type="number"
                    step="0.01"
                    min="0"
                    value={singleUnitRent}
                    onChange={(e) => setSingleUnitRent(e.target.value)}
                    placeholder="Enter monthly rent"
                    className="text-sm"
                  />
                </div>
              )}

              {/* Summary */}
              {(isMultiUnit ? units.length > 0 : singleUnitRent) && (
                <div className="border-t pt-4 mt-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Total Monthly Rent:</span>
                      <span className="font-semibold">
                        ${totalMonthlyRent.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Gross Annual Rent:</span>
                      <span className="font-semibold">
                        ${annualRent.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Vacancy ({vacancyRate}%):</span>
                      <span className="font-semibold text-red-600">
                        -${(annualRent - effectiveAnnualRent).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between text-base font-bold pt-2 border-t">
                      <span>Effective Annual Rent:</span>
                      <span className="text-green-700">
                        ${effectiveAnnualRent.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSaveAll}
          disabled={saving || (isMultiUnit && units.length === 0)}
          className="bg-black text-white hover:bg-gray-800 h-10"
        >
          <Save className="h-4 w-4 mr-2" />
          {saving ? 'Saving...' : isMultiUnit ? 'Update All Unit Rent & Vacancy' : 'Update Rent & Vacancy'}
        </Button>
      </div>
    </div>
  );
}

