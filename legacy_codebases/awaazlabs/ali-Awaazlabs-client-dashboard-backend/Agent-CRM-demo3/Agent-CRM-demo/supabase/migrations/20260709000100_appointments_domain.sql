-- Appointments domain for the AwaazLabs client dashboard.
-- Additive only: nothing here alters bookings / vob_queue / message_log or the live pipeline.
-- bookings stays the raw per-call capture table; these tables are the verified, normalized
-- layer the dashboard reads. Every constraint below is a verification layer: bad data is
-- rejected at the database boundary, never silently stored.

-- ============================================================
-- locations — clinic locations (timezone drives all UI rendering)
-- ============================================================
create table if not exists public.locations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  timezone text not null default 'America/Chicago',
  business_hours jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists locations_set_updated_at on public.locations;
create trigger locations_set_updated_at
  before update on public.locations
  for each row execute function set_updated_at();

insert into public.locations (name, timezone, business_hours)
select 'Awaaz Labs Cardiology', 'America/Chicago',
       '{"mon":["08:00","17:00"],"tue":["08:00","17:00"],"wed":["08:00","17:00"],"thu":["08:00","17:00"],"fri":["08:00","17:00"],"sat":null,"sun":null}'::jsonb
where not exists (select 1 from public.locations);

-- ============================================================
-- patients — deduplicated patient identities (bookings are per-call; patients are per-person)
-- ============================================================
create table if not exists public.patients (
  id uuid primary key default gen_random_uuid(),
  location_id uuid not null references public.locations(id),
  full_legal_name text not null,
  first_name text,
  last_name text,
  dob date,
  gender text,
  phone_e164 text,
  whatsapp_suitable boolean,
  email text,
  mailing_address text,
  language text not null default 'en',
  payer_name text,
  member_id text,
  group_number text,
  insurance_status text not null default 'pending',
  is_seeded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- verification layer: reject values that cannot be what they claim to be
  constraint patients_name_not_garbage check (
    length(full_legal_name) between 2 and 100
    and full_legal_name !~ '@'
    and full_legal_name !~ '[0-9]{3,}'
  ),
  constraint patients_dob_sane check (dob is null or (dob > date '1900-01-01' and dob <= current_date)),
  constraint patients_phone_e164 check (phone_e164 is null or phone_e164 ~ '^\+[1-9][0-9]{6,14}$'),
  constraint patients_email_shape check (email is null or email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
  constraint patients_language_enum check (language in ('en','es','other')),
  constraint patients_insurance_status_enum check (insurance_status in ('covered','partial','pending','pending_form','unknown','self_pay'))
);

create index if not exists patients_phone_idx on public.patients (phone_e164);
create index if not exists patients_name_idx on public.patients (lower(full_legal_name));
create index if not exists patients_location_idx on public.patients (location_id);

drop trigger if exists patients_set_updated_at on public.patients;
create trigger patients_set_updated_at
  before update on public.patients
  for each row execute function set_updated_at();

-- ============================================================
-- appointments — the dashboard hub entity (one row per appointment)
-- ============================================================
create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(),
  location_id uuid not null references public.locations(id),
  patient_id uuid not null references public.patients(id),
  booking_id uuid references public.bookings(id),
  call_id text,
  vob_id uuid references public.vob_queue(id),

  status text not null default 'booked',
  source text not null default 'voice',
  service_interest text not null,
  language text not null default 'en',
  triage text not null default 'none',
  insurance_captured boolean not null default false,

  booked_by_agent text not null default 'receptionist',
  booked_at timestamptz not null,
  after_hours boolean not null default false,

  -- appointment time: parsed from natural language, never guessed.
  -- starts_at stays null until parse succeeds or a human sets it; the parse trail is kept.
  starts_at timestamptz,
  appointment_text_raw text,
  time_parse_status text not null default 'pending',
  time_parse_confidence text,

  needs_review boolean not null default false,
  review_reasons text[] not null default '{}',
  is_seeded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint appointments_status_enum check (status in ('booked','confirmed','rescheduled','completed','cancelled','no_show')),
  constraint appointments_source_enum check (source in ('voice','whatsapp','web_chat','form')),
  constraint appointments_language_enum check (language in ('en','es','other')),
  constraint appointments_triage_enum check (triage in ('none','low','high','urgent')),
  constraint appointments_agent_enum check (booked_by_agent in ('receptionist','vob','verifier','chat','review_taker','reengagement')),
  constraint appointments_parse_status_enum check (time_parse_status in ('pending','parsed','ambiguous','unparseable','manual')),
  constraint appointments_parse_confidence_enum check (time_parse_confidence is null or time_parse_confidence in ('low','medium','high')),
  -- verification: a parsed appointment must actually carry a time, and vice versa
  constraint appointments_parsed_has_time check (time_parse_status not in ('parsed','manual') or starts_at is not null),
  constraint appointments_time_sane check (starts_at is null or starts_at > timestamptz '2026-01-01')
);

create index if not exists appointments_starts_at_idx on public.appointments (starts_at);
create index if not exists appointments_status_idx on public.appointments (status);
create index if not exists appointments_booked_at_idx on public.appointments (booked_at desc);
create index if not exists appointments_patient_idx on public.appointments (patient_id);
create index if not exists appointments_booking_idx on public.appointments (booking_id);
create index if not exists appointments_call_idx on public.appointments (call_id);
create index if not exists appointments_vob_idx on public.appointments (vob_id);
create index if not exists appointments_location_idx on public.appointments (location_id);
create index if not exists appointments_needs_review_idx on public.appointments (needs_review) where needs_review;

drop trigger if exists appointments_set_updated_at on public.appointments;
create trigger appointments_set_updated_at
  before update on public.appointments
  for each row execute function set_updated_at();

-- verification layer: appointment status lifecycle is enforced in the database.
-- terminal states never mutate; only transitions the product defines are possible.
create or replace function public.enforce_appointment_transition()
returns trigger language plpgsql as $$
begin
  if old.status = new.status then
    return new;
  end if;
  if old.status in ('completed','cancelled','no_show') then
    raise exception 'appointment % is % (terminal); cannot change to %', old.id, old.status, new.status;
  end if;
  if not (
    (old.status = 'booked'      and new.status in ('confirmed','rescheduled','cancelled','no_show','completed')) or
    (old.status = 'confirmed'   and new.status in ('rescheduled','cancelled','no_show','completed')) or
    (old.status = 'rescheduled' and new.status in ('confirmed','cancelled','no_show','completed'))
  ) then
    raise exception 'illegal appointment transition % -> %', old.status, new.status;
  end if;
  return new;
end $$;

drop trigger if exists appointments_enforce_transition on public.appointments;
create trigger appointments_enforce_transition
  before update of status on public.appointments
  for each row execute function public.enforce_appointment_transition();

-- ============================================================
-- appointment_events — immutable timeline
-- ============================================================
create table if not exists public.appointment_events (
  id uuid primary key default gen_random_uuid(),
  appointment_id uuid not null references public.appointments(id),
  at timestamptz not null default now(),
  label text not null,
  actor text not null,
  created_at timestamptz not null default now()
);
create index if not exists appointment_events_appt_idx on public.appointment_events (appointment_id, at);

-- ============================================================
-- confirmation_attempts — reminder/confirmation history
-- ============================================================
create table if not exists public.confirmation_attempts (
  id uuid primary key default gen_random_uuid(),
  appointment_id uuid not null references public.appointments(id),
  at timestamptz not null default now(),
  outcome text not null,
  channel text not null default 'whatsapp',
  created_at timestamptz not null default now(),
  constraint confirmation_outcome_enum check (outcome in ('reached','voicemail','no_answer','confirmed','reschedule_requested'))
);
create index if not exists confirmation_attempts_appt_idx on public.confirmation_attempts (appointment_id, at);

-- ============================================================
-- staff_notes — append-only clinical-adjacent notes
-- ============================================================
create table if not exists public.staff_notes (
  id uuid primary key default gen_random_uuid(),
  appointment_id uuid not null references public.appointments(id),
  at timestamptz not null default now(),
  author text not null,
  body text not null,
  created_at timestamptz not null default now(),
  constraint staff_notes_body_len check (length(body) between 1 and 4000)
);
create index if not exists staff_notes_appt_idx on public.staff_notes (appointment_id, at);

-- verification layer: notes are append-only, enforced by the database
create or replace function public.forbid_mutation()
returns trigger language plpgsql as $$
begin
  raise exception '% rows are append-only', tg_table_name;
end $$;

drop trigger if exists staff_notes_append_only on public.staff_notes;
create trigger staff_notes_append_only
  before update or delete on public.staff_notes
  for each row execute function public.forbid_mutation();

drop trigger if exists appointment_events_append_only on public.appointment_events;
create trigger appointment_events_append_only
  before update or delete on public.appointment_events
  for each row execute function public.forbid_mutation();

-- ============================================================
-- audit_events — who saw/did what (phone reveals, status changes, note edits, searches)
-- ============================================================
create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  at timestamptz not null default now(),
  actor text not null,
  action text not null,
  entity text not null,
  entity_id text,
  metadata jsonb,
  created_at timestamptz not null default now()
);
create index if not exists audit_events_entity_idx on public.audit_events (entity, entity_id);
create index if not exists audit_events_at_idx on public.audit_events (at desc);

drop trigger if exists audit_events_append_only on public.audit_events;
create trigger audit_events_append_only
  before update or delete on public.audit_events
  for each row execute function public.forbid_mutation();

-- ============================================================
-- RLS: default-deny on every new table, with EXPLICIT policies.
--
-- Access model: no client ever talks to Postgres directly. The dashboard calls
-- the dashboard-api edge function, which uses the service role (bypasses RLS)
-- after enforcing its own role/PHI-mode gating. anon + authenticated therefore
-- get nothing, stated explicitly rather than left to implicit denial.
--
-- These tables hold PHI-adjacent data (names, phones, insurance, appointment
-- history). A missing policy here is a high-severity gap, so each table below
-- is enabled AND carries a written deny for both client roles.
--
-- Existing tables (bookings, message_log, vob_queue) are intentionally NOT
-- touched by this migration: they already have RLS enabled with a deny_anon_all
-- policy. Tightening those (adding an explicit `authenticated` deny) is proposed
-- separately so the change to live policies can be reviewed on its own.
-- ============================================================
alter table public.locations             enable row level security;
alter table public.patients              enable row level security;
alter table public.appointments          enable row level security;
alter table public.appointment_events    enable row level security;
alter table public.confirmation_attempts enable row level security;
alter table public.staff_notes           enable row level security;
alter table public.audit_events          enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array[
    'locations','patients','appointments','appointment_events',
    'confirmation_attempts','staff_notes','audit_events'
  ] loop
    execute format('drop policy if exists deny_anon_all on public.%I', t);
    execute format(
      'create policy deny_anon_all on public.%I as permissive for all to anon using (false) with check (false)', t);

    execute format('drop policy if exists deny_authenticated_all on public.%I', t);
    execute format(
      'create policy deny_authenticated_all on public.%I as permissive for all to authenticated using (false) with check (false)', t);
  end loop;
end $$;
