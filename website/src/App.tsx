/**
 * ⚠️ ROUTING RULES:
 * - Router is in main.tsx. Do NOT add another <BrowserRouter> here or anywhere.
 * - Use <Routes> + <Route> components ONLY. Do NOT use useRoutes().
 * - STATIC IMPORTS ONLY — no React.lazy() or dynamic import().
 * - Import from 'react-router' — NOT 'react-router-dom' (does not exist).
 *
 * Route skeleton per docs/design/scroll-story.md §4. Sub-brand routes exist and
 * are placeholders until their sessions (Core/Studio = 3, Shield = 6). Legacy
 * URLs redirect permanently rather than 404, and the old page components are
 * kept on disk as copy sources for the rebuild.
 */
import { Routes, Route, Navigate } from 'react-router';
import { MotionConfig } from 'motion/react';
import { Layout } from '@/components/Layout';
import Home from '@/pages/Home';
import HowItWorks from '@/pages/HowItWorks';
import Pricing from '@/pages/Pricing';
import About from '@/pages/About';
import Contact from '@/pages/Contact';
import Privacy from '@/pages/Privacy';
import Terms from '@/pages/Terms';
import { Placeholder } from '@/pages/Placeholder';

export default function App() {
	return (
		<MotionConfig reducedMotion="user">
			<Layout>
				<Routes>
					<Route path="/" element={<Home />} />

					{/* Sitemap routes */}
					<Route
						path="/core"
						element={
							<Placeholder
								label="04 — Build"
								title="Wavia Core"
								note="The engine, the SDK and everything past the nine-line specimen. The specimen itself is on the home page, labelled a preview because the package is not on npm yet."
								next="Ships after gate 8: the real package name, method names and the interruptible flag. Until those are confirmed, this page would be inventing an API."
							/>
						}
					/>
					<Route
						path="/studio"
						element={
							<Placeholder
								label="02 — Done for you"
								title="Wavia Studio"
								note="The no-code path: name it, pick a voice, set your hours, connect your number. The app does not exist yet, so this page's CTA is a waitlist until it does."
								next="Ships in Session 2 (custom setup + businesses). No fake dashboard screenshot goes on this page, ever."
							/>
						}
					/>
					<Route
						path="/shield"
						element={
							<Placeholder
								label="11 — Shield"
								title="Wavia Shield"
								note="For the calls a business cannot get wrong: dedicated VPC or on-prem, SIP into the PBX you already own, a named architect."
								next="Ships in Session 6. The compliance wording stays gated until certification status is confirmed — no HIPAA or SOC 2 badge renders before then."
							/>
						}
					/>
					<Route path="/pricing" element={<Pricing />} />
					<Route path="/how-it-works" element={<HowItWorks />} />
					<Route path="/about" element={<About />} />
					<Route path="/contact" element={<Contact />} />
					<Route path="/privacy" element={<Privacy />} />
					<Route path="/terms" element={<Terms />} />
					<Route
						path="/status"
						element={
							<Placeholder
								label="Status"
								title="Uptime & incidents"
								note="Where uptime gets audited. There is no status feed yet, which is exactly why the site carries no uptime figure at all."
								next="Ships in Session 7 (polish), as a third-party status page or a static page fed by it."
							/>
						}
					/>

					{/* Permanent redirects from the pre-rebuild URLs */}
					<Route path="/for-developers" element={<Navigate to="/core" replace />} />
					<Route path="/enterprise" element={<Navigate to="/shield" replace />} />
					<Route path="/get-started" element={<Navigate to="/studio" replace />} />
					<Route path="/login" element={<Navigate to="/studio" replace />} />
				</Routes>
			</Layout>
		</MotionConfig>
	);
}
