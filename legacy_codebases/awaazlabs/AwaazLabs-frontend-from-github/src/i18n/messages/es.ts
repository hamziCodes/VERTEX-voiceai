/**
 * Spanish message catalogue — spec §2.7's "second locale target".
 *
 * Typed as `Messages`, i.e. `Readonly<Record<MessageKey, string>>`. If `en.ts` gains a key
 * that is missing here, `tsc` fails. There is no silent English fallback — an untranslated
 * string cannot reach a Spanish-speaking user by accident.
 *
 * Terminology notes, so a future translator does not "correct" these:
 *   - "VOB" (verification of benefits) is kept as-is: US clinic staff use the English
 *     acronym in Spanish-language workflows, and it names a product surface.
 *   - "Qualicall" is a product name and is never translated.
 *   - "PHI-BAA" / "NON-PHI" are regulatory terms of art (HIPAA) and stay in English.
 */

import type { Messages } from './en';

export const es: Messages = {
  // --- Navigation groups (§3) ---
  'nav.group.home': 'INICIO',
  'nav.group.operations': 'OPERACIONES',
  'nav.group.agents': 'AGENTES',
  'nav.group.quality': 'CALIDAD',
  'nav.group.growth': 'CRECIMIENTO',
  'nav.group.insights': 'ANÁLISIS',
  'nav.group.compliance': 'CUMPLIMIENTO',
  'nav.group.settings': 'AJUSTES',

  // --- Navigation items (§3) ---
  'nav.overview': 'Resumen',
  'nav.appointments': 'Citas',
  'nav.conversations': 'Conversaciones',
  'nav.calls': 'Llamadas',
  'nav.chats': 'Chats',
  'nav.escalations': 'Escalamientos',
  'nav.vobQueue': 'Cola de VOB',
  'nav.receptionist': 'Recepcionista',
  'nav.vobAgent': 'Agente de VOB',
  'nav.chatAgents': 'Agentes de chat',
  'nav.reviewTaker': 'Solicitud de reseñas',
  'nav.reengagement': 'Reactivación',
  'nav.quality': 'Calidad y optimización',
  'nav.knowledge': 'Conocimiento del agente',
  'nav.reviews': 'Reseñas',
  'nav.campaigns': 'Campañas',
  'nav.reports': 'Informes y exportaciones',
  'nav.auditLog': 'Registro de auditoría',
  'nav.members': 'Miembros',
  'nav.billing': 'Uso y facturación',
  'nav.organization': 'Organización y sedes',
  'nav.lines': 'Líneas y números',
  'nav.consent': 'Consentimiento y no llamar',
  'nav.notifications': 'Notificaciones',

  // --- Shell chrome ---
  'shell.skipToContent': 'Saltar al contenido principal',
  'shell.mainNavigation': 'Navegación principal',
  'shell.expandNavigation': 'Expandir navegación',
  'shell.collapseNavigation': 'Contraer navegación',

  // --- Top bar (§3) ---
  'topbar.organization': 'Organización',
  'topbar.changeOrganization': 'Cambiar de organización',
  'topbar.allLocations': 'Todas las sedes',
  'topbar.changeLocation': 'Cambiar de sede',
  'topbar.locationFilter': 'Filtro de sede',
  'topbar.notifications': 'Notificaciones',
  'topbar.unread': 'sin leer',
  'topbar.notificationsNone': 'Notificaciones: ninguna sin leer',
  'topbar.notificationsEscalations': 'Escalaciones por reconocer o resolver',
  'topbar.notificationsVobCalls': 'Llamadas pendientes a aseguradoras',
  'topbar.userMenu': 'Menú de usuario',
  'topbar.signOut': 'Cerrar sesión',
  'topbar.devOnly': 'Solo en compilaciones de desarrollo — ausente en producción',
  'topbar.signedInAs': 'Sesión iniciada como',
  'topbar.demoControls': 'Controles de demostración',
  'topbar.demoControlsNote':
    'No es una función del producto. En una implementación real, el rol y el modo llegan con la sesión; el modo lo configuran los administradores de Awaaz por organización y nunca es autoservicio (§2.1).',
  'topbar.role': 'Rol',
  'topbar.dataMode': 'Modo de datos',
  'topbar.interfaceLanguage': 'Idioma de la interfaz',
  'topbar.interfaceLanguageNote':
    'El marco de i18n está implementado según §2.7. La estructura de la aplicación está traducida; el contenido de las páginas se entrega en inglés, con el español como segundo idioma objetivo.',
  'topbar.modePhiTitle': 'Modo PHI-BAA: detalle completo a nivel de paciente. Requiere un BAA firmado.',
  'topbar.modeNonPhiTitle':
    'Modo NON-PHI: solo agregados y analíticas. Sin identidad del paciente, grabaciones ni transcripciones.',

  // --- Under construction placeholder ---
  'underConstruction.badge': 'En construcción',
  'underConstruction.spec': 'Especificación:',
  'underConstruction.plannedFor': 'Previsto para:',
  'underConstruction.milestone2': 'Etapa 2',

  // --- Route guard (§2.2) ---
  'guard.notAvailable': 'no está disponible',
  'guard.explanation':
    'Su rol y el modo de datos actual del espacio de trabajo no otorgan acceso a esta superficie. Si cree que esto es un error, comuníquese con el propietario de su organización.',
};
