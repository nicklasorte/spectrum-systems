import { loadDashboardPublication } from '../../lib/loaders/dashboard_publication_loader'
import { selectDashboardViewModel } from '../../lib/selectors/dashboard_selectors'

export const dynamic = 'force-dynamic'

export default async function ExecutiveSummaryPage() {
  const model = selectDashboardViewModel(await loadDashboardPublication())

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '20px 12px 40px' }}>
      <h1>Executive Summary</h1>
      <p>High-level governed summary without replacing operator truth surfaces.</p>
      <ul>
        <li>Publication state: {model.state.kind}</li>
        <li>Recommendation: {model.recommendation.title}</li>
        <li>Hard gate: {model.sections.hardGate.data?.readiness_status ?? 'Not available yet'}</li>
        <li>Run state: {model.sections.runState.data?.current_run_status ?? 'Not available yet'}</li>
      </ul>
    </main>
  )
}
