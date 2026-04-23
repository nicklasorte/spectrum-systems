# 3-Letter Systems Dashboard

Real-time observability dashboard for monitoring 28+ 3-letter systems (PQX, RDX, MAP, TPA, etc.) in **Spectrum Systems**.

## Overview

This dashboard provides a unified view of all governance systems in the Spectrum Systems runtime, including:

- **Execution Systems**: PQX, RDX, RQX, HNX
- **Governance Systems**: TPA, MAP, CDE, GOV, FRE, RIL, SEL
- **Orchestration Systems**: TLC, AEX
- **Data Systems**: DBB, DEM, MCL, BRM, XRL
- **Planning Systems**: NSX, PRG, RSM, PRA
- **Placeholder Systems**: LCE, ABX, DCL, SAL, SAS, SHA

## Features

✅ Real-time health scores (0-100) for each system
✅ Status indicators: healthy / warning / critical
✅ Contract violation tracking and display
✅ Incident counting and trending
✅ Mobile-responsive design with Tailwind CSS
✅ Dark mode ready
✅ API endpoint for programmatic access
✅ Fast refresh with data caching

## Architecture

### Backend (`spectrum_systems/dashboard/backend/`)

- **artifact_parser.py**: Parse JSON artifacts with caching
- **health_calculator.py**: Calculate health scores for all systems
- **lineage_validator.py**: Validate artifact lineage chains
- **github_client.py**: Fetch PR data from GitHub
- **data_refresh.py**: Hourly data refresh pipeline

### Frontend (`apps/dashboard-3ls/`)

- **app/page.tsx**: Main dashboard page
- **components/SystemCard.tsx**: Individual system card component
- **components/SystemDetail.tsx**: Detailed system information panel
- **app/api/health/route.ts**: Health data API endpoint
- **Tailwind CSS**: Responsive styling

## Running Locally

### Prerequisites
- Node.js 18+
- Python 3.10+

### Frontend Setup

```bash
cd apps/dashboard-3ls
npm install
npm run dev
```

Dashboard will be available at http://localhost:3000

### Backend Setup

```bash
cd spectrum_systems/dashboard/backend
pip install -r requirements.txt
python -m pytest
```

## Deployment

### Vercel (Recommended)

1. Go to https://vercel.com
2. Import repository
3. Select Root Directory: `apps/dashboard-3ls`
4. Add environment variables (optional):
   - `GITHUB_TOKEN`: GitHub personal access token
   - `NEXT_PUBLIC_DASHBOARD_TITLE`: Dashboard title
5. Deploy

Dashboard will be live at: `https://spectrum-3ls-dashboard.vercel.app`

### Manual Deployment

```bash
npm run build
npm run start
```

## API Endpoints

### GET `/api/health`

Returns health status for all 28+ systems.

**Response:**
```json
{
  "status": "success",
  "systems": [
    {
      "system_id": "PQX",
      "system_name": "Bounded Execution",
      "system_type": "execution",
      "health_score": 92,
      "status": "healthy",
      "incidents_week": 0,
      "contract_violations": []
    }
  ],
  "refreshed_at": "2026-04-23T12:34:56Z"
}
```

## Health Score Calculation

Health score is a weighted average of:

- **Execution Success** (40%): Success rate of system operations
- **Contract Adherence** (30%): Compliance with contract rules
- **Incident Rate** (20%): Number of incidents (lower is better)
- **Latency** (10%): P99 latency performance

### Status Mapping

- **Healthy**: Health score ≥ 85
- **Warning**: Health score 70-84
- **Critical**: Health score < 70

## Systems Reference

### Execution Systems

| ID  | Name | Purpose |
|-----|------|---------|
| PQX | Bounded Execution | Core execution runtime with limits |
| RDX | Roadmap Execution Loop | Executes approved roadmap items |
| RQX | Review Queue Execution | Processes review queue |
| HNX | Stage Harness | Manages stage transitions |

### Governance Systems

| ID  | Name | Purpose |
|-----|------|---------|
| TPA | Trust/Policy Gate | Enforces trust and policy rules |
| MAP | Review Artifact Mediation | Mediates review artifacts |
| CDE | Closure Decision Authority | Makes closure decisions |
| GOV | Governance Authority | Central governance |
| FRE | Failure Diagnosis & Repair | Diagnoses and repairs failures |
| RIL | Review Interpretation | Interprets review inputs |
| SEL | Enforcement Control | Controls enforcement actions |

### Orchestration Systems

| ID  | Name | Purpose |
|-----|------|---------|
| TLC | Top-Level Orchestration | Orchestrates all operations |
| AEX | Admission Exchange | Manages admission flow |

### Data Systems

| ID  | Name | Purpose |
|-----|------|---------|
| DBB | Data Backbone | Core data storage and access |
| DEM | Decision Economics | Tracks decision metrics |
| MCL | Memory Compaction | Manages memory efficiency |
| BRM | Blast Radius Manager | Limits blast radius of changes |
| XRL | External Reality Loop | Syncs with external systems |

### Planning Systems

| ID  | Name | Purpose |
|-----|------|---------|
| NSX | Next-Step Extraction | Extracts next steps |
| PRG | Program Planning | Plans program execution |
| RSM | Reconciliation State | Manages reconciliation |
| PRA | PR Anchor Discovery | Discovers PR anchors |

## Troubleshooting

### Dashboard shows "Loading..." forever
- Check browser console for errors (F12)
- Verify `/api/health` endpoint is working: `curl http://localhost:3000/api/health`
- Check network tab in browser DevTools

### No systems visible
- Ensure artifacts directory exists
- Run artifact parser test: `python -m pytest spectrum_systems/dashboard/backend/`
- Check for parsing errors in logs

### Vercel deployment fails
- Ensure Root Directory is set to `apps/dashboard-3ls`
- Check build logs in Vercel dashboard
- Verify all dependencies in package.json

## Development

### Adding a new system

1. Add system to `SYSTEMS` dict in `health_calculator.py`:
```python
'XYZ': {'name': 'System Name', 'type': 'category'},
```

2. System will automatically appear in dashboard

3. Implement health calculation logic in `_get_*` methods

### Customizing styles

Edit `apps/dashboard-3ls/tailwind.config.js` and components as needed.

### Extending health calculation

Edit `health_calculator.py:calculate_system()` to add new metrics.

## Performance

- **Health API**: < 100ms response time
- **Dashboard Load**: < 2s with network latency
- **Artifact Parsing**: Cached for 1 hour
- **Data Refresh**: Hourly batch update

## Contributing

See main repository CONTRIBUTING.md for guidelines.

## License

Spectrum Systems License

## Support

For issues, questions, or contributions, please open an issue in the main repository.
