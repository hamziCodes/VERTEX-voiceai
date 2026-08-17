-- Patient name quality gate.
--
-- Motivation (found in live backfilled data, 2026-07-09): the original
-- patients_name_not_garbage CHECK blocked literal '@' and digit runs, but callers
-- dictate contact details phonetically and ASR writes them out as words. Real rows
-- that slipped through:
--     "Hamzah zero five sulza n at gma I l. Dot c o m."   -> a spoken email address
--     "H A B I B A I M R A N"                             -> spelled-out letters
--     "Ya lo estoy"                                       -> Spanish "I already am"
--     "Like"                                              -> an ASR filler word
--     "Layla"                                             -> the AI agent's own name
--
-- A blank field is better than a wrong field (the agent prompt says so too), so a
-- name that fails this gate must never reach the normalized layer. Nothing is
-- deleted here: offending rows keep their raw string in full_legal_name_raw and are
-- flagged for a human.

-- ============================================================
-- 1. Quarantine columns (additive)
-- ============================================================
alter table public.patients add column if not exists full_legal_name_raw text;
alter table public.patients add column if not exists needs_review boolean not null default false;
alter table public.patients add column if not exists review_reasons text[] not null default '{}';

create index if not exists patients_needs_review_idx on public.patients (needs_review) where needs_review;

-- ============================================================
-- 2. Single source of truth for "is this plausibly a human legal name?"
--    Used by the CHECK below and mirrored by scripts/lib/util.js.
-- ============================================================
create or replace function public.is_valid_patient_name(name text)
returns boolean
language sql
immutable
as $$
  select
    name is not null
    and length(btrim(name)) between 2 and 60
    -- must start with a letter
    and btrim(name) ~ '^[[:alpha:]]'
    -- no literal email / digits
    and name !~ '@'
    and name !~ '[0-9]'
    -- phonetic email dictation: "... at gmail dot com", "dot com", "at gmail"
    and name !~* '\mdot\M'
    and name !~* '\mgmail\M|\myahoo\M|\mhotmail\M|\moutlook\M'
    and name !~* '\mat\M[[:space:][:punct:]]+[[:alpha:]]+[[:space:][:punct:]]+\mdot\M'
    -- spelled-out digits (two or more, e.g. "zero five", "one two three")
    and name !~* '\m(zero|one|two|three|four|five|six|seven|eight|nine)\M([[:space:][:punct:]]+\w+){0,3}[[:space:][:punct:]]+\m(zero|one|two|three|four|five|six|seven|eight|nine)\M'
    -- letter-by-letter spelling: 3+ consecutive single-letter "words" ("H A B I B A")
    and name !~* '(\m[[:alpha:]]\M[[:space:][:punct:]]+){3,}'
    -- conversational filler / non-names captured by ASR
    and lower(btrim(name)) not in (
      'like','yes','no','okay','ok','hello','hi','thanks','thank you','sure',
      'ya lo estoy','si','sí','claro','bueno','nothing','none','unknown','n/a','na',
      'test','patient','caller'
    )
    -- the AI agent must never be recorded as the patient
    and lower(btrim(name)) not in ('layla','vera')
$$;

comment on function public.is_valid_patient_name(text) is
  'Gate for patients.full_legal_name. Rejects dictated emails/phone numbers, spelled-out '
  'letters, ASR filler words, and the AI agents own names. Mirrored in scripts/lib/util.js.';

-- ============================================================
-- 3. Quarantine rows that already violate the gate (non-destructive).
--    Raw string is preserved; the display name falls back to a usable first name
--    from the originating booking when one exists, else an explicit placeholder.
-- ============================================================
with bad as (
  select id from public.patients where not public.is_valid_patient_name(full_legal_name)
)
update public.patients p
set
  full_legal_name_raw = coalesce(p.full_legal_name_raw, p.full_legal_name),
  full_legal_name     = coalesce(
    (
      select b.first_name
      from public.appointments a
      join public.bookings b on b.id = a.booking_id
      where a.patient_id = p.id
        and b.first_name is not null
        and public.is_valid_patient_name(b.first_name)
      order by b.created_at
      limit 1
    ),
    'Unknown Patient'
  ),
  needs_review  = true,
  review_reasons = (
    select array(select distinct unnest(p.review_reasons || array['name_capture_failed']))
  )
where p.id in (select id from bad);

-- ============================================================
-- 4. Enforce the gate. Replaces the weaker regex-only constraint.
-- ============================================================
alter table public.patients drop constraint if exists patients_name_not_garbage;
alter table public.patients drop constraint if exists patients_name_valid;
alter table public.patients
  add constraint patients_name_valid check (public.is_valid_patient_name(full_legal_name));

-- ============================================================
-- 5. Audit trail for the quarantine action itself.
-- ============================================================
insert into public.audit_events (actor, action, entity, entity_id, metadata)
select
  'system:migration',
  'patient_name_quarantined',
  'patient',
  p.id::text,
  jsonb_build_object('raw_name', p.full_legal_name_raw, 'replacement', p.full_legal_name)
from public.patients p
where p.needs_review
  and 'name_capture_failed' = any(p.review_reasons)
  and not exists (
    select 1 from public.audit_events ae
    where ae.entity = 'patient' and ae.entity_id = p.id::text
      and ae.action = 'patient_name_quarantined'
  );
