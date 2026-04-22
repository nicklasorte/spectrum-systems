# Phase 16: Repository Separation & Removal Plan

## New Repository: spectrum-pipeline-engine

**Location**: https://github.com/nicklasorte/spectrum-pipeline-engine

### Directory Structure (To Be Created)

```
spectrum-pipeline-engine/
├── src/
│   ├── mvp-integration/    ← moved from spectrum-systems
│   ├── observability/      ← moved from spectrum-systems
│   └── control_plane/      ← moved from spectrum-systems
├── spectrum_systems/       ← moved from spectrum-systems (496 files)
│   ├── execution/
│   ├── agents/
│   └── prompts/
├── working_paper_generator/  ← moved from spectrum-systems
├── .github/
│   └── workflows/
│       └── build.yml       ← CI/CD for execution layer
├── README.md
│   "This repo: AI execution + MVP integration
│    Governance: See spectrum-systems repo"
└── package.json
```

## Rollback Procedure (If Phase 16 Breaks Something)

### Pre-Removal Safeguard

```bash
# Before removal: Create tag to mark intact state
git tag -a v1.16-intact -m "Pre-phase-16-removal snapshot"
git push origin v1.16-intact
```

### Rollback Steps

```bash
# Option 1: Revert specific commits
git revert <commit-that-moved-files>

# Option 2: Hard reset to tagged version (destructive)
git reset --hard v1.16-intact
```

### Post-Rollback Verification

```bash
# Verify file count restored
ls -la spectrum_systems/ | wc -l  # Should see 496+ files

# Run all tests to ensure nothing broke
pytest tests/ -v

# Verify directory structure
find spectrum_systems -type d | head -20
```

## Testing Strategy

1. **Before removal**: All tests pass
2. **After removal**: Verify both repos have clean test suites
3. **Integration test**: Cross-repo imports work correctly
4. **Deployment test**: CI/CD pipelines work in both repos

## Timeline

- **Phase 16 Removal**: Scheduled for post-production-readiness
- **Execution lead**: Engineering team
- **Rollback authority**: SRE lead
- **Verification**: Quality assurance team
