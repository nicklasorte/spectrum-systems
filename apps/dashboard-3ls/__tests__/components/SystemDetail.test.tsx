import React from 'react';
import { render, screen } from '@testing-library/react';
import { SystemDetail } from '@/components/SystemDetail';

describe('SystemDetail', () => {
  const mockSystem = {
    system_id: 'RDX',
    system_name: 'Roadmap Execution Loop',
    system_type: 'execution',
    health_score: 88,
    status: 'warning' as const,
    incidents_week: 2,
    contract_violations: [
      { rule: 'sequence_check', detail: 'Batch out of order' }
    ],
  };

  it('renders null when system is not provided', () => {
    const { container } = render(<SystemDetail system={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('displays system details when system is provided', () => {
    render(<SystemDetail system={mockSystem} />);

    expect(screen.getByText(/RDX/)).toBeInTheDocument();
    expect(screen.getByText(/Roadmap Execution Loop/)).toBeInTheDocument();
    expect(screen.getByText('88')).toBeInTheDocument();
  });

  it('displays contract violations', () => {
    render(<SystemDetail system={mockSystem} />);

    expect(screen.getByText('Contract Violations:')).toBeInTheDocument();
    expect(screen.getByText(/sequence_check/)).toBeInTheDocument();
    expect(screen.getByText(/Batch out of order/)).toBeInTheDocument();
  });
});
