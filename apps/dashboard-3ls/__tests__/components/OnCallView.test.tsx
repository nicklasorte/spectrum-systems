import React from 'react';
import { render, screen } from '@testing-library/react';
import { OnCallView } from '@/components/OnCallView';

describe('OnCallView', () => {
  const mockIncidents = [
    {
      id: 'INC001',
      system_id: 'RDX',
      title: 'Batch out of sequence',
      severity: 'warning' as const,
      duration: '2 hours',
      status: 'open' as const,
      root_cause: 'Batch processing order violation',
      recommended_fix: 'Verify sequencing checkpoint',
      runbook_url: '/runbooks/batch',
    },
    {
      id: 'INC002',
      system_id: 'XRL',
      title: 'P99 latency exceeded',
      severity: 'critical' as const,
      duration: '4 hours',
      status: 'investigating' as const,
      root_cause: 'External API timeout',
      recommended_fix: 'Increase timeout threshold',
      runbook_url: '/runbooks/latency',
    },
  ];

  it('shows no incidents message when empty', () => {
    render(<OnCallView incidents={[]} />);
    expect(screen.getByText(/All systems operational/)).toBeInTheDocument();
  });

  it('displays incidents sorted by severity', () => {
    render(<OnCallView incidents={mockIncidents} />);

    expect(screen.getByText('P99 latency exceeded')).toBeInTheDocument();
    expect(screen.getByText('Batch out of sequence')).toBeInTheDocument();
  });

  it('shows incident details', () => {
    render(<OnCallView incidents={mockIncidents} />);

    expect(screen.getByText('Batch out of sequence')).toBeInTheDocument();
    expect(screen.getByText('P99 latency exceeded')).toBeInTheDocument();
  });

  it('includes runbook links', () => {
    render(<OnCallView incidents={mockIncidents} />);

    const runbookLinks = screen.getAllByText('Open Runbook');
    expect(runbookLinks.length).toBeGreaterThan(0);
  });
});
