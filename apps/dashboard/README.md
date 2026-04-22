# Spectrum Systems Dashboard

Production-ready web dashboard for real-time entropy posture & governance monitoring. Mobile-optimized, serverless, and deployed on Vercel.

## Features

- **Real-time Metrics**: Decision divergence, exception rates, trace coverage
- **Control Decision Display**: Block/escalate/proceed system status
- **Query Drill-Down**: Interactive modals for deep analysis
- **7-Day Trends**: Historical entropy tracking
- **Mobile-First Design**: Fully responsive (iPhone, iPad, Android)
- **Vercel Deployment**: Zero-infrastructure cloud hosting
- **Auto-Refresh**: Configurable metric polling (15s - 5m)

## Local Development

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Type checking
npm run type-check
```

### Environment Variables

Copy `.env.example` to `.env.local` and set:
- `ARTIFACT_API_URL`: Base URL for artifact store API (default: http://localhost:3001)
- `WS_URL`: WebSocket URL for real-time updates (default: ws://localhost:3001)

## Deployment to Vercel

### Option 1: GitHub Integration (Recommended)

1. Go to https://vercel.com/import
2. Connect your GitHub repository
3. Select project root: `apps/dashboard`
4. Add environment variables:
   - `ARTIFACT_API_URL`: https://api.spectrum-systems.com
   - `WS_URL`: wss://api.spectrum-systems.com
5. Click "Deploy"

### Option 2: Vercel CLI

```bash
npm i -g vercel
vercel login
vercel
```

### Configure Custom Domain

In Vercel dashboard:
1. Settings → Domains
2. Add: spectrum-systems-dashboard.vercel.app
3. Enable auto-HTTPS

## Architecture

```
app/
├── layout.tsx              Root layout
├── page.tsx                Main dashboard page
└── api/
    ├── entropy/
    │   └── latest.ts       Latest entropy snapshot
    └── queries/
        ├── reason-codes.ts Reason code query
        └── [queryId].ts    Dynamic query endpoint

components/
├── EntropyDashboard.tsx    Main dashboard
├── MetricCard.tsx          Individual metric
├── TrendChart.tsx          Trend visualization
├── ControlDecisionBanner.tsx Status banner
├── QueryDrillDown.tsx      Drill-down modal
└── Header.tsx              Navigation

lib/
└── types.ts                TypeScript types
```

## Metrics

- **Decision Divergence**: % disagreement between automated decisions and human reviews
- **Exception Rate**: % of decisions overridden by exception handling
- **Trace Coverage**: % of decisions with complete trace evidence
- **Calibration Drift**: % deviation from training distribution
- **Override Hotspots**: Number of policy override locations
- **Failure-to-Eval Rate**: % of failures without evaluation artifacts

## API Endpoints

- `GET /api/entropy/latest` - Latest entropy snapshot
- `GET /api/queries/reason-codes?days=30&limit=10` - Top blocking reasons
- `GET /api/queries/[queryId]` - Execute named query

## Mobile Support

Tested and optimized for:
- iPhone 13+ (iOS 15+)
- Android 12+ (Chrome, Firefox)
- iPad (iPadOS 15+)

## Production Checklist

- [x] TypeScript strict mode
- [x] Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
- [x] Cache headers (5s refresh, 10s stale-while-revalidate)
- [x] Error handling for API failures
- [x] Loading states and UX
- [x] Mobile-responsive design
- [x] Tailwind CSS optimized
- [x] Recharts visualization library
- [x] Next.js 14+ with App Router

## Performance

- First Contentful Paint: <1s
- Largest Contentful Paint: <2s
- Cumulative Layout Shift: <0.1
- Interactive: <2.5s

## Support

For issues or questions:
- Check `.env.local` configuration
- Verify artifact API connectivity
- Review browser console for errors
- Check Vercel logs: `vercel logs`

## License

Proprietary - Spectrum Systems
