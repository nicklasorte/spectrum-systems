# Vercel Deployment Quick Start

Deploy the 3-Letter Systems Dashboard to Vercel in 5 minutes.

## Prerequisites

- Vercel account (free at https://vercel.com)
- GitHub account with access to nicklasorte/spectrum-systems

## Step-by-Step Deployment

### 1. Go to Vercel Dashboard

```
https://vercel.com/dashboard
```

### 2. Click "Add New..." → "Project"

![Screenshot would go here]

### 3. Import Repository

- Search for `spectrum-systems`
- Click on `nicklasorte/spectrum-systems`
- Click "Import"

### 4. Configure Project

**Step 1: Select Root Directory**

```
Framework Preset: Next.js
Root Directory: apps/dashboard-3ls
```

**Step 2: Environment Variables (Optional)**

Add these environment variables (optional):

- `GITHUB_TOKEN`: Your GitHub personal access token (optional)
- `NEXT_PUBLIC_DASHBOARD_TITLE`: Dashboard title (default: "3-Letter Systems Dashboard")

To create a GitHub token:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token"
3. Select `repo` scope
4. Copy token and paste in Vercel

### 5. Deploy

Click "Deploy"

Vercel will:
1. Clone the repository
2. Install dependencies
3. Build Next.js app
4. Deploy to global CDN

**Deployment takes 2-5 minutes**

### 6. Access Dashboard

Once deployment completes:

1. Click the deployment URL
2. Dashboard will open at: `https://spectrum-3ls-dashboard.vercel.app`

## Verify Deployment

Check these endpoints:

### Dashboard UI
```
https://spectrum-3ls-dashboard.vercel.app
```
Should show 28+ system cards with health scores.

### Health API
```
https://spectrum-3ls-dashboard.vercel.app/api/health
```
Should return JSON with systems array.

## Configuration

### Custom Domain

1. Go to project settings
2. Click "Domains"
3. Add your custom domain
4. Update DNS records per instructions

### Environment Variables

1. Go to project settings
2. Click "Environment Variables"
3. Add or update variables
4. Redeploy when done

To trigger redeploy:
- Make a commit to main
- Or click "Redeploy" in Vercel dashboard

### Build Settings

To change build settings:

1. Go to project settings
2. Click "Build & Development Settings"
3. Update as needed
4. Save

Current settings:
- Build Command: `cd apps/dashboard-3ls && npm install && npm run build`
- Install Command: `npm install`
- Output Directory: `.next`

## Troubleshooting

### Deployment Failed

Check the build logs:
1. Go to Vercel dashboard
2. Click the failed deployment
3. Click "View Logs"
4. Look for error messages

Common issues:
- Missing environment variables
- Incorrect root directory
- Node.js version mismatch

### Dashboard Shows Blank Page

1. Check browser console (F12)
2. Check Vercel logs
3. Ensure `/api/health` returns valid JSON

### Slow Dashboard

1. Check Vercel analytics: Project → Analytics
2. Identify slow endpoints
3. Optimize data fetching

## Redeploy

### Automatic Redeploy

Vercel automatically redeploys when:
- You push to main
- You push a new tag
- You manually trigger

### Manual Redeploy

1. Go to Vercel dashboard
2. Click your project
3. Click "Deployments"
4. Find latest deployment
5. Click "..." menu
6. Click "Redeploy"

### Rollback

To revert to previous deployment:
1. Go to "Deployments"
2. Find previous working deployment
3. Click "..." menu
4. Click "Promote to Production"

## Monitoring

### View Logs

```
Vercel Dashboard → Project → Analytics → Logs
```

### Check Performance

```
Vercel Dashboard → Project → Analytics → Web Vitals
```

Monitor:
- First Contentful Paint (FCP)
- Largest Contentful Paint (LCP)
- Cumulative Layout Shift (CLS)
- Time to First Byte (TTFB)

### Set Up Alerts

1. Go to project settings
2. Click "Alerts"
3. Configure alert conditions
4. Set notification email

## Local Testing Before Deploy

Before pushing to production, test locally:

```bash
cd apps/dashboard-3ls
npm install
npm run build
npm run start
```

Then visit: http://localhost:3000

## Support

- **Vercel Docs**: https://vercel.com/docs
- **Dashboard Repo**: https://github.com/nicklasorte/spectrum-systems
- **Issues**: https://github.com/nicklasorte/spectrum-systems/issues

## Next Steps

1. ✅ Deploy to Vercel
2. ✅ Share dashboard URL with team
3. ✅ Configure monitoring/alerts
4. ✅ Set up custom domain (optional)
5. ✅ Add real artifact data source

---

**Dashboard is now live! 🚀**

Share your dashboard URL:
```
https://spectrum-3ls-dashboard.vercel.app
```
