import React from 'react';
import { render, screen } from '@testing-library/react';
import { SystemCard } from '@/components/SystemCard';

describe('SystemCard', () => {
  const mockSystem = {
    system_id: 'PQX',
    system_name: 'Bounded Execution',
    system_type: 'execution',
    health_score: 92,
    status: 'healthy' as const,
    incidents_week: 0,
    contract_violations: [],
  };

  it('renders system information', () => {
    render(
      <SystemCard
        system={mockSystem}
        onClick={() => {}}
        isSelected={false}
      />
    );

    expect(screen.getByText('PQX')).toBeInTheDocument();
    expect(screen.getByText('Bounded Execution')).toBeInTheDocument();
    expect(screen.getByText('92')).toBeInTheDocument();
  });

  it('displays status badge', () => {
    render(
      <SystemCard
        system={mockSystem}
        onClick={() => {}}
        isSelected={false}
      />
    );

    expect(screen.getByText('HEALTHY')).toBeInTheDocument();
  });

  it('shows contract violations when present', () => {
    const systemWithViolations = {
      ...mockSystem,
      contract_violations: [
        { rule: 'test_rule', detail: 'test violation' }
      ],
    };

    render(
      <SystemCard
        system={systemWithViolations}
        onClick={() => {}}
        isSelected={false}
      />
    );

    expect(screen.getByText('Violations:')).toBeInTheDocument();
  });

  it('renders a source badge when data_source is provided', () => {
    render(
      <SystemCard
        system={{ ...mockSystem, data_source: 'stub_fallback' }}
        onClick={() => {}}
        isSelected={false}
      />
    );
    expect(screen.getByTestId('source-badge').textContent).toMatch(/stub/i);
  });

  it('renders the authority role inline when provided (DSH-07)', () => {
    render(
      <SystemCard
        system={{ ...mockSystem, system_id: 'CDE', authority_role: 'decides' }}
        onClick={() => {}}
        isSelected={false}
      />
    );
    expect(screen.getByText('decides')).toBeInTheDocument();
  });

  it('renders UNKNOWN status without painting it green (DSH-04)', () => {
    render(
      <SystemCard
        system={{ ...mockSystem, status: 'unknown' as const }}
        onClick={() => {}}
        isSelected={false}
      />
    );
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
    expect(screen.queryByText('HEALTHY')).not.toBeInTheDocument();
  });
});
