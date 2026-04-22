# Vercel Deployment Guide

## Overview

The Spectrum Systems Dashboard is a production-ready Next.js application configured for deployment on Vercel. This guide walks through the deployment process and post-deployment configuration.

## Pre-Deployment Checklist

- [x] Next.js 14 application created at `apps/dashboard`
- [x] All React components developed and typed
- [x] API endpoints configured
- [x] Tailwind CSS styling complete
- [x] TypeScript strict mode enabled
- [x] Environment variables documented
- [x] Security headers configured
- [x] vercel.json configuration created

## Deployment Methods

### Method 1: GitHub Integration (Recommended)

**Easiest and most automated approach.**

1. **Go to Vercel Dashboard**
   - Visit https://vercel.com/dashboard
   - Click "Import Project"

2. **Connect Repository**
   - Select "GitHub" as source
   - Authenticate with GitHub account
   - Find and select `nicklasorte/spectrum-systems`

3. **Configure Project**
   - Framework: Next.js (auto-detected)
   - Root Directory: `apps/dashboard`
   - Build Command: `npm run build`
   - Output Directory: `.next`
   - Install Command: `npm install`

4. **Set Environment Variables**
   - In Vercel dashboard, go to Settings → Environment Variables
   - Add the following:
     ```
     ARTIFACT_API_URL=https://api.spectrum-systems.com
     WS_URL=wss://api.spectrum-systems.com
     ```
   - Or use your actual production API endpoints

5. **Deploy**
   - Click "Deploy"
   - Wait for build and deployment to complete
   - Dashboard will be available at `https://spectrum-systems-dashboard.vercel.app`

### Method 2: Vercel CLI

**For developers who prefer command-line deployment.**

```bash
# Install Vercel CLI globally
npm install -g vercel

# Login to Vercel
vercel login

# Navigate to project root
cd /home/user/spectrum-systems

# Deploy
vercel

# Follow the prompts:
# - Link to existing project or create new?
# - Which scope? (your account)
# - Link to existing project in current directory? (No for first deployment)
# - Project name: spectrum-systems-dashboard
# - Root directory: apps/dashboard
# - Build settings: auto-detected
# - Environment variables: add ARTIFACT_API_URL and WS_URL
```

## Post-Deployment Configuration

### 1. Custom Domain Setup

In Vercel Dashboard:
1. Go to Project Settings → Domains
2. Add custom domain: `dashboard.spectrum-systems.com` (or your domain)
3. Configure DNS records as provided by Vercel
4. Wait for DNS propagation (typically 5-30 minutes)

### 2. Environment Variables

Update production environment variables:

```bash
vercel env add ARTIFACT_API_URL
# Enter: https://api.spectrum-systems.com

vercel env add WS_URL
# Enter: wss://api.spectrum-systems.com
```

Or via Vercel Dashboard:
- Project Settings → Environment Variables
- Click "Add New Variable"
- Set `ARTIFACT_API_URL` and `WS_URL`
- Ensure both Production, Preview, and Development environments are selected
- Redeploy to apply changes

### 3. Monitoring and Logs

View deployment logs:
```bash
vercel logs
```

View real-time logs:
```bash
vercel logs --follow
```

### 4. Analytics

Enable Vercel Analytics (optional):
1. Go to Project Settings → Analytics
2. Click "Enable Analytics"
3. View performance metrics at https://vercel.com/analytics

## Continuous Deployment (CI/CD)

### Automatic Deployments

- **Production**: Every push to `main` automatically deploys
- **Preview**: Every pull request gets a preview deployment
- **Rollback**: Click "Rollback" in Vercel Dashboard to revert

### Branch Deployments

To deploy specific branches:

1. In Vercel Dashboard → Settings → Git
2. Add branch under "Deploy on Git Push"
3. Select `claude/deploy-vercel-dashboard-1x2Xb`
4. Every push to that branch will trigger deployment

## Troubleshooting

### Build Failures

Check Vercel build logs:
```bash
vercel logs --follow
```

Common issues:
- **Missing dependencies**: Ensure `apps/dashboard/package.json` has all required packages
- **Environment variables**: Verify `ARTIFACT_API_URL` is set
- **Node version**: Vercel uses Node 18+ by default (sufficient for Next.js 14)

### API Connectivity Issues

If API calls fail:
1. Check that `ARTIFACT_API_URL` is correctly set
2. Verify artifact API is accessible from Vercel (no firewall/IP restrictions)
3. Test endpoint manually:
   ```bash
   curl https://api.spectrum-systems.com/api/entropy/latest-snapshot
   ```

### Performance Issues

Monitor Core Web Vitals:
1. Go to Project Settings → Analytics
2. Check Lighthouse scores
3. Review performance recommendations

Optimize if needed:
- Enable Image Optimization in `next.config.js`
- Implement ISR (Incremental Static Regeneration)
- Add caching headers for static assets

## Scaling and Limits

Vercel's free and pro plans include:
- **Auto-scaling**: Automatically handles traffic spikes
- **CDN**: Global content delivery network
- **Serverless Functions**: API routes scaled automatically
- **Bandwidth**: Included in plan

For production workloads, consider Vercel Pro or Enterprise.

## Security Considerations

### CORS Headers

If dashboard and API are on different domains, add CORS headers to `next.config.js`:

```javascript
headers: async () => [
  {
    source: '/api/:path*',
    headers: [
      {
        key: 'Access-Control-Allow-Origin',
        value: 'https://api.spectrum-systems.com',
      },
    ],
  },
];
```

### Rate Limiting

Implement rate limiting for API endpoints (optional):
```bash
npm install ratelimit
```

### Secrets Management

Never commit sensitive data. Use Vercel's environment variables:
- API keys
- Database credentials
- OAuth tokens

## Rollback Procedure

If deployment causes issues:

1. **Via Vercel Dashboard**
   - Go to Deployments
   - Find previous working deployment
   - Click "Rollback"
   - Confirm

2. **Via CLI**
   ```bash
   vercel rollback
   # Select previous deployment
   ```

## Testing After Deployment

1. **Health Check**
   - Visit https://spectrum-systems-dashboard.vercel.app
   - Verify page loads without errors

2. **Metrics Display**
   - Check all metric cards render
   - Verify data loads from API
   - Confirm refresh works

3. **Mobile Testing**
   - Test on iPhone (Safari)
   - Test on Android (Chrome)
   - Verify responsive design

4. **Performance**
   - Open DevTools (F12)
   - Check Network tab for API calls
   - Verify no console errors

## Maintenance

### Regular Tasks

- Monitor deployment logs weekly
- Check analytics for performance issues
- Update dependencies monthly:
  ```bash
  cd apps/dashboard
  npm update
  ```

### Updating Dashboard Code

1. Make changes on feature branch
2. Create pull request
3. Get review approval
4. Merge to `main`
5. Vercel automatically deploys

## Reference

- **Vercel Docs**: https://vercel.com/docs
- **Next.js Docs**: https://nextjs.org/docs
- **Dashboard Code**: `/apps/dashboard/`
- **Config**: `/vercel.json`

## Support

For deployment issues:
- Check Vercel documentation
- Review application logs via Vercel Dashboard
- Test API connectivity from local environment
- Verify environment variables are set correctly
