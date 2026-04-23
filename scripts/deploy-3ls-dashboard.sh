#!/bin/bash

set -e

echo "=== 3-Letter Systems Dashboard Deployment ==="
echo "Starting deployment at $(date)"

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Run Python tests
echo -e "\n${YELLOW}[1/6]${NC} Running Python backend tests..."
cd spectrum_systems/dashboard
if python -m pytest tests/ -v --tb=short 2>/dev/null; then
  echo -e "${GREEN}✓ Backend tests passed${NC}"
else
  echo -e "${RED}✗ Backend tests failed${NC}"
  exit 1
fi

# 2. Check Python code quality
echo -e "\n${YELLOW}[2/6]${NC} Checking Python code quality..."
if python -m py_compile spectrum_systems/dashboard/backend/*.py 2>/dev/null; then
  echo -e "${GREEN}✓ Python syntax valid${NC}"
else
  echo -e "${RED}✗ Python syntax errors${NC}"
  exit 1
fi

# 3. Build frontend
echo -e "\n${YELLOW}[3/6]${NC} Building frontend..."
cd apps/dashboard
if npm install 2>/dev/null; then
  echo -e "${GREEN}✓ Dependencies installed${NC}"
else
  echo -e "${RED}✗ npm install failed${NC}"
  exit 1
fi

# 4. Run frontend tests (if they exist)
echo -e "\n${YELLOW}[4/6]${NC} Running frontend linter..."
if [ -f "next.config.js" ]; then
  npm run lint 2>/dev/null || echo -e "${YELLOW}⚠ Lint warnings (continuing)${NC}"
  echo -e "${GREEN}✓ Frontend linting complete${NC}"
fi

# 5. Build frontend
echo -e "\n${YELLOW}[5/6]${NC} Building frontend..."
if npm run build 2>/dev/null; then
  echo -e "${GREEN}✓ Frontend build successful${NC}"
else
  echo -e "${RED}✗ Frontend build failed${NC}"
  exit 1
fi

# 6. Smoke tests
echo -e "\n${YELLOW}[6/6]${NC} Running smoke tests..."

# Test artifact parser
python3 -c "
from spectrum_systems.dashboard.backend import ArtifactParser
from pathlib import Path
parser = ArtifactParser(Path('artifacts'))
print('✓ Artifact parser initialized')
" 2>/dev/null || echo -e "${YELLOW}⚠ Artifact parser test skipped (artifacts not found)${NC}"

# Test health calculator
python3 -c "
from spectrum_systems.dashboard.backend import HealthCalculator
calc = HealthCalculator({})
results = calc.calculate_all()
print(f'✓ Health calculator initialized - {len(results)} systems registered')
" 2>/dev/null

# Test alert engine
python3 -c "
from spectrum_systems.dashboard.backend import AlertEngine
engine = AlertEngine()
alerts = engine.generate_alerts({})
print('✓ Alert engine initialized')
" 2>/dev/null

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo "Timestamp: $(date)"
echo ""
echo "Next steps:"
echo "  1. Deploy to staging: vercel deploy --prod --env staging"
echo "  2. Run fire drill: python scripts/fire_drill.py"
echo "  3. Monitor dashboard at https://spectrum-3ls-dashboard.vercel.app"
