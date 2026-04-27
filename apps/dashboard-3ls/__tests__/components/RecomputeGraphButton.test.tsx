import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RecomputeGraphButton } from '@/components/RecomputeGraphButton';

global.fetch = jest.fn();

describe('RecomputeGraphButton', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('handles recompute success', async () => {
    const onResult = jest.fn();
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({ status: 'recompute_success_signal' }) });

    render(<RecomputeGraphButton onResult={onResult} />);
    fireEvent.click(screen.getByTestId('recompute-graph-button'));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(expect.objectContaining({ status: 'recompute_success_signal' })));
  });

  it('handles recompute failure without requiring graph reset', async () => {
    const onResult = jest.fn();
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, json: async () => ({ status: 'recompute_failed_signal', error_message: 'boom' }) });

    render(<RecomputeGraphButton onResult={onResult} />);
    fireEvent.click(screen.getByTestId('recompute-graph-button'));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(expect.objectContaining({ status: 'recompute_failed_signal' })));
  });
});
