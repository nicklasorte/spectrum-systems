'use client';

import { useState, useEffect } from 'react';

interface QueryDrillDownProps {
  queryId: string;
  onClose: () => void;
}

export function QueryDrillDown({ queryId, onClose }: QueryDrillDownProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchQuery = async () => {
      try {
        const response = await fetch(`/api/queries/${queryId}`);
        const results = await response.json();
        setData(results);
      } catch (error) {
        console.error('Query failed:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchQuery();
  }, [queryId]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-96 overflow-y-auto">
        <div className="sticky top-0 bg-gray-100 px-6 py-4 flex justify-between items-center border-b">
          <h2 className="text-lg font-semibold capitalize">{queryId}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 font-bold text-2xl"
          >
            ✕
          </button>
        </div>

        <div className="p-6">
          {loading && <p className="text-gray-600">Loading...</p>}

          {!loading && data && (
            <pre className="bg-gray-50 p-4 rounded text-xs overflow-x-auto">
              {JSON.stringify(data, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
