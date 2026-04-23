# Dashboard Components

## Overview

React/TypeScript components for the 3-Letter Systems Dashboard.

## Components

### SystemCard
Displays a single system's health status and metrics.

**Props:**
- `system: SystemMetrics` - System metrics data
- `onClick: () => void` - Click handler for selection
- `isSelected: boolean` - Whether card is selected

### SystemDetail
Shows detailed metrics panel for selected system.

**Props:**
- `system?: SystemMetrics` - Selected system (optional)

### DashboardView
Main dashboard layout with system grid and detail panel.

**Props:**
- `systems: SystemMetrics[]` - All system metrics
- `isLoading?: boolean` - Loading state
- `lastRefresh?: string` - Last refresh timestamp

### OnCallView
On-call incident dashboard showing incidents sorted by severity.

**Props:**
- `incidents: Incident[]` - List of incidents
- `isLoading?: boolean` - Loading state

## Usage

```typescript
import { DashboardView } from '@/components/DashboardView';
import { OnCallView } from '@/components/OnCallView';

// Main dashboard
<DashboardView systems={systems} lastRefresh={refreshTime} />

// On-call view
<OnCallView incidents={incidents} />
```

## Types

See `SystemCard.tsx` and `OnCallView.tsx` for TypeScript interfaces.
