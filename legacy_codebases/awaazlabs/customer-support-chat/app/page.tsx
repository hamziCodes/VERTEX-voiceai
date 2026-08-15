"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const starterMessages: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "Hi, I'm Layla from AwaazLabs support. I can help with calls, links, forms, confirmations, privacy, or technical issues."
  }
];

const quickTopics = [
  "I missed an AI call",
  "My link is not opening",
  "I need appointment support",
  "I have a privacy question"
];

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>(starterMessages);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const canSend = useMemo(
    () => input.trim().length > 0 && !isSending,
    [input, isSending]
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSending]);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = input.trim();
    if (!trimmed || isSending) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed
    };
    const nextMessages = [...messages, userMessage];

    setMessages(nextMessages);
    setInput("");
    setError("");
    setIsSending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          messages: nextMessages.map(({ role, content }) => ({ role, content }))
        })
      });

      const data = (await response.json()) as {
        reply?: string;
        error?: string;
      };

      if (!response.ok || !data.reply) {
        throw new Error(data.error || "The assistant could not respond.");
      }

      const reply = data.reply;
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply
        }
      ]);
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Something went wrong while sending the message.";
      setError(message);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  function resetChat() {
    setMessages(starterMessages);
    setInput("");
    setError("");
    inputRef.current?.focus();
  }

  function selectQuickTopic(topic: string) {
    setInput(topic);
    inputRef.current?.focus();
  }

  return (
    <main className="page-shell">
      <header className="top-bar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            A
          </div>
          <div>
            <p>AwaazLabs</p>
            <span>Patient Support</span>
          </div>
        </div>
        <div className="top-status">
          <span className="status-dot" aria-hidden="true" />
          Support assistant online
        </div>
      </header>

      <section className="support-layout" aria-label="AwaazLabs support">
        <section className="chat-panel" aria-label="Customer support chat">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Live support assistant</p>
              <h2>Chat with Layla</h2>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={resetChat}
            >
              New chat
            </button>
          </header>

          <div className="mobile-topics" aria-label="Common support topics">
            {quickTopics.map((topic) => (
              <button
                key={topic}
                type="button"
                onClick={() => selectQuickTopic(topic)}
              >
                {topic}
              </button>
            ))}
          </div>

          <div className="message-list" aria-live="polite">
            {messages.map((message) => (
              <article
                className={`message-bubble ${message.role}`}
                key={message.id}
              >
                <span>{message.role === "assistant" ? "Layla" : "You"}</span>
                <p>{message.content}</p>
              </article>
            ))}

            {isSending ? (
              <article className="message-bubble assistant pending">
                <span>Layla</span>
                <p>Typing...</p>
              </article>
            ) : null}

            <div ref={messagesEndRef} />
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          <form className="composer" onSubmit={sendMessage}>
            <textarea
              ref={inputRef}
              aria-label="Message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Type your support question..."
              rows={2}
            />
            <button type="submit" disabled={!canSend}>
              {isSending ? "Sending" : "Send"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}
