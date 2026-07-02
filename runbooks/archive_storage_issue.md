# Archive Storage Issue

## Symptoms
- Archive storage usage above normal.
- Oracle archive operations report capacity pressure.
- Cleanup requests may be visible in operational logs.

## Health Checks
- Check archive storage disk usage percentage.
- Check Oracle archive error messages.
- Check whether cleanup has reduced disk usage.

## Thresholds
- Warning: disk usage above 90%.
- Critical: disk usage above 95%.

## Likely Causes
- Old archive files have not been cleaned up.
- Backup retention is too aggressive for available storage.
- Cleanup activity was incomplete or interrupted.

## Recommended Actions
- Review storage capacity and archive retention.
- Remove safe-to-delete archive content.
- Re-run cleanup if the first pass did not reduce usage.

## Risk Level
- Medium to high.

## Verification Steps
- Confirm disk usage drops below the warning threshold.
- Confirm Oracle archive errors stop appearing.
- Confirm archive operations resume normally.
