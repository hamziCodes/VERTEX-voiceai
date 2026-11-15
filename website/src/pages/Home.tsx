import { CallJourney } from '@/components/journey/CallJourney';
import { DemoSection } from '@/components/DemoSection';
import { BuildSection } from '@/components/BuildSection';
import { DevSpecimen } from '@/components/DevSpecimen';
import { TrailerSection } from '@/components/TrailerSection';
import { PipelineSection } from '@/components/PipelineSection';
import { EnterpriseSection } from '@/components/EnterpriseSection';
import { PrivacySection } from '@/components/PrivacySection';

/**
 * The immersive homepage (docs/design/IMMERSIVE_SCENARIO.md).
 *
 * PILOT — Scenes 0–4 are the pinned call journey (CallJourney): land → ring →
 * conversation flows out → interruption → the booking docks into the CRM.
 * The journey hands off into the existing interactive demo (Scene 5's
 * territory — the demo component and its four-language branching logic are
 * untouched), and the sections below it are the old beats, unchanged until
 * their own scenes are built in the next stages.
 *
 * Gates still wired, not just noted:
 * 1. The headline is "It picks up." — the "In Urdu." line returns only when
 *    URDU_AUDIO_READY flips with real engine audio (see CallJourney).
 * 2. No numbers anywhere in the journey. Latency, uptime and certification
 *    are unverified and stay off the page.
 * 3. No "CRM updated" claim: the journey's outcome is a booking docked into
 *    a CRM record with its confirmation sent — exactly what the demo script
 *    itself says.
 */
export default function Home() {
	return (
		<>
			<CallJourney />
			<DemoSection />

			{/* Below the pilot: the old beats, as-is, until Scenes 5–10 are
			    built. Beat 3 (businesses) still waits for real recordings. */}
			<BuildSection />
			<DevSpecimen />
			<TrailerSection />
			<PipelineSection />
			<PrivacySection />
			<EnterpriseSection />
		</>
	);
}
