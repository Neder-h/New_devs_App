import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext.new';
import { SecureAPI, type DashboardProperty } from '../lib/secureApi';
import { RevenueSummary } from './RevenueSummary';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  // Remount account-specific state immediately when the authenticated identity changes.
  return <DashboardContent key={`${user?.id}:${user?.tenant_id}`} />;
};

function DashboardContent() {
  const [properties, setProperties] = useState<DashboardProperty[]>([]);
  const [selectedProperty, setSelectedProperty] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [period, setPeriod] = useState('monthly');
  // The supplied reservation fixtures are from March 2024.
  const [selectedMonth, setSelectedMonth] = useState('2024-03');
  const [selectedYear, setSelectedYear] = useState('2024');

  useEffect(() => {
    let active = true;
    SecureAPI.getDashboardProperties()
      .then((items) => {
        if (!active) return;
        setProperties(items);
        setSelectedProperty(items[0]?.id || '');
      })
      .catch(() => {
        if (active) setError('Unable to load your properties. Please try again.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const year = period === 'monthly' ? Number(selectedMonth.split('-')[0])
    : period === 'annual' ? Number(selectedYear) : undefined;
  const month = period === 'monthly' ? Number(selectedMonth.split('-')[1]) : undefined;
  const validPeriod = period === 'all' || (
    Number.isInteger(year) && year! >= 1 && year! <= 9998
    && (period === 'annual' || (Number.isInteger(month) && month! >= 1 && month! <= 12))
  );
  const inputClass = 'block w-full mt-1 px-3 py-2 border border-gray-300 rounded-md text-sm';

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <h2 className="text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
          <p className="text-gray-600 mb-6">Revenue for your properties by reporting period.</p>

          <div className="grid gap-4 sm:grid-cols-3 mb-6">
            <label className="text-sm font-medium text-gray-700">
              Select Property
              <select className={inputClass} value={selectedProperty}
                onChange={(event) => setSelectedProperty(event.target.value)} disabled={loading}>
                {properties.map((property) => (
                  <option key={property.id} value={property.id}>{property.name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium text-gray-700">
              Report period
              <select className={inputClass} value={period} onChange={(event) => setPeriod(event.target.value)}>
                <option value="monthly">Monthly</option>
                <option value="annual">Annual</option>
                <option value="all">All time</option>
              </select>
            </label>
            {period === 'monthly' && (
              <label className="text-sm font-medium text-gray-700">
                Month
                <input className={inputClass} type="month" min="0001-01" max="9998-12"
                  value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} />
              </label>
            )}
            {period === 'annual' && (
              <label className="text-sm font-medium text-gray-700">
                Year
                <input className={inputClass} type="number" min="1" max="9998"
                  value={selectedYear} onChange={(event) => setSelectedYear(event.target.value)} />
              </label>
            )}
          </div>

          {loading && <p role="status">Loading properties...</p>}
          {error && <p role="alert" className="text-red-600">{error}</p>}
          {!loading && !error && properties.length === 0 && <p>No properties available.</p>}
          {!validPeriod && <p role="alert">Select a valid reporting period.</p>}
          {selectedProperty && validPeriod && (
            <RevenueSummary key={`${selectedProperty}:${year}:${month}`}
              propertyId={selectedProperty} year={year} month={month} />
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
