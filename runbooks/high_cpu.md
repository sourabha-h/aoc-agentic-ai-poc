# High CPU

## Symptoms
- CPU usage is higher than normal.
- Node response time may increase.
- Background jobs may lag.

## Health Checks
- Check CPU percentage.
- Check latency and queue depth.
- Check whether the node has recurring busy loops.

## Thresholds
- Warning: CPU above 75%.
- Critical: CPU above 90%.

## Likely Causes
- Traffic spike.
- Inefficient job processing.
- Downstream delays causing retries.

## Recommended Actions
- Reduce non-essential workload.
- Recheck heavy jobs and scheduling.
- Monitor for sustained saturation.

## Risk Level
- Medium.

## Verification Steps
- Confirm CPU returns below warning threshold.
- Confirm latency improves.
- Confirm queue depth stabilizes or drops.
