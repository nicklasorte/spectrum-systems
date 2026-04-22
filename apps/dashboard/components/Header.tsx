'use client';

import { useState } from 'react';

interface HeaderProps {
  autoRefresh: number;
  onRefreshChange: (seconds: number) => void;
}

export function Header({ autoRefresh, onRefreshChange }: HeaderProps) {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <header className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">SS</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Spectrum Systems
          </h1>
          <span className="text-sm text-gray-500 ml-2">Dashboard</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition"
            >
              ⚙️ Settings
            </button>

            {showSettings && (
              <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                <div className="p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Auto-refresh (seconds)
                    </label>
                    <select
                      value={autoRefresh}
                      onChange={(e) =>
                        onRefreshChange(parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    >
                      <option value="15">15 seconds</option>
                      <option value="30">30 seconds</option>
                      <option value="60">1 minute</option>
                      <option value="300">5 minutes</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition"
          >
            ↻ Refresh
          </button>
        </div>
      </div>
    </header>
  );
}
