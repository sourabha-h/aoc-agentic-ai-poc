# Queue Backlog

## Symptoms
- Queue depth is growing.
- Requests are waiting longer than expected.
- Downstream processing appears delayed.

## Health Checks
- Check queue depth.
- Check processing latency.
- Check whether downstream services are healthy.

## Thresholds
- Warning: queue depth above 20.
- Critical: queue depth above 50.

## Likely Causes
- Slow downstream dependency.
- Temporary traffic burst.
- Service processing is blocked.

## Recommended Actions
- Verify downstream dependencies.
- Reduce input rate if possible.
- Re-run backlog checks after recovery.

## Risk Level
- Medium.

## Verification Steps
- Confirm queue depth is falling.
- Confirm latency is returning to normal.
- Confirm blocked consumers recover.
