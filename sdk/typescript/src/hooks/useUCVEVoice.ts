/** React lifecycle wrapper for the Wavia raw-WebSocket client. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { UCVEVoiceClient, UCVEVoiceClientOptions } from '../client.js';

export interface UseUCVEVoiceReturn {
  isConnected: boolean;
  isSpeaking: boolean;
  transcript: Array<{ speaker: 'user' | 'agent'; text: string }>;
  remoteClose: Record<string, unknown> | null;
  connect: (token: string, options?: UCVEVoiceClientOptions) => Promise<void>;
  disconnect: () => void;
  sendAudioChunk: (pcmBytes: ArrayBuffer | Uint8Array) => void;
  sendTextTurn: (text: string) => void;
  sendBargeIn: () => void;
  cancelPlayback: () => void;
}

export function useUCVEVoice(): UseUCVEVoiceReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [remoteClose, setRemoteClose] = useState<Record<string, unknown> | null>(null);
  const [transcript, setTranscript] = useState<Array<{ speaker: 'user' | 'agent'; text: string }>>([]);
  const clientRef = useRef<UCVEVoiceClient | null>(null);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    clientRef.current = null;
    setIsConnected(false);
    setIsSpeaking(false);
  }, []);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  const connect = useCallback(async (token: string, options: UCVEVoiceClientOptions = {}) => {
    clientRef.current?.disconnect();
    setRemoteClose(null);
    const client = new UCVEVoiceClient(token, {
      ...options,
      onTranscript: (speaker, text) => {
        setTranscript((prev) => [...prev, { speaker, text }]);
        options.onTranscript?.(speaker, text);
      },
      onAudioStart: (event) => {
        setIsSpeaking(true);
        options.onAudioStart?.(event);
      },
      onClearAudio: async (event) => {
        setIsSpeaking(false);
        return await options.onClearAudio?.(event);
      },
      onPlayedTextCommit: (event) => {
        if (event.complete) setIsSpeaking(false);
        options.onPlayedTextCommit?.(event);
      },
      onClose: (event) => {
        setRemoteClose(event);
        setIsConnected(false);
        setIsSpeaking(false);
        options.onClose?.(event);
      },
    });
    clientRef.current = client;
    await client.connect();
    setIsConnected(true);
  }, []);

  const sendAudioChunk = useCallback((pcmBytes: ArrayBuffer | Uint8Array) => {
    clientRef.current?.sendAudioChunk(pcmBytes);
  }, []);

  const sendTextTurn = useCallback((text: string) => {
    clientRef.current?.sendTextTurn(text);
  }, []);

  const cancelPlayback = useCallback(() => {
    clientRef.current?.cancelPlayback();
    setIsSpeaking(false);
  }, []);

  const sendBargeIn = useCallback(() => {
    cancelPlayback();
    clientRef.current?.sendBargeIn();
  }, [cancelPlayback]);

  return {
    isConnected,
    isSpeaking,
    transcript,
    remoteClose,
    connect,
    disconnect,
    sendAudioChunk,
    sendTextTurn,
    sendBargeIn,
    cancelPlayback,
  };
}
