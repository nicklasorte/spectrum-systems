# Dashboard Quick Start

Get the Spectrum Systems Dashboard running in 5 minutes.

## Local Development (5 minutes)

```bash
# 1. Navigate to dashboard directory
cd apps/dashboard

# 2. Install dependencies
npm install

# 3. Create environment file
cp .env.example .env.local

# 4. Start development server
npm run dev

# 5. Open browser
# http://localhost:3000
```

Dashboard will be available at http://localhost:3000 with hot-reload enabled.

## Environment Configuration

Edit `.env.local` to point to your artifact API:

```bash
ARTIFACT_API_URL=http://localhost:3001
WS_URL=ws://localhost:3001
```

For production (after deploying to Vercel):
```bash
ARTIFACT_API_URL=https://api.spectrum-systems.com
WS_URL=wss://api.spectrum-systems.com
```

## Vercel Deployment (2 steps)

### Option 1: One-Click Deploy (Easiest)

1. Go to https://vercel.com/import
2. Select `nicklasorte/spectrum-systems`
3. Set root to `apps/dashboard`
4. Add environment variables
5. Click "Deploy"

**Done!** Dashboard available at `https://spectrum-systems-dashboard.vercel.app`

### Option 2: Via CLI

```bash
npm install -g vercel
cd /path/to/spectrum-systems
vercel
# Follow prompts → Deploy
```

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **Real-time Metrics** | Decision divergence, exception rates, trace coverage |
| **Control Decisions** | System status display (proceed/escalate/block) |
| **7-Day Trends** | Historical entropy visualization |
| **Drill-Down Analysis** | Click metrics for detailed query results |
| **Mobile Optimized** | Works on iPhone, iPad, Android |
| **Auto-Refresh** | Configurable polling (15s - 5m) |
| **Dark-Ready UI** | Clean, professional design |

## Key Files

```
apps/dashboard/
├── app/
│   ├── layout.tsx          Root layout
│   ├── page.tsx            Main dashboard
│   └── api/
│       ├── entropy/latest.ts
│       └── queries/[queryId].ts
├── components/
│   ├── EntropyDashboard.tsx
│   ├── MetricCard.tsx
│   ├── TrendChart.tsx
│   ├── ControlDecisionBanner.tsx
│   ├── QueryDrillDown.tsx
│   └── Header.tsx
├── lib/types.ts
├── next.config.js
└── package.json
```

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/entropy/latest` | Latest entropy snapshot |
| `GET /api/queries/reason-codes` | Top blocking reasons |
| `GET /api/queries/[queryId]` | Execute named query |

## Metrics Explained

- **Decision Divergence** (%): Disagreement between automated decisions and human review
- **Exception Rate** (%): Override frequency
- **Trace Coverage** (%): Decisions with complete trace evidence
- **Calibration Drift** (%): Distribution deviation
- **Override Hotspots** (#): Policy override locations
- **Failure-to-Eval** (%): Failures without evaluation

## Status Colors

| Color | Meaning |
|-------|---------|
| 🟢 Green | Good (within thresholds) |
| 🟡 Yellow | Warning (elevated but acceptable) |
| 🔴 Red | Critical (requires immediate attention) |

## Common Tasks

### Change Refresh Rate
1. Click "Settings" in header
2. Select new interval (15s, 30s, 1m, 5m)

### Drill Down on Metric
1. Click any metric card
2. View detailed query results in modal
3. Click ✕ to close

### View in Production
1. Navigate to Vercel deployment URL
2. Share URL with team
3. No installation needed - works on any device

## Testing the Dashboard

### With Mock Data
```bash
# API will use mock data if ARTIFACT_API_URL is not accessible
cd apps/dashboard
npm run dev
# Works even without running artifact API
```

### With Real API
```bash
# Start artifact API on localhost:3001
# Then start dashboard:
cd apps/dashboard
npm run dev
# Dashboard fetches real data
```

## Production Checklist

Before going live:
- [ ] Environment variables configured in Vercel
- [ ] API endpoint is publicly accessible
- [ ] CORS headers configured (if needed)
- [ ] Custom domain set up
- [ ] Analytics enabled
- [ ] Monitor first deployment

## Troubleshooting

### Dashboard won't load
- Check browser console (F12) for errors
- Verify `ARTIFACT_API_URL` is set correctly
- Ensure artifact API is running/accessible

### Metrics show "Error"
- Check API connectivity: `curl $ARTIFACT_API_URL/api/entropy/latest-snapshot`
- Verify network request in DevTools
- Check Vercel logs: `vercel logs`

### Slow performance
- Check DevTools Network tab
- Review Vercel Analytics
- Verify API response times

## Next Steps

1. **Local Development**: `npm run dev` in `apps/dashboard`
2. **Deploy to Vercel**: Follow deployment steps above
3. **Configure Domain**: Set custom domain in Vercel
4. **Share with Team**: Send dashboard URL
5. **Monitor**: Watch Vercel Analytics for performance

## Learn More

- [Vercel Deployment Guide](./VERCEL_DEPLOYMENT_GUIDE.md)
- [Dashboard README](./apps/dashboard/README.md)
- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com)

---

**Deployed?** Share this URL with your team: `https://spectrum-systems-dashboard.vercel.app`

**Questions?** Check `VERCEL_DEPLOYMENT_GUIDE.md` for detailed setup instructions.
