# Telephony Multi-Trunk Failover Architecture

## Principles & Operational Guidance

1. **Single-Trunk Default**: Dev and staging environments default to a single primary trunk (`TelnyxDirectSIPAdapter`). Secondary trunk is **optional**.
2. **Production Multi-Trunk Failover**: Production tenants configure primary and secondary SIP trunks (e.g., Telnyx primary, Twilio/Plivo secondary).
3. **Failover Arbitration**: `TelephonyFailoverRouter` checks health status of configured trunks in priority order. If primary trunk is down, calls automatically route to secondary.
4. **Single-Trunk Outage Policy**: If a tenant has only 1 trunk configured and it fails, the session fails closed immediately with `TrunkUnavailableError`.
