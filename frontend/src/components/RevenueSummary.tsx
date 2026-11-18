import React, { useEffect, useState } from 'react';
import { SecureAPI, type DashboardSummary } from '../lib/secureApi';

interface RevenueSummaryProps {
  propertyId: string;
  month?: number;
  year?: number;
}

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({ propertyId, month, year }) => {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    setLoading(true);

    SecureAPI.getDashboardSummary(propertyId, { month, year })
      .then((response) => {
        if (active) setData(response);
      })
      .catch(() => {
        if (active) setError('Unable to load revenue. Please try again.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [propertyId, month, year]);

  if (loading) return <p role="status" className="p-6 text-gray-500">Loading revenue...</p>;
  if (error) return <p role="alert" className="p-4 text-red-600 bg-red-50 rounded-lg">{error}</p>;
  if (!data) return null;

  // Add grouping separators without converting the exact decimal string to a float.
  const [whole, cents] = data.total_revenue.split('.');
  const displayTotal = `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Total Revenue</h2>
      <p className="text-3xl font-bold text-gray-900 mt-1 mb-6" data-testid="revenue-total">
        {data.currency} {displayTotal}
      </p>
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
        <div>
          <p className="text-xs text-gray-500 uppercase">Property ID</p>
          <p className="text-sm font-semibold text-gray-700 mt-1">{data.property_id}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">Reservations</p>
          <p className="text-sm font-semibold text-gray-700 mt-1" data-testid="reservation-count">
            {data.reservations_count} bookings
          </p>
        </div>
      </div>
      <p className="mt-4 text-xs text-gray-500">
        Revenue is recognized on check-in. Reporting timezone: {data.timezone}.
      </p>
    </div>
  );
};
