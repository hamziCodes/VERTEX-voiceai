-- Escalations domain + sync support columns.
-- Additive only: nothing here alters existing tables except adding columns.
-- The escalations table is the dashboard hub for safety escalations derived from
-- Retell call data (triage flags, transfers, Groq-inferred triggers).

-- ============================================================
-- 1. New columns on bookings
-- ============================================================
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS transfer_destination text;
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS escalation_trigger text DEFAULT 'none';

-- ============================================================
-- 2. New column on locations (fallback for escalation routed_to)
-- ============================================================
ALTER TABLE public.locations ADD COLUMN IF NOT EXISTS escalation_forwarding_number text;

UPDATE public.locations
SET escalation_forwarding_number = '+13125550100'
WHERE name = 'Awaaz Labs Cardiology'
  AND escalation_forwarding_number IS NULL;

-- ============================================================
-- 3. escalations — one row per booking that triggered an escalation
-- ============================================================
CREATE TABLE IF NOT EXISTS public.escalations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  location_id uuid NOT NULL REFERENCES public.locations(id),
  booking_id uuid REFERENCES public.bookings(id),
  call_id text,
  patient_id uuid REFERENCES public.patients(id),
  trigger text NOT NULL,
  routed_to text,
  status text NOT NULL DEFAULT 'open',
  acknowledged_at timestamptz,
  acknowledged_by text,
  resolution_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT escalations_status_enum CHECK (status IN ('open','acknowledged','resolved')),
  CONSTRAINT escalations_trigger_enum CHECK (trigger IN ('triage_high','triage_urgent_emergency','caller_requested_human','clinical_question','agent_initiated')),
  CONSTRAINT escalations_booking_unique UNIQUE (booking_id)
);

CREATE INDEX IF NOT EXISTS escalations_status_idx ON public.escalations (status);
CREATE INDEX IF NOT EXISTS escalations_created_at_idx ON public.escalations (created_at DESC);
CREATE INDEX IF NOT EXISTS escalations_location_idx ON public.escalations (location_id);
CREATE INDEX IF NOT EXISTS escalations_booking_idx ON public.escalations (booking_id);
CREATE INDEX IF NOT EXISTS escalations_patient_idx ON public.escalations (patient_id);
CREATE INDEX IF NOT EXISTS escalations_call_id_idx ON public.escalations (call_id);

DROP TRIGGER IF EXISTS escalations_set_updated_at ON public.escalations;
CREATE TRIGGER escalations_set_updated_at
  BEFORE UPDATE ON public.escalations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 4. RLS: default-deny (same pattern as other domain tables)
-- ============================================================
ALTER TABLE public.escalations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS deny_anon_all ON public.escalations;
CREATE POLICY deny_anon_all ON public.escalations
  AS PERMISSIVE FOR ALL TO anon USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_authenticated_all ON public.escalations;
CREATE POLICY deny_authenticated_all ON public.escalations
  AS PERMISSIVE FOR ALL TO authenticated USING (false) WITH CHECK (false);

-- ============================================================
-- 5. Enable Supabase Realtime on appointments + escalations
--    (consumed server-side by the Next.js SSE endpoint, not by the browser)
-- ============================================================
DO $$
BEGIN
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.appointments; EXCEPTION WHEN OTHERS THEN NULL; END;
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.escalations; EXCEPTION WHEN OTHERS THEN NULL; END;
END $$;
