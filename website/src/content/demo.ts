/**
 * Beat 1 demo content — the branching script, in all four product languages.
 *
 * This is a *scripted* demo, not a live session: the visitor picks the caller's
 * lines and every reply is pre-written. The card says so in its own header.
 *
 * There is no audio. Recordings from the engine are gate 8.5, and until they
 * exist the card shows the transcript. When they land, each node gains a clip
 * per language and the player takes over — the tree shape, the interruption
 * branches and the scenario stay exactly as they are.
 *
 * LANGUAGE QUALITY — read before editing:
 * The English and Urdu scripts are ours and reviewed. The Arabic and Malay
 * scripts are drafts written by a non-native writer so the four-language claim
 * is demonstrable, and they are flagged as UNVERIFIED in
 * docs/design/PROGRESS.md. A fluent speaker must read both before public
 * launch. Do not mark them verified here.
 */

export type DemoLang = 'en' | 'ur' | 'ar' | 'ms';

/** One line of the call, in every language the product speaks. */
export type DemoTurn = Record<DemoLang, string>;

export type DemoLine = {
	from: 'wavia' | 'caller';
	text: DemoTurn;
	/** Set when this line cut the assistant off mid-sentence. */
	cutAfterMs?: number;
};

export type DemoOption = {
	text: DemoTurn;
	next: string;
	/** Marked options truncate the trace and are announced as an interruption. */
	interrupt?: boolean;
};

export type DemoNode = {
	id: string;
	line: DemoLine;
	options?: DemoOption[];
};

/** Text in the order this file reads it: en, ur, ar, ms. */
const L = (en: string, ur: string, ar: string, ms: string): DemoTurn => ({ en, ur, ar, ms });

export const DEMO_START = 'start';

export const DEMO_NODES: Record<string, DemoNode> = {
	start: {
		id: 'start',
		line: {
			from: 'wavia',
			text: L(
				'Good evening, this is the clinic. How can I help?',
				'السلام علیکم، یہ کلینک ہے۔ میں آپ کی کیا مدد کر سکتا ہوں؟',
				'مساء الخير، هذه العيادة. كيف أساعدك؟',
				'Selamat malam, ini klinik. Bagaimana saya boleh membantu?',
			),
		},
		options: [
			{
				text: L(
					"I'd like an appointment tomorrow.",
					'مجھے کل کی اپائنٹمنٹ چاہیے۔',
					'أريد موعدًا غدًا.',
					'Saya mahu buat temujanji untuk esok.',
				),
				next: 'slot',
			},
			{
				text: L(
					'Can you speak English?',
					'کیا آپ انگریزی بول سکتے ہیں؟',
					'هل تتحدث الإنجليزية؟',
					'Boleh anda bercakap bahasa Inggeris?',
				),
				next: 'switch',
			},
			{
				text: L(
					'Wait — I said Thursday.',
					'رکیے — میں نے جمعرات کہا تھا۔',
					'لحظة — قلت الخميس.',
					'Tunggu — saya kata hari Khamis tadi.',
				),
				next: 'thursday',
				interrupt: true,
			},
		],
	},

	slot: {
		id: 'slot',
		line: {
			from: 'wavia',
			text: L(
				'Tomorrow at ten in the morning or four in the afternoon — which suits you?',
				'ٹھیک ہے۔ کل صبح دس بجے یا شام چار بجے — کون سا وقت ٹھیک ہے؟',
				'غدًا الساعة العاشرة صباحًا أو الرابعة عصرًا — أي وقت يناسبك؟',
				'Esok pukul sepuluh pagi atau pukul empat petang — yang mana sesuai?',
			),
		},
		options: [
			{
				text: L('Ten works.', 'دس بجے ٹھیک ہے۔', 'العاشرة مناسبة.', 'Pukul sepuluh sesuai.'),
				next: 'booked',
			},
			{
				text: L('Four.', 'چار بجے۔', 'الرابعة.', 'Pukul empat.'),
				next: 'booked',
			},
			{
				text: L(
					'No — I said Thursday.',
					'نہیں، میں نے جمعرات کہا تھا۔',
					'لا، قلت الخميس.',
					'Tidak, saya kata hari Khamis tadi.',
				),
				next: 'thursday',
				interrupt: true,
			},
		],
	},

	thursday: {
		id: 'thursday',
		line: {
			from: 'wavia',
			text: L(
				'Sorry about that. Thursday — ten in the morning, or four in the afternoon?',
				'معاف کیجیے۔ جمعرات، صبح دس بجے یا شام چار بجے؟',
				'عذرًا، لم أسمعك جيدًا. الخميس — العاشرة صباحًا أم الرابعة عصرًا؟',
				'Maaf, saya tersilap dengar. Hari Khamis — pukul sepuluh pagi atau pukul empat petang?',
			),
		},
		options: [
			{
				text: L(
					'Thursday, ten.',
					'جمعرات، دس بجے۔',
					'الخميس، العاشرة.',
					'Hari Khamis, pukul sepuluh.',
				),
				next: 'booked',
			},
			{
				text: L(
					'Thursday, four.',
					'جمعرات، چار بجے۔',
					'الخميس، الرابعة.',
					'Hari Khamis, pukul empat.',
				),
				next: 'booked',
			},
		],
	},

	switch: {
		id: 'switch',
		line: {
			from: 'wavia',
			text: L(
				'Yes, of course. How can I help?',
				'جی ہاں، میں انگریزی بول سکتا ہوں۔ بتائیے؟',
				'نعم، بالتأكيد. كيف أساعدك؟',
				'Boleh, sudah tentu. Bagaimana saya boleh membantu?',
			),
		},
		options: [
			{
				text: L(
					"I'd like an appointment tomorrow.",
					'مجھے کل کی اپائنٹمنٹ چاہیے۔',
					'أريد موعدًا غدًا.',
					'Saya mahu buat temujanji untuk esok.',
				),
				next: 'slot',
			},
		],
	},

	booked: {
		id: 'booked',
		line: {
			from: 'wavia',
			text: L(
				'Booked. I have sent you a confirmation message. Thank you!',
				'اپائنٹمنٹ بک ہو گئی۔ تصدیقی پیغام بھیج دیا گیا ہے۔ شکریہ!',
				'تم حجز الموعد. أرسلت لك رسالة تأكيد. شكرًا لك!',
				'Tempahan sudah dibuat. Saya sudah menghantar mesej pengesahan. Terima kasih!',
			),
		},
	},
};

/**
 * Chip row. All four are live: the demo is text, and text needs no recording.
 * The honesty labels live on the card, not on the chips.
 */
export const DEMO_LANGS: { code: DemoLang; label: string }[] = [
	{ code: 'ur', label: 'اردو' },
	{ code: 'en', label: 'English' },
	{ code: 'ar', label: 'العربية' },
	{ code: 'ms', label: 'Bahasa Melayu' },
];

/** Languages set right-to-left, and the face each one is set in. */
export const RTL_LANGS: DemoLang[] = ['ur', 'ar'];

export const LANG_CLASS: Record<DemoLang, string> = {
	ur: 'urdu',
	ar: 'arabic',
	en: '',
	ms: '',
};
