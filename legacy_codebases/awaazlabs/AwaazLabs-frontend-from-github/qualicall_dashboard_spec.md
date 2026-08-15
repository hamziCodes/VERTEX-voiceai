1.4 Agent catalog the dashboard must surface
Receptionist: inbound call answering 24/7, appointment booking with direct EHR/calendar write, triage with safety escalation, intake capture


VOB Agent: outbound calls to insurance payers, verification of eligibility and benefits per patient, IVR navigation, benefit capture


Chat Agents: WhatsApp and landing-page web chat performing the receptionist function on text channels


Review Taker: outbound post-appointment calls requesting Google reviews


Reengagement Agent: outbound calls to lapsed patients and unconverted leads to book consultations and checkups


Custom agents: enterprise builds, must render in the same framework (see 2.6)


1.5 The Qualicall loop (product moat, must be visible) Every completed call is analyzed and graded by Qualicall. Grades feed an optimization decision: the agent either remains at peak or is flagged for tuning, and tuning events are applied and logged. The client dashboard must make this loop visible: per-call grades, aggregate quality trend, and a timeline of optimization events. This is the differentiator no competitor (Weave, NexHealth, Birdeye, Podium, Infinx-class tools) shows, and it is the centerpiece of the demo. See Section 12.
SECTION 2. GLOBAL ARCHITECTURE
2.1 Data modes The workspace runs in one of two modes, set by Awaaz admins per organization, never self-serve:
NON-PHI mode: aggregates and analytics only. No patient identity, no recordings, no transcripts, no patient-level rows. Appointments, VOB Queue, Conversations, and Audit Log render as aggregate-only or hidden.


PHI mode (BAA clients): full patient-level detail as specified in this document. Requires an executed BAA and data retention opt-in. Every page header renders a mode badge: NON-PHI or PHI-BAA. All specifications below describe PHI mode; NON-PHI degradation is noted per tab when non-obvious.


2.2 Roles and permissions Three roles minimum at launch:
Owner/Admin: everything, including Billing, Members, Audit Log, and consent settings


Manager: all operational tabs and patient-level data; no Billing, no Members, no Audit Log


Viewer: aggregate analytics and appointment list; no recordings, no transcripts, no phone-number reveal, no exports Permission checks are server-side. The UI hides what the role cannot access; the API independently rejects it.


2.3 Audit principle (applies everywhere) In PHI mode, the following actions always write an immutable audit event: login, phone-number reveal, recording playback, transcript view, patient search, export, note edit, appointment status change, VOB queue action, knowledge change request, consent list change, permission change. The Audit Log tab (Section 15) is the read surface; writes happen at the action layer and cannot be disabled.
2.4 Multi-location model Organization > Location > Agent. Every interaction, appointment, VOB, review request, and campaign row carries a location_id. A global location filter sits in the top bar and persists across tabs. Single-location clinics see no filter. This is mandatory in the data model at launch: the target buyer operates hundreds of clinics and will evaluate multi-location day one.
2.5 Patient data envelope (data minimization, locked) Patient-level surface is limited to: first name, last name (PHI mode, US market standard), phone (masked by default, click-to-reveal, audited), insurance carrier and member context captured for VOB, treatment/service interest, language, and operational metadata (timestamps, statuses, agent attribution). No DOB display, no SSN, no clinical notes, no diagnosis. The EHR remains the system of record for the patient; this dashboard is the system of record for interactions and outcomes.
2.6 Custom agent rendering framework Every agent, standard or custom, renders from the same schema: an agent registry entry (name, type, channel, icon), a metrics contract (list of KPI definitions it emits), and a standard analytics page template (stat cards, one primary chart, one distribution component, drill-through to interaction rows). Custom enterprise agents therefore get a dashboard page with zero frontend work. This is an explicit demo point for the enterprise conversation.
2.7 Localization and timezone All timestamps stored UTC, rendered in the location's configured timezone. UI ships English; the i18n framework is in place day one with Spanish as the second locale target (US market language mix already shows meaningful Spanish volume). Language of patient interactions is a data dimension throughout, separate from UI locale.
2.8 US compliance surfaces (cross-cutting)
HIPAA: BAA-gated PHI mode, audit log, role-based access, encryption in transit and at rest, retention per contract


TCPA and DNC: all outbound agents (Verifier, Review Taker, Reengagement) check a per-organization suppression list before dialing; consent basis is stored per contact; the client manages this in Settings > Consent and Do-Not-Call (Section 16.5)


Call recording consent: per-location setting for one-party vs two-party consent states; when two-party, the agent discloses recording at call start and the disclosure event is stored on the call record


Review solicitation policy: the Review Taker asks every eligible completed appointment without sentiment pre-filtering. Google prohibits review gating; the architecture must not implement a sentiment filter before the ask. Negative-experience handling routes to a private feedback flow after the review ask, not instead of it.


SECTION 3. NAVIGATION ARCHITECTURE
Top bar: organization switcher (multi-org users), location filter, mode badge, notifications bell, user menu.
Left navigation:
HOME
Overview


OPERATIONS
Appointments


Conversations (sub-views: Calls, Chats)


Escalations


VOB Queue


AGENTS
Receptionist


VOB Agent


Chat Agents


Review Taker


Reengagement


(custom agents append here from the registry)


QUALITY
Quality and Optimization (Qualicall client view)


Agent Knowledge


GROWTH
Reviews


Campaigns


INSIGHTS
Reports and Exports


COMPLIANCE (PHI mode only)
Audit Log


SETTINGS
Members


Usage and Billing


Organization and Locations


Lines and Numbers


Consent and Do-Not-Call


Notifications


Design rule: OPERATIONS is where staff work daily (actionable rows), AGENTS is where performance is reviewed (analytics), QUALITY is the trust and moat surface, GROWTH is where outbound value is proven. The demo narrative walks top to bottom in exactly this order.

SECTION 4. OVERVIEW TAB
Purpose: the daily-glance page for the clinic owner and manager. Order of sections is a product decision: business outcomes first (appointments, VOB), operational telemetry second. Every card is a click-through to the tab that owns the underlying data.
4.1 Section A: Appointments (top of page) Stat cards:
Appointments booked today (count, delta vs same weekday last week)


Appointments booked this week (count plus booking rate: booked divided by completed inbound interactions)


Upcoming next 7 days (count; click-through to Appointments filtered to upcoming)


No-shows and cancellations this week (count plus rate; card hides if outcome data unavailable for this clinic, never render misleading zeros) Chart: Bookings over time, 7D/30D toggle, stacked by source (Voice, WhatsApp, Web Chat).


4.2 Section B: VOB status Stat cards:
VOB in progress (statuses: queued, dialing, on call with payer, pending callback)


VOB completed today and this week, with verified rate percentage


Needs attention (sum of unable to verify, member not found, inactive policy; red accent; click-through to VOB Queue pre-filtered) Component: compact horizontal status distribution bar mirroring the VOB tab chart.


4.3 Section C: Revenue recovered (estimate) Single card: estimated revenue recovered this month, computed as (after-hours bookings + reengagement bookings + recovered no-shows) multiplied by the clinic-configured average appointment value. Labeled clearly as an estimate. Configuration lives in Organization settings; card hides if average value is unset. Tooltip shows the formula and inputs.
4.4 Section D: Quality pulse One row: current aggregate call quality grade (from Qualicall, e.g. 92/100), 30-day trend sparkline, and count of optimization events this month. Click-through to Quality and Optimization. This puts the moat on the first screen.
4.5 Section E: Operational telemetry
Interactions row: per-agent interaction counts plus Overall and All


Calls today, minutes today, average duration, average cost per interaction


Calls over time and minutes over time charts (7D/30D)


Average first-audio response time (ms) with target line at 800 ms


Success rate (completed divided by attempted) with completion counts


Live calls now, with refresh timestamp


4.6 Section F: Attention banner (conditional) A dismissible red banner renders above Section A when any of the following are true: unacknowledged escalation older than the configured threshold, VOB needs-attention items older than 48 hours, any line health check failing, or usage at 90 percent or more of plan minutes. Each condition deep-links to its owning surface.
SECTION 5. APPOINTMENTS TAB
Purpose: the working surface for front desk staff. Table-first; calendar view is a secondary toggle.
5.1 Header stats strip Booked today, upcoming 7 days, confirmation rate (confirmed divided by booked with a scheduled confirmation attempt), no-show rate trailing 30 days.
5.2 Appointments table (paginated, server-side filtering and sorting) Columns:
Date and time (location timezone, default sort upcoming ascending)


Patient name (first plus last)


Phone (masked as pattern, click-to-reveal, reveal audited)


Treatment or service interest


Source (Voice, WhatsApp, Web Chat, Form)


Language


Insurance captured (yes/no badge)


VOB status chip (Verified, Partial, Needs auth, Needs referral, Not covered, or none) linking to the VOB record


Triage flag (None, Low, High, Urgent; red accents on High and Urgent)


Status (Booked, Confirmed, Rescheduled, Cancelled, Completed, No-show)


Booked by (agent name and timestamp)


Location (when multi-location)


5.3 Filters Date range, status, source, VOB status, triage flag, language, location, free-text search on name and phone (search is audited in PHI mode).
5.4 Detail drawer (row click, slide-over)
Full appointment record with unmask-on-demand fields


Originating interaction link: opens the call or chat with recording, transcript, and QA grade


VOB card when a verification exists: payer, coverage status, copay, deductible, out-of-pocket, prior auth flag, timestamp, link to the queue record


Confirmation and reminder history: each Verifier attempt with outcome (reached, voicemail, no answer, confirmed, reschedule requested)


Timeline: booked, confirmation sent, confirmed or rescheduled, outcome; every event timestamped with actor


Outcome control: manual buttons for Completed and No-show for clinics without calendar write-back; this is the universal fallback and feeds the no-show analytics


Staff notes (append-only, audited)


Flag this interaction button (routes to Qualicall priority review, see Section 12.5)


5.5 Calendar view (secondary) Day and week agenda rendering of the same data with the same filters. No drag-to-reschedule in this build; rescheduling remains an agent or EHR action.
5.6 Empty and degraded states No appointments yet: explanatory empty state. EHR sync unavailable: banner stating outcomes are manual-entry until sync restores. NON-PHI mode: tab renders aggregate counts only, table hidden.
SECTION 6. RECEPTIONIST TAB (agent analytics)
Purpose: performance of the inbound voice agent.
6.1 Stat cards
Appointments booked (count, with completed inbound calls denominator)


Booking rate percentage, with healthcare scheduling FCR benchmark reference (~75 percent)


Safety escalation rate percentage (triage High plus Urgent share), info tooltip explaining the triage model


Insurance capture rate percentage (front-end capture reduces downstream denials)


WhatsApp deflection-suitable rate percentage


Average booking handle time


After-hours share of bookings (percentage of bookings occurring outside configured business hours; this is the recovery story rendered as a metric)


Missed and abandoned inbound (count of inbound legs that ended before agent connect; target near zero)


6.2 Charts and distributions
Triage distribution donut (None, Low, High, Urgent or Emergency)


Intake method donut (Form, Voice, Unknown)


Language mix horizontal bars (en, es, other)


Bookings by hour-of-day heatmap split business hours vs after hours


Booking rate trend, 7D/30D


6.3 Drill-through Every card and chart segment filters into Conversations > Calls scoped to the Receptionist agent.
SECTION 7. VOB AGENT TAB (agent analytics)
Purpose: eligibility and benefits verification performance. Industry pattern (Infinx, pVerify class): analytics here, actionable worklist in VOB Queue.
7.1 Stat cards
Verifications (count, period selector)


Verified rate percentage


Partial coverage, Needs authorization, Needs referral, Not covered, Inactive policy, Unable to verify (each as percentage with count on hover)


Prior auth required percentage, with note that catching this pre-visit protects revenue


Referral required percentage


IVR navigation success percentage


Benefit capture completeness percentage, decomposed into copay captured, deductible captured, out-of-pocket max captured (three sub-bars; completeness tracks clean-claim rate, industry target 95 percent plus)


Member not found (count and share)


Payer reps reached (count)


Average handle time per call, plus turnaround time per verification (request to terminal status, median and P95; these are different numbers and both matter)


7.2 Charts
VOB status distribution horizontal bars (sums to 100 percent)


Verifications over time


Payer breakdown table: per payer, verification count, verified rate, average handle time, unable-to-verify rate. This is where a billing company spots problem payers, and the distributor audience is a billing company; make this table prominent.


7.3 Canonical VOB status model (single source of truth across Overview, this tab, VOB Queue, and the Appointments chip) queued > in_progress (dialing, on_call, pending_callback) > terminal Terminal statuses: verified, partial_coverage, needs_authorization, needs_referral, not_covered, inactive_policy, member_not_found, unable_to_verify. Everything terminal other than verified is a needs-attention state and appears in the VOB Queue worklist.
SECTION 8. VOB QUEUE TAB (worklist)
Purpose: the actionable per-verification surface, exception-driven, following the Infinx and pVerify worklist pattern.
8.1 Worklist table Columns: patient name, payer, plan, status (canonical model above), linked appointment date, assigned-to (clinic staff member, optional), age in queue, last attempt timestamp, attempts count, location. Row aging SLA indicator: amber past 24 hours in a non-terminal state, red past 48 hours.
8.2 Row detail drawer Verification record: captured benefits (copay, deductible, out-of-pocket, coverage notes), prior auth and referral flags, per-attempt call log with recordings and transcripts (PHI mode, audited), payer reference numbers captured on the call.
8.3 Row actions Retry (re-queue the verification), Mark resolved (with reason picker: verified manually, patient rescheduled, patient cancelled, other), Escalate to staff (assigns and notifies), Add note. Every action writes an audit event and updates the status timeline.
8.4 Queue-level controls Filters by status, payer, age, assigned-to, location. Bulk retry on filtered selection. CSV export (audited, role-gated).

SECTION 9. CHAT AGENTS TAB (agent analytics)
Purpose: performance of the WhatsApp and landing-page chat agents, which perform the receptionist function on text channels.
9.1 Stat cards
Sessions (count, period selector), split by channel: WhatsApp vs Web Chat


Average messages per session


Containment rate percentage (sessions fully handled by the agent)


Resolution rate percentage (sessions where the patient's goal was met)


Paired reading rule rendered in the UI: high containment with low resolution is false containment; the two cards sit adjacent with a shared caption


Deflection rate (sessions successfully moved from an intended call to chat completion)


Escalation rate (sessions handed to a human)


Bookings from chat (count plus conversion rate: bookings divided by sessions with booking intent)


Average response latency and P95 response latency, target line under 800 ms


CSAT proxy score out of 5


9.2 Charts
Containment vs Resolution vs Deflection vs Escalation grouped bars


Sessions over time by channel


Intent distribution (booking, pricing, hours and directions, insurance question, clinical question routed, other)


Language mix


9.3 Drill-through All cards filter into Conversations > Chats.
SECTION 10. CONVERSATIONS TAB
Purpose: the unified interaction record. This is where a clinic answers the question "what exactly did the agent say to my patient." Two sub-views sharing one filter bar.
10.1 Sub-view: Calls Table columns: timestamp, direction (inbound, outbound), agent (Receptionist, VOB, Verifier, Review Taker, Reengagement), patient name where matched, phone (masked), duration, disposition (booked, info only, verified, confirmed, review requested, reengaged-booked, escalated, voicemail, no answer, abandoned), triage flag, QA grade (numeric badge from Qualicall), location. Row detail drawer:
Audio player for the recording (role-gated, playback audited)


Full transcript with speaker labels and PII redaction markers


Recording-consent disclosure event shown when two-party consent mode was active


QA grade breakdown (see Section 12.3) inline


Linked objects: appointment created, VOB record, review request, campaign


Flag this interaction button


10.2 Sub-view: Chats Thread list: patient name where matched, channel, last message time, session outcome (contained, resolved, escalated, booked), message count. Thread detail: full transcript with timestamps, handoff markers where a human took over, linked appointment, flag button. Same audit rules as call playback.
10.3 Filters (shared) Date range, agent, channel, direction, disposition, triage, QA grade band, location, free-text search (audited).
10.4 NON-PHI degradation Aggregate counts only; no rows, no recordings, no transcripts.
SECTION 11. ESCALATIONS TAB
Purpose: every safety escalation and clinical-question routing in one accountable surface. For the clinic this is the safety audit trail; for Awaaz it is live proof that the hard-coded clinical boundary works.
11.1 Table Columns: timestamp, patient name, source interaction (call or chat link), trigger (triage High, Urgent or Emergency, clinical question, caller requested human, agent-initiated), routed to (staff member or forwarding number), acknowledged (yes/no with timestamp), resolution note, location.
11.2 Acknowledgement workflow Escalations arrive unacknowledged. Any Manager or Owner can acknowledge (one tap, audited) and append an outcome note. Unacknowledged escalations older than the configured threshold (default 30 minutes for Urgent, 4 hours otherwise) trigger the Overview attention banner and a notification per the matrix in Section 16.6.
11.3 Stat strip Escalations this week, acknowledgement rate, median time to acknowledge, breakdown by trigger.
SECTION 12 PREVIEW NOTE Quality and Optimization (the Qualicall loop) is specified in Part 4 as Section 12 so that the moat surface, knowledge, reports, audit, and settings sit together in the final part.
SECTION 13. REVIEW TAKER TAB (agent analytics) AND REVIEWS TAB
13.1 Review Taker agent tab Purpose: performance of the outbound post-appointment review agent. Eligibility pipeline shown as a funnel: completed appointments > eligible (consent present, not suppressed, within recency window) > called > reached > review ask delivered > agreed > link sent (SMS) > review posted (attributed). Stat cards:
Review calls placed, patients reached, reach rate


Agreement rate (agreed divided by asks delivered)


Link-send rate and link-click rate


Reviews posted, attributed (via tracked link or Google Business Profile delta within the attribution window; label the attribution method in a tooltip)


Average rating of attributed reviews


Opt-outs generated (each writes to the suppression list automatically)


Average call duration Compliance note rendered in the UI and enforced in the pipeline: every eligible patient receives the ask; no sentiment pre-filtering before the ask (review gating violates Google policy). Patients expressing a negative experience are routed to a private feedback capture after the ask; those private feedback items appear in this tab as a separate list for the clinic to action.


13.2 Reviews tab (GROWTH section) Purpose: the outcome surface for reputation.
Rating trend chart: Google rating over time with review-agent go-live marked as an annotation line


Reviews over time: attributed vs organic stacked bars


Recent attributed reviews list: date, rating, excerpt, link to the live review


Private feedback list: date, patient, summary, source call link, status (new, actioned)


Location comparison table when multi-location: per location, rating, attributed reviews this month, agreement rate Scope boundary: this tab reports outcomes of the Review Taker agent. It is not a reputation management suite; no review responding, no listings management, no social publishing (Birdeye and Podium territory, out of scope by design).


SECTION 14. REENGAGEMENT TAB (agent analytics) AND CAMPAIGNS TAB
14.1 Reengagement agent tab Purpose: performance of the outbound agent that follows up with lapsed patients and unconverted leads. Funnel: audience > contacted > reached > conversation completed > booking intent > booked. Stat cards:
Contacts attempted, reached, reach rate


Conversations completed


Bookings generated (count plus conversion rate from reached)


Revenue estimate from reengagement bookings (bookings multiplied by configured average appointment value; feeds the Overview revenue card)


Opt-outs generated (auto-writes to suppression)


Best contact window analysis: reach rate by hour-of-day and day-of-week heatmap


Average attempts per successful booking


14.2 Campaigns tab (GROWTH section) Purpose: the management surface for outbound audiences and runs. All outbound campaign types render here: reengagement (lapsed patients, unconverted leads), no-show recovery, and recall. Campaign list: name, type, audience size, status (draft, scheduled, running, paused, completed), started, progress (contacted divided by audience), bookings to date, location. Campaign detail:
Funnel identical to 14.1 scoped to the campaign


Audience definition summary (segment rules, e.g. no visit in 6 months, treatment interest X)


Per-contact rows: name, phone masked, attempts, last outcome, booked link, opt-out flag


Pacing settings display: calling window (respects location timezone and configured quiet hours), max attempts, retry spacing


Pause and resume controls (Owner and Manager, audited) Guardrails enforced by the platform and displayed read-only: suppression list checked before every dial, TCPA calling window enforcement, per-contact attempt caps. Audience creation in v1 is a request-to-Awaaz workflow (same pattern as knowledge change requests); self-serve segment building is deliberately deferred.




Part 4 of 4.

SECTION 12. QUALITY AND OPTIMIZATION TAB (the Qualicall loop)
Purpose: the client-visible rendering of the product moat. Every completed interaction is analyzed and graded; grades drive an optimization decision; optimizations are applied and logged. This tab shows the clinic that the system is not static software but a self-improving agent under continuous supervision. This is the centerpiece of the enterprise demo.
12.1 Header: the loop, visualized A four-stage horizontal loop graphic with live counts for the selected period: Calls completed > Analyzed and graded > Flagged for optimization > Optimizations applied. Each stage is a click-through filter.
12.2 Aggregate quality
Current quality score (0 to 100, weighted aggregate across dimensions)


30-day and 90-day trend line with optimization events plotted as markers on the line, so the clinic sees grade improvements following each tuning event


Grade distribution histogram (share of calls per grade band)


Per-agent quality table: agent, calls graded, average grade, trend arrow, open optimization items


12.3 Grading dimensions (per-call and aggregate) Each call receives sub-scores that roll into the overall grade:
Accuracy: information given matched the knowledge base


Compliance: required disclosures made, clinical boundary respected, consent language delivered where applicable


Conversation quality: tone, interruptions handling, proper opening and closing


Task completion: did the call achieve its objective (booking, verification, confirmation, review ask)


Efficiency: handle time vs benchmark for the call type The per-call grade badge in Conversations expands to this breakdown.


12.4 Optimization events timeline Reverse-chronological feed, client-safe language: each entry shows date, agent affected, what was detected (e.g. "calls ending without a proper closing detected across 12 calls"), what was changed (e.g. "closing sequence updated"), status (detected, in tuning, deployed, verified), and the grade delta measured after deployment. Internal tuning mechanics (prompts, model configuration, reviewer identity) are never exposed. The event vocabulary is a controlled list maintained by Awaaz ops.
12.5 Flagged interactions All client-submitted flags (from the Flag this interaction button across Appointments, Conversations, VOB Queue) land here as priority items with status: submitted, under review, resolved, with resolution note. This closes the loop publicly: the clinic flags, Awaaz reviews, the fix appears in the optimization timeline.
12.6 Compliance sub-panel Clinical boundary adherence rate (share of clinical questions correctly routed, target 100 percent, sourced from grading dimension two), disclosure delivery rate, and escalation correctness rate. These three numbers are the governance story in metric form.
SECTION 13 AND 14: specified in Part 3.
SECTION 15. AGENT KNOWLEDGE TAB
Purpose: answers the clinic owner's biggest trust question: what is this system telling my patients. Read-only with a controlled change workflow.
15.1 Knowledge view Structured, per-location where applicable: services and treatments list, pricing displayed to patients, providers and their schedules summary, business hours and holiday calendar, insurance carriers accepted, FAQ answers, booking rules (buffer times, new vs returning patient rules), escalation routing map (which triggers route where).
15.2 Change request workflow Request an update button on every knowledge block: proposed change plus reason, submitted to Awaaz ops. Status tracking per request: requested, in review, scheduled, live, with timestamps. Every state change notifies the requester. Deliberately no self-serve editing in this build: uncontrolled knowledge edits are how the clinical boundary and compliance language degrade; every change passes Awaaz review. Version history list: what changed, when, requested by whom.
SECTION 16. REMAINING TABS
16.1 Reports and Exports (INSIGHTS)
Scheduled reports: weekly and monthly PDF summaries (appointments, VOB, conversations, quality, reviews, campaigns) emailed to configured recipients; per-location and consolidated variants


On-demand CSV export per operational table (Appointments, VOB Queue, Conversations, Campaigns contacts), role-gated to Owner and Manager, every export audited with row-count and filter parameters recorded


Monthly business review pack: a one-click generated deck-style PDF combining outcomes, quality trend, and revenue-recovered estimate; built for the clinic to show its own stakeholders


16.2 Audit Log (COMPLIANCE, PHI mode only, Owner only) Immutable, append-only. Columns: timestamp (UTC plus location timezone), actor, role, event type, object reference, IP, user agent. Event types per Section 2.3. Filters: actor, event type, date range, object. Export available; the export action itself writes an audit event. Retention per contract term. This tab is a contractual deliverable of the BAA tier and ships with the first PHI client, not after.
16.3 Members (SETTINGS) User list with role, last active, MFA status. Invite by email with role assignment (Owner only). Role changes audited. MFA required for Owner and Manager in PHI mode.
16.4 Usage and Billing (SETTINGS)
Minutes consumed vs plan allocation, current cycle, with projection to cycle end


Consumption breakdown by agent and by location


Chat sessions consumed (metered separately from voice minutes; display both meters)


Overage indicator and history of past cycles


Invoice list with download No plan or price editing in the client dashboard; plan changes are an account-manager workflow.


16.5 Organization and Locations, Lines and Numbers, Consent and Do-Not-Call (SETTINGS)
Organization and Locations: org profile, average appointment value configuration (feeds revenue cards), location list with timezone, business hours, holiday calendar per location


Lines and Numbers: connected phone numbers and WhatsApp senders per location, per-line health indicator (green/red with last-checked timestamp), escalation forwarding target, recording-consent mode per location (one-party or two-party)


Consent and Do-Not-Call: suppression list view (phone, source of suppression: patient opt-out, manual add, complaint), manual add and remove (audited, Owner and Manager), consent basis field per contact where captured, quiet-hours configuration for outbound calling windows


16.6 Notifications (SETTINGS) Preference matrix: event type (escalation unacknowledged, VOB needs-attention aging, line health failure, usage threshold, weekly report, monthly report, knowledge request status change, flag resolution) by channel (email, SMS, in-app) by role. Escalation alerts default on and cannot be fully disabled for the Owner role.
SECTION 17. APPENDIX A: CANONICAL STATUS MODELS
Appointment: booked > confirmed > (rescheduled loops to confirmed) > completed | cancelled | no_show


VOB: per Section 7.3


Escalation: open > acknowledged > resolved


Review request: eligible > called > reached > asked > agreed > link_sent > posted | declined | opt_out


Campaign contact: queued > attempted > reached > booked | exhausted | opt_out


Flag: submitted > under_review > resolved


Optimization event: detected > in_tuning > deployed > verified


Call disposition: booked, info_only, verified, confirmed, review_requested, reengaged_booked, escalated, voicemail, no_answer, abandoned One shared enum definition per model in the codebase; UI chips, filters, and API all reference it.


SECTION 18. APPENDIX B: COMPETITIVE POSITION SUMMARY
NexHealth and Weave own the appointment-and-communication layer: prebuilt appointment dashboards, no-show and cancellation tracking, call analytics. Our Appointments, Overview, and Conversations surfaces match that expectation set.


Infinx and pVerify class tools own eligibility: status-driven worklists, benefit capture depth, payer analytics, audit logging. Our VOB Agent and VOB Queue surfaces match that pattern, with the payer breakdown table as the surface a billing distributor evaluates first.


Birdeye and Podium own reputation: review generation funnels and rating trends. Our Reviews surface reports the same outcomes scoped to our agent, deliberately without their management suite.


No competitor surfaces a per-call grading and optimization loop to the client. Section 12 is the differentiated screen; the demo should end there.


SECTION 19. BUILD PRIORITY ORDER (for the 24-hour sprint) Sequence for a demo-complete build, in strict order:
Global frame: navigation, mode badge, roles, location filter (2.1 to 2.4)


Overview restructure with all six sections (Section 4)


Appointments tab: table, filters, drawer, manual outcome control (Section 5)


Canonical status enums (Section 17) wired into VOB tab and VOB Queue worklist with row actions (Sections 7, 8)


Conversations: calls sub-view with recording, transcript, grade badge; chats sub-view (Section 10)


Quality and Optimization: loop header, trend with event markers, optimization timeline, flag inbox (Section 12). Seed with realistic demo data including at least one detected-to-verified optimization event showing a grade lift.


Review Taker funnel and Reviews tab; Reengagement funnel and Campaigns tab (Sections 13, 14)


Escalations with acknowledgement flow (Section 11)


Agent Knowledge read-only with change-request stub (Section 15)


Settings: Usage meters, Lines health, Consent list, Notifications matrix (Section 16)


Reports: on-demand CSV plus one scheduled-report mock; Audit Log table (16.1, 16.2) Anything cut under time pressure comes from the bottom of this list, never the top. Items 1 through 6 are the demo spine and are not negotiable.


END OF DOCUMENT

seed the Quality tab with demo data that shows one full loop cycle (issue detected, fix deployed, grade improved).
