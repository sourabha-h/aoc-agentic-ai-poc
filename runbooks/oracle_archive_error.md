# Oracle Archive Error

## Symptoms
- Oracle archive logging reports capacity or destination errors.
- Database writes may slow down.
- Archive-related warnings appear in logs.

## Health Checks
- Check for ORA archive error messages.
- Check archive destination availability.
- Check database latency and write stability.

## Thresholds
- Warning: latency above 100 ms.
- Critical: archive destination unavailable or error repeated.

## Likely Causes
- Archive storage is full or near full.
- Archive destination is unavailable.
- Dependent storage cleanup has not completed.

## Recommended Actions
- Verify archive storage availability.
- Free space in the archive destination.
- Recheck database archive status after cleanup.

## Risk Level
- High.

## Verification Steps
- Confirm archive error messages disappear.
- Confirm database latency returns to baseline.
- Confirm archive destination is available again.
