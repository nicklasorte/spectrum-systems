import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { NextStepPanel } from '@/components/NextStepPanel';

global.fetch = jest.fn();

describe('NextStepPanel', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('renders selected next step and rejected rows', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        state: 'ok',
        payload: {
          artifact_type: 'next_step_recommendation_report',
          schema_version: '1.0.0',
          generated_at: '2026-04-27T00:00:00Z',
          status: 'pass',
          readiness_state: 'ready',
          source_refs: [],
          completed_work: [],
          partial_work: [],
          remaining_work_table: [],
          ranked_priorities: [{ id: 'RFX-PROOF-01', work_item: 'RFX LOOP-09/10' }],
          selected_recommendation: { id: 'RFX-PROOF-01', work_item: 'RFX LOOP-09/10', why: 'proof first', depends_on: ['H01'], unlocks: ['EVL'] },
          rejected_next_steps: [{ work_item: 'MET', reason: 'wait for proof' }],
          dependency_observations: [],
          red_team_findings: [{ id: 'RT-1', finding: 'test finding' }],
          warnings: [],
          reason_codes: [],
        },
      }),
    });

    render(<NextStepPanel />);
    await waitFor(() => expect(screen.getByTestId('next-step-selected')).toBeInTheDocument());
    expect(screen.getAllByText(/RFX LOOP-09\/10/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('next-step-rejected').textContent).toContain('MET');
    expect(screen.getByTestId('next-step-redteam').textContent).toContain('RT-1');
  });

  it('renders blocked state when missing artifact payload is returned', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        state: 'missing',
        payload: {
          artifact_type: 'next_step_recommendation_report',
          schema_version: '1.0.0',
          generated_at: '2026-04-27T00:00:00Z',
          status: 'blocked',
          readiness_state: 'blocked',
          source_refs: [{ path: 'artifacts/next_step_recommendation_report.json', required: true, present: false, content_hash: null }],
          completed_work: [],
          partial_work: [],
          remaining_work_table: [],
          ranked_priorities: [],
          selected_recommendation: null,
          rejected_next_steps: [],
          dependency_observations: [],
          red_team_findings: [],
          warnings: ['missing'],
          reason_codes: ['missing_required_artifact:artifacts/next_step_recommendation_report.json'],
        },
      }),
    });

    render(<NextStepPanel />);
    await waitFor(() => expect(screen.getByTestId('next-step-blocked')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId('next-step-reasons').textContent).toContain('missing_required_artifact'));
  });
});
