# Runbook: HIPAA Incident

Suspected PHI exposure (Phases 10–12).

## Trigger

- Report of transcript in wrong tenant dashboard
- PHI in client-visible error or webhook body
- Unauthorized audit log access
- Missing BAA with HIPAA tier active

## Immediate actions (first 30 min)

1. **Contain:** disable affected tenant mint if ongoing leak suspected.
2. **Preserve:** pull audit trail by correlation_id — Phase 12; no copy of PHI to external tickets.
3. **Assess scope:** tenant_ids, time window, data classes involved.
4. Invoke legal/compliance contact — breach notification timeline **legal review required**.

## Do not

- Paste transcripts, audio, or caller_id into Slack/email
- Delete logs before legal hold assessment

## Evidence collection

- Audit export (Phase 12)
- DLQ refs (not payloads) if post-call involved
- AlertRouter email logs — metadata only

## Recovery

- Rotate compromised secrets (Phase 09)
- Re-enable tenant after root cause fix + BAA verification

## Escalation

SEV-1 always for confirmed cross-tenant PHI or missing BAA on HIPAA tier.

## Related

- [../developer/COMPLIANCE_INTEGRATOR_GUIDE.md](../developer/COMPLIANCE_INTEGRATOR_GUIDE.md)
- [../security/PENTEST_READINESS.md](../security/PENTEST_READINESS.md)
