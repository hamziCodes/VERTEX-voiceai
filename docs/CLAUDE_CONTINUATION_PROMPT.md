# Claude continuation prompt — Wavia Engine

You are continuing the Wavia engine on a new machine. Work from the repository and the recorded evidence; do not assume a phase is complete because code exists.

1. Clone the public repository and check out the required branch:

   ```powershell
   git clone https://github.com/hamziCodes/VERTEX-voiceai.git
   Set-Location VERTEX-voiceai
   git switch wavia-fixv1
   git status --short --branch
   ```

2. Before writing code, read these files in this exact order:

   1. `docs/HANDOVER_TO_CLAUDE.md`
   2. `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md`
   3. `Codex Fix/EXECUTION_TRACKER.md`
   4. `Codex Fix/HUMAN_INPUT.md`
   5. `Codex Fix/IMPLEMENTATION.md` and `Codex Fix/TRACEABILITY.md`
   6. `Codex Fix/phases/13h-customer-access-shell-completion-implementation-plan.md`
   7. Relevant Phase 13 evidence, especially `Codex Fix/evidence/phase-13g/VERIFICATION.md`
   8. `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md`
   9. `docs/DESIGN.md`
   10. `docs/design/design-tokens.json`
   11. `README.md`, `docs/deploy/COMPOSE_QUICKSTART.md`, `.env.example`, `infra/docker/.env.example` and `docs/developer/env/.env.example`

   Save the standing project context from the handover into your persistent project memory before implementation. The saved `DESIGN.md` and `design-tokens.json` together govern all dashboard frontend work going forward: understand them first, then improve/build against them. Do not edit either reference file unless Hamzi explicitly asks.

3. Set up the machine exactly as `docs/HANDOVER_TO_CLAUDE.md` describes. Copy the environment templates to local `.env` files, leave every value as a placeholder until Hamzi supplies the applicable manual values, and tell Hamzi exactly which named values must be filled. Never ask for or echo a secret in chat. Keep `RUN_LIVE_PROVIDERS=0` and `RUN_LIVE_TELEPHONY=0`.

4. Verify the setup with the safe test/build commands from the handover. Report the exact result and label missing local dependencies/configuration honestly; do not substitute a claim that a test passed.

5. Confirm back to Hamzi: the repository/branch/HEAD, recorded phase status, clean stop point and that you are resuming at **Phase 13H Task 7 — Workspace Settings and Members management**. Then start that task without waiting for further instructions.

6. Implement only Task 7 first. Follow its failure-first test plan: member list permissions, exact five launch roles, tenant-admin warning, one-time invitation reveal without storage/logging, role changes, removal confirmation, last-admin protection and expired/replayed invitation handling. Require `member:read` to view and `member:write` to mutate; repeat authorization server-side. Run focused Vitest and the offline Playwright journey, inspect for token/secret/cross-tenant leakage, then make the single task commit:

   ```text
   feat(studio): add workspace member management
   ```

   Do not begin Phase 13H Task 8 until Task 7 is committed and its focused verification passes.

7. Work as follows throughout:

   - Work only on `wavia-fixv1`; never push to `main` or force-push.
   - Make small, atomic commits and push clean checkpoints.
   - Make a rollback commit before risky multi-file changes.
   - Never read or expose secret values/raw key files. Never commit `.env`, invitation tokens, credentials or customer data.
   - Do not touch `.github/workflows`, deploy, publish, buy numbers, make real calls, use paid production providers or spend money without Hamzi's explicit approval.
   - Treat FastAPI/control plane as the authorization and domain authority. Studio is not an authorization boundary.
   - Keep production session configuration immutable and published-plan-driven. Test doubles must be explicit and must never mimic production success.
   - Record exact verification commands/results and label unverified items honestly.
   - Treat acoustic end-of-speech to first audible agent sample as the latency metric. Do not trade away transcript retention, audio continuity, interruption correctness or tenant safety for a misleading timing improvement.

8. Make normal technical decisions yourself and document them in the phase evidence/trackers the same way Codex did. Stop and ask Hamzi only when an action is irreversible, involves live calls/production providers/spending, requires deployment/publication or external coordination, changes material product scope, or when repository evidence contradicts itself and cannot be resolved from the repository.

After Task 7, execute Phase 13H Task 8's complete close gate, update evidence/tracker truthfully, commit `test(studio): close phase 13h customer foundation`, stop for review, and only then proceed to the later Studio/operations/release phases in the order stated by the handover.
