import RepoDashboard from '../components/RepoDashboard'
import { loadDashboardPublication } from '../lib/loaders/dashboard_publication_loader'
import { selectDashboardViewModel } from '../lib/selectors/dashboard_selectors'

export const dynamic = 'force-dynamic'

export default async function Page() {
  const publication = await loadDashboardPublication()
  const model = selectDashboardViewModel(publication)

  return <RepoDashboard model={model} />
}
