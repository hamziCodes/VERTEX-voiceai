/**
 * React hook for managing sovereign UCVE voice sessions.
 */

import { useState, useCallback, useRef } from 'react';
import { UCVEVoiceClient, UCVEVoiceClientOptions } from '../client';

export interface UseUCVEVoiceReturn {
  isConnected: boolean;
  isSpeaking: boolean;
  transcript: Array<{ speaker: 'user' | 'agent'; text: string }>;
  connect: (token: string, options?: UCVEVoiceClientOptions) => Promise<void>;
  disconnect: () => void;
  sendBargeIn: () => void;
}

export function useUCVEVoice(): UseUCVEVoiceReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState<Array<{ speaker: 'user' | 'agent'; text: string }>>([]);
  const clientRef = useRef<UCVEVoiceClient | null>(null);

  const connect = useCallback(async (token: string, options: UCVEVoiceClientOptions = {}) => {
    const client = new UCVEVoiceClient(token, {
      ...options,
      onTranscript: (speaker, text) => {
        setTranscript((prev) => [...prev, { speaker, text }]);
      },
    });
    clientRef.current = client;
    await client.connect();
    setIsConnected(true);
  }, []);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    setIsConnected(false);
    setIsSpeaking(false);
  }, []);

  const sendBargeIn = useCallback(() => {
    // Cut off agent audio immediately
    setIsSpeaking(false);
  }, []);

  return {
    isConnected,
    isSpeaking,
    transcript,
    connect,
    disconnect,
    sendBargeIn,
  };
}
