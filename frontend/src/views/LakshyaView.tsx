import { useEffect, useMemo, useRef, useState } from "react";
import { streamChatQuery, listChatSessions, fetchSessionMessages } from "../lib/api";
import { getUserId } from "../lib/user";
import { Icon } from "../components/Icon";
import { Markdown } from "../components/Markdown";

/* ── Types ────────────────────────────────────────────────────────────── */
type Role = "user" | "assistant";
interface Msg {
  id: string;
  role: Role;
  text: string;
  time: string;
  streaming?: boolean;
  stageIndex?: number;
  specialists?: string[];
  sources?: string[];
}
interface Thread {
  id: string;
  title: string;
  messages: Msg[];
  backendSessionId?: string;
  updatedAt: string;
  loaded?: boolean; // false = a persisted session whose messages aren't fetched yet
}

/* ── Stage stepper ────────────────────────────────────────────────────── */
const STAGES = [
  { key: "routing", label: "Routing" },
  { key: "planning", label: "Planning" },
  { key: "evidence", label: "Gathering Evidence" },
  { key: "specialists", label: "Consulting Specialists" },
  { key: "writing", label: "Writing" },
];

function stageIndexFor(stage: string): number {
  if (stage === "routing") return 0;
  if (stage === "planning") return 1;
  if (stage === "evidence" || stage === "evidence_item") return 2;
  if (stage === "reasoning" || stage === "specialist") return 3;
  if (stage === "synthesizing") return 4;
  return -1;
}

const SPECIALIST_NAMES: Record<string, string> = {
  company_analysis: "Company Analyst",
  news_analysis: "News Analyst",
  compare_companies: "Comparison Analyst",
  document_analysis: "Document Reader",
  thematic_discovery: "Theme Explorer",
  causal_analysis: "Causal Detective",
  portfolio_analysis: "Portfolio Manager",
};

function StageStepper({ stageIndex, specialists }: { stageIndex: number; specialists: string[] }) {
  return (
    <div className="bg-bg-2 border border-outline-variant rounded-md p-sm mb-md">
      <div className="flex flex-wrap items-center gap-x-sm gap-y-xs">
        {STAGES.map((s, i) => {
          const done = i < stageIndex;
          const active = i === stageIndex;
          return (
            <div key={s.key} className="flex items-center gap-xs">
              {active ? (
                <span className="flex items-center gap-xs bg-primary text-on-primary rounded-full px-sm py-[3px] text-caption font-semibold">
                  <Icon name="progress_activity" className="text-[14px] animate-spin" /> {s.label}
                </span>
              ) : (
                <span className={`flex items-center gap-xs text-caption ${done ? "text-on-surface" : "text-on-surface-variant"}`}>
                  <Icon name={done ? "check_circle" : "radio_button_unchecked"} className={`text-[14px] ${done ? "text-primary" : "text-on-surface-variant"}`} />
                  {s.label}
                </span>
              )}
              {i < STAGES.length - 1 && <Icon name="chevron_right" className="text-[14px] text-on-surface-variant" />}
            </div>
          );
        })}
      </div>
      {specialists.length > 0 && (
        <div className="flex flex-wrap items-center gap-xs mt-sm pt-sm border-t border-outline-variant/50">
          <span className="text-label-caps font-label-caps text-on-surface-variant">Active Specialization:</span>
          {specialists.map((sp) => (
            <span key={sp} className="flex items-center gap-xs bg-bg-0 border border-outline-variant rounded px-sm py-[2px] text-caption text-on-surface">
              <Icon name="workspace_premium" className="text-[13px] text-primary" /> {SPECIALIST_NAMES[sp] ?? sp}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Messages ─────────────────────────────────────────────────────────── */
function UserBubble({ msg }: { msg: Msg }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] bg-bg-1 border border-outline-variant rounded-lg px-lg py-md">
        <p className="text-body-md text-on-surface whitespace-pre-wrap">{msg.text}</p>
        <p className="text-caption text-on-surface-variant text-right mt-xs">{msg.time}</p>
      </div>
    </div>
  );
}

function AssistantMessage({ msg }: { msg: Msg }) {
  return (
    <div>
      <div className="flex items-center gap-sm mb-sm">
        <div className="w-7 h-7 rounded bg-bg-2 border border-outline-variant flex items-center justify-center">
          <Icon name="bolt" className="text-[16px] text-primary" />
        </div>
        <span className="text-body-md font-semibold text-on-surface">Lakshya</span>
      </div>
      {(msg.streaming || (msg.stageIndex ?? -1) >= 0) && msg.stageIndex !== undefined && msg.stageIndex < 4 && (
        <StageStepper stageIndex={msg.stageIndex} specialists={msg.specialists ?? []} />
      )}
      <div className="text-body-md">
        <Markdown>{msg.text}</Markdown>
        {msg.streaming && msg.text && <span className="inline-block w-[2px] h-4 bg-primary align-middle animate-blink ml-[2px]" />}
        {msg.streaming && !msg.text && (msg.stageIndex ?? 0) < 4 && (
          <span className="text-body-sm text-on-surface-variant">Thinking…</span>
        )}
      </div>
      {msg.sources && msg.sources.length > 0 && (
        <div className="flex flex-wrap gap-xs mt-sm">
          <span className="text-label-caps font-label-caps text-on-surface-variant self-center">Sources:</span>
          {msg.sources.map((s, i) => (
            <span key={i} className="text-caption text-on-surface-variant bg-bg-2 border border-outline-variant rounded-full px-sm py-[2px]">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── View ─────────────────────────────────────────────────────────────── */
const now = () => new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

function newThread(): Thread {
  return { id: uid(), title: "New research thread", messages: [], updatedAt: new Date().toISOString() };
}

export function LakshyaView() {
  const userId = useMemo(() => getUserId(), []);
  const [threads, setThreads] = useState<Thread[]>(() => [newThread()]);
  const [activeId, setActiveId] = useState<string>(() => threads[0].id);
  const [composer, setComposer] = useState("");
  const [expertise, setExpertise] = useState<"beginner" | "advanced">("advanced");
  const [streaming, setStreaming] = useState(false);
  const [threadSearch, setThreadSearch] = useState("");
  const [threadsOpen, setThreadsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = threads.find((t) => t.id === activeId) ?? threads[0];

  // Restore past conversations from the backend on mount (kept below the fresh
  // "New research thread" so a refresh no longer wipes history).
  useEffect(() => {
    let cancelled = false;
    listChatSessions(userId)
      .then((sessions) => {
        if (cancelled || sessions.length === 0) return;
        setThreads((cur) => [
          ...cur,
          ...sessions.map((s) => ({
            id: `sess-${s.id}`,
            title: s.title || "Past conversation",
            messages: [] as Msg[],
            backendSessionId: s.id,
            updatedAt: s.last_message_at || s.created_at,
            loaded: false,
          })),
        ]);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function openThread(id: string) {
    setActiveId(id);
    setThreadsOpen(false);
    const t = threads.find((x) => x.id === id);
    if (!t || t.loaded || !t.backendSessionId) return;
    patchThread(id, (x) => ({ ...x, loaded: true })); // optimistic to avoid double-fetch
    try {
      const msgs = await fetchSessionMessages(t.backendSessionId, userId);
      patchThread(id, (x) => ({
        ...x,
        messages: msgs.map((m) => ({
          id: m.id,
          role: m.role,
          text: m.content,
          time: m.created_at ? new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "",
        })),
      }));
    } catch {
      /* leave empty on failure */
    }
  }

  const patchThread = (id: string, fn: (t: Thread) => Thread) =>
    setThreads((cur) => cur.map((t) => (t.id === id ? fn(t) : t)));

  const patchMsg = (threadId: string, msgId: string, patch: Partial<Msg> | ((m: Msg) => Msg)) =>
    patchThread(threadId, (t) => ({
      ...t,
      updatedAt: new Date().toISOString(),
      messages: t.messages.map((m) => (m.id === msgId ? (typeof patch === "function" ? patch(m) : { ...m, ...patch }) : m)),
    }));

  const scrollToBottom = () => requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }));

  async function send() {
    const text = composer.trim();
    if (!text || streaming || !active) return;
    const threadId = active.id;
    const userMsg: Msg = { id: uid(), role: "user", text, time: now() };
    const asstId = uid();
    const asstMsg: Msg = { id: asstId, role: "assistant", text: "", time: now(), streaming: true, stageIndex: 0, specialists: [] };

    setComposer("");
    setStreaming(true);
    patchThread(threadId, (t) => ({
      ...t,
      title: t.messages.length === 0 ? text.slice(0, 46) : t.title,
      messages: [...t.messages, userMsg, asstMsg],
    }));
    scrollToBottom();

    let acc = "";
    try {
      await streamChatQuery(
        { user_id: userId, query: text, expertise_level: expertise, session_id: active.backendSessionId },
        {
          onStage: (stage, _detail) => {
            const idx = stageIndexFor(stage);
            if (idx >= 0) patchMsg(threadId, asstId, (m) => ({ ...m, stageIndex: Math.max(m.stageIndex ?? 0, idx) }));
            if (stage === "specialist") patchMsg(threadId, asstId, (m) => ({ ...m, specialists: [...new Set([...(m.specialists ?? []), _detail])] }));
          },
          onToken: (tok) => {
            acc += tok;
            patchMsg(threadId, asstId, (m) => ({ ...m, text: acc, stageIndex: 4 }));
            scrollToBottom();
          },
          onDone: (data) => {
            // Humanised source labels so beginners see where the answer came from.
            const SOURCE_LABEL: Record<string, string> = {
              company: "Company financials",
              news: "Recent news",
              filings: "Filings & concalls",
              portfolio: "Your portfolio",
              thematic: "Theme search",
              causal: "Causal analysis",
              causal_snapshot: "Causal analysis",
              web: "Web search",
              specialist: "Specialist analysis",
            };
            const sources = Array.from(new Set(
              (data.sources ?? [])
                .map((s) => String((s as Record<string, unknown>).kind ?? (s as Record<string, unknown>).name ?? ""))
                .filter(Boolean)
                .map((k) => SOURCE_LABEL[k] ?? k)
            ));
            patchMsg(threadId, asstId, (m) => ({ ...m, streaming: false, sources }));
            if (data.session_id) patchThread(threadId, (t) => ({ ...t, backendSessionId: data.session_id }));
          },
          onError: (d) => patchMsg(threadId, asstId, (m) => ({ ...m, streaming: false, text: `⚠️ ${d}` })),
        }
      );
    } catch (e) {
      patchMsg(threadId, asstId, (m) => ({ ...m, streaming: false, text: `⚠️ ${e instanceof Error ? e.message : "Request failed"}` }));
    } finally {
      setStreaming(false);
      scrollToBottom();
    }
  }

  const filteredThreads = threads.filter((t) => t.title.toLowerCase().includes(threadSearch.toLowerCase()));

  const ThreadPanel = (
    <div className="flex flex-col h-full bg-bg-1 border border-outline-variant rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-md py-md border-b border-outline-variant">
        <h3 className="text-section-header text-on-surface">Lakshya Threads</h3>
        <button
          onClick={() => {
            const t = newThread();
            setThreads((cur) => [t, ...cur]);
            setActiveId(t.id);
            setThreadsOpen(false);
          }}
          className="w-8 h-8 rounded bg-primary text-on-primary flex items-center justify-center hover:opacity-90"
          title="New thread"
        >
          <Icon name="edit_square" className="text-[18px]" />
        </button>
      </div>
      <div className="p-sm">
        <div className="flex items-center bg-bg-0 border border-outline-variant rounded px-sm py-xs">
          <Icon name="search" className="text-on-surface-variant text-[18px] mr-xs" />
          <input value={threadSearch} onChange={(e) => setThreadSearch(e.target.value)} placeholder="Search threads…" className="bg-transparent text-body-sm text-on-surface focus:outline-none w-full placeholder:text-on-surface-variant" />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-sm pb-sm space-y-xs">
        {filteredThreads.map((t) => (
          <button
            key={t.id}
            onClick={() => openThread(t.id)}
            className={`w-full text-left rounded p-sm border transition-colors ${
              active?.id === t.id ? "bg-bg-2 border-primary/40" : "bg-transparent border-transparent hover:bg-bg-2"
            }`}
          >
            <p className="text-body-sm text-on-surface font-medium line-clamp-2">{t.title}</p>
            <p className="text-caption text-on-surface-variant mt-xs flex items-center gap-xs">
              {t.id === active?.id && streaming ? <><span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" /> Active</> : `${t.messages.length} messages`}
            </p>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="flex gap-lg h-[calc(100vh-9.5rem)]">
      {/* Threads (desktop) */}
      <div className="hidden lg:block w-72 shrink-0">{ThreadPanel}</div>

      {/* Threads drawer (mobile) */}
      {threadsOpen && (
        <div className="lg:hidden fixed inset-0 z-[60]">
          <div className="absolute inset-0 bg-black/50" onClick={() => setThreadsOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-72 p-md">{ThreadPanel}</div>
        </div>
      )}

      {/* Conversation */}
      <div className="flex-1 flex flex-col bg-bg-1 border border-outline-variant rounded-lg overflow-hidden min-w-0">
        <div className="flex items-center justify-between px-lg py-md border-b border-outline-variant">
          <div className="flex items-center gap-sm min-w-0">
            <button onClick={() => setThreadsOpen(true)} className="lg:hidden text-on-surface-variant"><Icon name="menu" className="text-[22px]" /></button>
            <Icon name="bolt" className="text-primary text-[20px] shrink-0" />
            <h3 className="text-section-header text-on-surface truncate">{active?.title ?? "Lakshya"}</h3>
          </div>
          <button className="flex items-center gap-xs text-on-surface-variant hover:text-on-surface text-body-sm">
            <Icon name="download" className="text-[18px]" /> <span className="hidden sm:inline">Export</span>
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-lg py-lg space-y-lg">
          {active && active.messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-lg bg-bg-2 border border-outline-variant flex items-center justify-center mb-md">
                <Icon name="bolt" className="text-[24px] text-primary" />
              </div>
              <h4 className="text-section-header text-on-surface">Ask Lakshya anything about Indian equities</h4>
              <p className="text-body-md text-on-surface-variant mt-xs max-w-md">Company deep-dives, comparisons, portfolio exposure, or hidden causal impacts — grounded and streamed.</p>
              <div className="flex flex-wrap gap-sm justify-center mt-lg max-w-lg">
                {["Compare TCS and Infosys — which is the better investment?", "Hidden second-order effects of a crude oil spike?", "How exposed is my portfolio to rising oil?"].map((p) => (
                  <button key={p} onClick={() => setComposer(p)} className="text-body-sm text-on-surface-variant bg-bg-2 border border-outline-variant rounded-full px-md py-sm hover:text-on-surface hover:border-primary/40">{p}</button>
                ))}
              </div>
            </div>
          ) : (
            active?.messages.map((m) => (m.role === "user" ? <UserBubble key={m.id} msg={m} /> : <AssistantMessage key={m.id} msg={m} />))
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-outline-variant p-md">
          <div className="bg-bg-0 border border-outline-variant rounded-lg focus-within:border-primary/50 transition-colors">
            <textarea
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={2}
              placeholder="Ask Lakshya to dive deeper, compare vendors, or cite sources…"
              className="w-full bg-transparent text-body-md text-on-surface px-md pt-md resize-none focus:outline-none placeholder:text-on-surface-variant"
            />
            <div className="flex items-center justify-between px-md pb-md pt-xs">
              <div className="flex items-center gap-sm">
                <button className="text-on-surface-variant hover:text-on-surface" title="Attach"><Icon name="attach_file" className="text-[20px]" /></button>
                <div className="flex items-center bg-bg-2 border border-outline-variant rounded-full p-[2px] text-caption">
                  <button onClick={() => setExpertise("beginner")} className={`px-sm py-[3px] rounded-full ${expertise === "beginner" ? "bg-bg-1 text-on-surface" : "text-on-surface-variant"}`}>Summary</button>
                  <button onClick={() => setExpertise("advanced")} className={`px-sm py-[3px] rounded-full flex items-center gap-xs ${expertise === "advanced" ? "bg-bg-1 text-primary" : "text-on-surface-variant"}`}><Icon name="expand_less" className="text-[14px]" /> Advanced</button>
                </div>
              </div>
              <button onClick={() => void send()} disabled={streaming || !composer.trim()} className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center hover:opacity-90 disabled:opacity-40">
                <Icon name={streaming ? "progress_activity" : "arrow_upward"} className={`text-[20px] ${streaming ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
          <p className="text-caption text-on-surface-variant text-center mt-sm">Lakshya can make mistakes. Verify critical financial data against source citations.</p>
        </div>
      </div>
    </div>
  );
}
