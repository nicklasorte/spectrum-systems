# Policy-as-Code Foundation

Versioned, tested, gradually-rolled-out policies.

## Policy Lifecycle

1. **Draft**: Policy created, versioned
2. **Test**: Test cases written, all pass
3. **Deploy**: Canary rollout (10% initially)
4. **Increase**: Gradual increase to 100% if no incidents
5. **Active**: Full rollout in use
6. **Deprecated**: Superseded by new policy version

## Testing Before Deployment

All test cases must pass before deployment approved.
Canary rollout tracks incidents.
On incident spike, auto-rollback to previous version.

## Policy Decisions

Every policy application is recorded:
- Which policy applied
- Target artifact
- Decision outcome
- Rollout percentage at time
