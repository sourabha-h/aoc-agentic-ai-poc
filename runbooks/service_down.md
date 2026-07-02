# Service Down

## Symptoms
- A service is not running.
- Requests time out or fail.
- Health checks show the node as degraded or critical.

## Health Checks
- Check service process status.
- Check application logs for startup or crash messages.
- Check dependent service availability.

## Thresholds
- Warning: service status is degraded.
- Critical: service status is down or unavailable.

## Likely Causes
- Service process exited unexpectedly.
- The node is under heavy load.
- A dependency is unavailable.

## Recommended Actions
- Restart the affected service.
- Check recent log errors.
- Verify dependencies before retrying.

## Risk Level
- High.

## Verification Steps
- Confirm the service reports running.
- Confirm logs no longer show crash errors.
- Confirm request paths recover.
