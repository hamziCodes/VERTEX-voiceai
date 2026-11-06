export interface AuditEventDto {
  id: string;
  tenant_id: string;
  actor_id: string;
  actor_type: string;
  action: string;
  resource_type: string;
  resource_id: string;
  detail: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}
