# Routing Timeout

## Symptoms
- Requests to the gateway are timing out.
- Client response latency rises.
- Routing errors appear in logs.

## Health Checks
- Check gateway latency.
- Check upstream service status.
- Check recent routing errors.

## Thresholds
- Warning: latency above 100 ms.
- Critical: repeated timeouts or latency above 150 ms.

## Likely Causes
- Upstream platform is slow.
- Network path is degraded.
- The gateway is under load.

## Recommended Actions
- Verify upstream availability.
- Check for queue buildup.
- Retry once the upstream path is healthy.

## Risk Level
- Medium to high.

## Verification Steps
- Confirm latency returns to baseline.
- Confirm timeout errors stop.
- Confirm routing paths are stable.
