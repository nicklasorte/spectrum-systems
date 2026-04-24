import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import RGEPage from '@/app/rge/page';

global.fetch = jest.fn();

describe('RGE Dashboard', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementationOnce(
      () => new Promise(() => {})
    );
    render(<RGEPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays trust mode', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ admitted_count: 2, blocked_count: 1, active_drift_legs: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ context_maturity_level: 8, entropy_vectors: {} }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ([]) });

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/WARN-GATED/)).toBeInTheDocument();
    });
  });

  it('displays maturity level', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ admitted_count: 0, blocked_count: 0, active_drift_legs: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ context_maturity_level: 8, entropy_vectors: {} }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ([]) });

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/8\/10/)).toBeInTheDocument();
    });
  });

  it('displays admitted and blocked phase counts', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ admitted_count: 5, blocked_count: 3, active_drift_legs: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ context_maturity_level: 8, entropy_vectors: {} }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ([]) });

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('displays active drift legs when present', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ admitted_count: 0, blocked_count: 0, active_drift_legs: ['EVL', 'OBS'] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ context_maturity_level: 8, entropy_vectors: {} }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ([]) });

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText('EVL')).toBeInTheDocument();
      expect(screen.getByText('OBS')).toBeInTheDocument();
    });
  });

  it('displays entropy vectors', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ admitted_count: 0, blocked_count: 0, active_drift_legs: [] }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          context_maturity_level: 8,
          entropy_vectors: {
            decision_entropy: 'clean',
            silent_drift: 'warn',
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ([]) });

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/decision entropy/i)).toBeInTheDocument();
      expect(screen.getByText(/silent drift/i)).toBeInTheDocument();
    });
  });

  it('handles API errors gracefully', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/error:/i)).toBeInTheDocument();
    });
  });
});
