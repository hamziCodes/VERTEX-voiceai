# Post-Incident Review Template (PIR)

Use within 5 business days of any SEV-1 or SEV-2 operational or compliance incident (Phase 34).

## 1. Incident Overview

- **Incident ID:** `INC-YYYYMMDD-XX`
- **Severity:** [SEV-1 / SEV-2 / SEV-3]
- **Date / Time Start:** YYYY-MM-DD HH:MM UTC
- **Date / Time Resolved:** YYYY-MM-DD HH:MM UTC
- **Duration:** XX minutes
- **Incident Commander:** Name / Handle
- **Lead Investigator:** Name / Handle

## 2. Executive Summary

A concise (1-2 paragraph) summary of what happened, who was impacted, and how it was resolved. Never include raw PHI or API keys in this report; reference `correlation_id` only.

## 3. Impact Assessment

- **Tenants Affected:** Count or tier list (e.g. Standard, HIPAA)
- **Sessions Dropped / Failed:** XX calls
- **Revenue / SLA Impact:** XX minutes of degraded service against 99.9% target
- **Data Exposure:** None / PHI suspected (if HIPAA, refer to [../runbooks/RUNBOOK_HIPAA_INCIDENT.md](../runbooks/RUNBOOK_HIPAA_INCIDENT.md))

## 4. Timeline (UTC)

- `HH:MM` - Anomaly detected via alert / customer report
- `HH:MM` - Incident commander paged
- `HH:MM` - Triage initiated; runbook [NAME] applied
- `HH:MM` - Root cause identified
- `HH:MM` - Mitigating change deployed or rollback executed
- `HH:MM` - Verification completed; health checks green
- `HH:MM` - Incident resolved

## 5. Root Cause Analysis (5 Whys)

1. **Why did the outage happen?**
   - ...
2. **Why?**
   - ...
3. **Why?**
   - ...
4. **Why?**
   - ...
5. **Why?**
   - ...

## 6. Action Items & Preventative Measures

| Item # | Description | Owner | Target Date | Ticket Link |
|---|---|---|---|---|
| 1 | Add alerting rule for metric ... | Name | YYYY-MM-DD | #123 |
| 2 | Update runbook [NAME] with step ... | Name | YYYY-MM-DD | #124 |
| 3 | Add regression test to test suite | Name | YYYY-MM-DD | #125 |

## 7. Approvals

- **Engineering Lead:** _____________________ Date: _________
- **Operations / Compliance Lead:** _________ Date: _________
