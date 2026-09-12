# UCVE Agent Studio — Component Contracts & API Specifications

This document outlines the React component interface contracts, props, emitted events, and backing Phase 26 REST API endpoints.

---

## 1. PersonaEditor Component

- **File**: `agent-studio/src/components/persona/PersonaEditor.tsx`
- **Props**:
  ```typescript
  interface PersonaEditorProps {
    agentId: string;
    initialPersona: {
      system_prompt: string;
      greeting?: string;
      voice_id: string;
      persona_isolation: boolean;
    };
    onAutosave: (patch: Record<string, unknown>) => Promise<boolean>;
    disabled?: boolean;
  }
  ```
- **Events**:
  - `onChange(persona: PersonaConfig)`: Debounced trigger (30s) calling `PATCH /v1/agents/{id}/autosave`.
  - `onVoicePreview(voiceId: string)`: Calls `POST /v1/tts/preview` to synthesize short sample phrase.
- **Backing API**: `GET /v1/agents/{id}`, `PATCH /v1/agents/{id}/autosave`

---

## 2. ProviderChainEditor Component

- **File**: `agent-studio/src/components/providers/ProviderChainEditor.tsx`
- **Props**:
  ```typescript
  interface ProviderChainEditorProps {
    agentId: string;
    providers: {
      stt: CategoryPriorityChain[];
      llm: CategoryPriorityChain[];
      tts: CategoryPriorityChain[];
    };
    onChainUpdated: (category: string, routes: ProviderRoute[]) => void;
  }
  ```
- **Invariants Enforced**:
  - Disables the "Publish" button if any category has `< 2` enabled routes.
  - Re-orders routes via drag-and-drop updating `priority: 1, 2, ...`.
- **Backing API**: `PATCH /v1/agents/{id}/autosave`

---

## 3. LanguageVoicePicker Component

- **File**: `agent-studio/src/components/languages/LanguageVoicePicker.tsx`
- **Props**:
  ```typescript
  interface LanguageVoicePickerProps {
    selectedLanguages: string[];
    voiceId: string;
    onVoiceChange: (voiceId: string) => void;
    onLanguageToggle: (langCode: string, enabled: boolean) => void;
  }
  ```
- **RTL Validation Rule**:
  - If `selectedLanguages.includes('ar')` and `voiceId` does not match `KNOWN_ARABIC_RTL_VOICES`, displays inline alert:
    `"Arabic RTL voice required. Please choose an RTL-capable voice model."`

---

## 4. TestSandboxPanel Component

- **File**: `agent-studio/src/components/sandbox/TestSandboxPanel.tsx`
- **Props**:
  ```typescript
  interface TestSandboxPanelProps {
    agentId: string;
    tenantId: string;
    sandboxAllowanceMinutesRemaining: number;
    onSessionStarted: (sessionId: string) => void;
  }
  ```
- **Events**:
  - `onStartCall`: Initiates mint call to `POST /v1/session/mint?test_call=true`.
  - Automatically pins session configuration to latest published snapshot via `POST /v1/agents/{id}/pin`.
- **Backing API**: `POST /v1/session/mint`, `POST /v1/agents/{id}/pin`, WebSocket `ws://.../ws/audio`
