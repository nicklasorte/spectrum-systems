# Chaos Campaign Registry

This registry defines mandatory chaos campaigns for governed 3LS seams.

## Required campaigns
1. broken schema
2. missing eval
3. missing trace
4. conflicting context
5. stale artifact
6. bad input
7. fake healthy signal
8. authority boundary violation

Campaign definitions are schema-bound by `chaos_campaign_record` and must include owner system, detection signal, control response, and replayability assertions.
