import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import RGEPage from '@/app/rge/page';

global.fetch = jest.fn();

const mockRoadmap = {
  admitted_count: 2,
  blocked_count: 1,
  active_drift_legs: [],
  step_count: 24,
  top_risks: [],
  data_source: 'artifact_store',
  warnings: [],
};

const mockAnalysis = {
  context_maturity_level: 8,
  wave_status: 3,
  entropy_vectors: {},
  rge_can_operate: true,
  rge_max_autonomy: 'warn_gated',
  mg_kernel_status: 'pass',
  mg_kernel_run_id: 'MG-KERNEL-24-01-TEST',
  manual_residue_steps: 2,
  dashboard_truth_status: 'verified',
  registry_alignment_status: 'aligned',
  active_drift_legs: [],
  data_source: 'artifact_store',
  warnings: [],
};

const mockProposals = {
  data_source: 'derived',
  warnings: [],
  proposals: [],
};

function setupFetchMock(
  roadmap = mockRoadmap,
  analysis = mockAnalysis,
  proposals = mockProposals
) {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => roadmap })
    .mockResolvedValueOnce({ ok: true, json: async () => analysis })
    .mockResolvedValueOnce({ ok: true, json: async () => proposals });
}

describe('RGE Dashboard', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementationOnce(() => new Promise(() => {}));
    render(<RGEPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays trust mode from rge_max_autonomy', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/WARN-GATED/i)).toBeInTheDocument();
    });
  });

  it('displays maturity level', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/8\/10/)).toBeInTheDocument();
    });
  });

  it('displays wave status', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/Wave 3/i)).toBeInTheDocument();
    });
  });

  it('displays governance signals panel', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/MG-KERNEL status/i)).toBeInTheDocument();
      expect(screen.getByText(/Manual residue steps/i)).toBeInTheDocument();
      expect(screen.getByText(/Dashboard truth/i)).toBeInTheDocument();
      expect(screen.getByText(/Registry alignment/i)).toBeInTheDocument();
    });
  });

  it('displays active drift legs when present', async () => {
    setupFetchMock(
      { ...mockRoadmap, active_drift_legs: [] },
      { ...mockAnalysis, active_drift_legs: ['EVL', 'OBS'] }
    );
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText('EVL')).toBeInTheDocument();
      expect(screen.getByText('OBS')).toBeInTheDocument();
    });
  });

  it('displays entropy vectors when present', async () => {
    setupFetchMock(mockRoadmap, {
      ...mockAnalysis,
      entropy_vectors: {
        decision_entropy: 'clean',
        silent_drift: 'warn',
      },
    });
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/decision entropy/i)).toBeInTheDocument();
      expect(screen.getByText(/silent drift/i)).toBeInTheDocument();
    });
  });

  it('renders warnings when data_source is stub_fallback', async () => {
    setupFetchMock(
      mockRoadmap,
      {
        ...mockAnalysis,
        data_source: 'stub_fallback',
        warnings: ['mg_kernel status unavailable: checkpoint_summary.json not found'],
      }
    );
    render(<RGEPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/mg_kernel status unavailable/i)
      ).toBeInTheDocument();
    });
  });

  it('shows warnings banner when warnings are present', async () => {
    setupFetchMock(
      mockRoadmap,
      {
        ...mockAnalysis,
        warnings: ['some-inference-warning'],
      }
    );
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('does not render any Execute button', async () => {
    setupFetchMock(mockRoadmap, mockAnalysis, {
      ...mockProposals,
      proposals: [
        {
          proposal_id: 'PROP-001',
          phase_id: 'RC-01',
          phase_name: 'Freeze authority inputs',
          failure_prevented: 'Source drift',
          signal_improved: 'Trust gain',
          status: 'awaiting_cde',
        },
      ],
    });
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.queryByText(/execute/i)).not.toBeInTheDocument();
    });
  });

  it('shows Propose to CDE button for pending proposals', async () => {
    setupFetchMock(mockRoadmap, mockAnalysis, {
      ...mockProposals,
      proposals: [
        {
          proposal_id: 'PROP-001',
          phase_id: 'RC-01',
          phase_name: 'Freeze authority inputs',
          failure_prevented: 'Source drift',
          signal_improved: 'Trust gain',
          status: 'awaiting_cde',
        },
      ],
    });
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/propose to cde/i)).toBeInTheDocument();
    });
  });

  it('displays footer with artifact-backed language, not fake-live claim', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.queryByText(/real data from RGE backend APIs/i)).not.toBeInTheDocument();
      expect(screen.getByText(/artifact-backed data when available/i)).toBeInTheDocument();
    });
  });

  it('handles API errors gracefully', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByText(/error:/i)).toBeInTheDocument();
    });
  });

  it('declares authority boundary statement (RGE proposes, CDE decides, SEL enforces)', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/RGE proposes only\. CDE decides\. SEL enforces\./i)
      ).toBeInTheDocument();
    });
  });

  it('renders provisional badge when analysis data_source is derived_estimate (DSH-05)', async () => {
    setupFetchMock(mockRoadmap, {
      ...mockAnalysis,
      data_source: 'derived_estimate',
      warnings: ['partial inputs'],
    });
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.getByTestId('provisional-badge')).toBeInTheDocument();
    });
  });

  it('does not render provisional badge when fully artifact-backed', async () => {
    setupFetchMock();
    render(<RGEPage />);
    await waitFor(() => {
      expect(screen.queryByTestId('provisional-badge')).not.toBeInTheDocument();
    });
  });
});
