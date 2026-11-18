import React, { useEffect, useRef, useState } from "react";
import { harlabApi } from "../services/api";
import type { ExperimentResult } from "../types/harlab";

interface AIAssistantPageProps {
  experiments: ExperimentResult[];
}

interface ChatMessage {
  role: "assistant" | "user";
  text: string;
}

const INITIAL_GREETING: ChatMessage = {
  role: "assistant",
  text: "Hello! I'm the HARLAB Research Assistant. Ask me to interpret your experiment statistics, explain order-book metrics, or help design a market microstructure hypothesis. How can I help you today?",
};

export const AIAssistantPage: React.FC<AIAssistantPageProps> = ({ experiments }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_GREETING]);
  const [input, setInput] = useState("");
  const [selectedExpId, setSelectedExpId] = useState<string>(
    experiments[0]?.experiment_id ?? ""
  );
  const [includeBook, setIncludeBook] = useState(true);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", text: trimmed }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    // Include recent turns so follow-up questions keep conversation context
    const historyText = nextMessages
      .slice(-8)
      .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.text}`)
      .join("\n");

    try {
      const res = await harlabApi.askAi({
        question: historyText,
        experiment_id: selectedExpId || null,
        include_book_context: includeBook,
      });

      const replyText =
        res.ok && res.interpretation
          ? res.interpretation
          : res.error || "Sorry, the assistant is temporarily unavailable. Please try again.";

      setMessages((prev) => [...prev, { role: "assistant", text: replyText }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text:
            err instanceof Error
              ? `Connection error: ${err.message}`
              : "Unable to reach the research assistant right now.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void sendMessage();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div
      className="panel"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 130px)",
        minHeight: 500,
        padding: 0,
        overflow: "hidden",
      }}
    >
      {/* Compact Header + Research Context Controls */}
      <div
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2 className="panel-title">AI Research Assistant</h2>
          <span className="muted" style={{ fontSize: 12 }}>
            Grounded in HARLAB's deterministic calculations
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <select
            value={selectedExpId}
            onChange={(e) => setSelectedExpId(e.target.value)}
            aria-label="Attach experiment context"
          >
            <option value="">No experiment attached</option>
            {experiments.map((exp) => (
              <option key={exp.experiment_id} value={exp.experiment_id}>
                {exp.experiment_id} — {exp.hypothesis.hypothesis_id}
              </option>
            ))}
          </select>

          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={includeBook}
              onChange={(e) => setIncludeBook(e.target.checked)}
            />
            Order-book context
          </label>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setMessages([INITIAL_GREETING])}
            disabled={loading}
          >
            Clear Chat
          </button>
        </div>
      </div>

      {/* Scrollable Conversation Thread */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "18px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={idx}
              style={{
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "78%",
                padding: "10px 14px",
                borderRadius: 8,
                background: isUser ? "var(--accent-blue)" : "var(--bg-elevated)",
                color: isUser ? "#ffffff" : "var(--ink-primary)",
                border: isUser ? "none" : "1px solid var(--border-subtle)",
                whiteSpace: "pre-wrap",
                fontSize: 13.5,
                lineHeight: 1.55,
              }}
            >
              {msg.text}
            </div>
          );
        })}

        {loading ? (
          <div
            style={{
              alignSelf: "flex-start",
              padding: "10px 14px",
              borderRadius: 8,
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-subtle)",
              color: "var(--ink-secondary)",
              fontSize: 13,
            }}
          >
            Thinking...
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {/* Message Input Bar */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border-subtle)",
          display: "flex",
          gap: 10,
          alignItems: "flex-end",
          background: "var(--bg-surface)",
        }}
      >
        <textarea
          rows={2}
          style={{ flex: 1, resize: "none" }}
        placeholder="Ask about your experiment, spread, order-book imbalance, or a new hypothesis..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button className="btn" type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
};