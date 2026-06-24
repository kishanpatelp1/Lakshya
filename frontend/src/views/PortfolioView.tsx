import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import {
  addHolding,
  deleteHolding,
  fetchPortfolioMetrics,
  fetchPortfolios,
  streamChatQuery,
  type AICompany,
  type AIHoldingDetail,
  type PortfolioMetrics,
} from "../lib/api";
import { formatINR, formatPct } from "../lib/format";
import { getUserId } from "../lib/user";
import { Icon } from "../components/Icon";
import { Markdown } from "../components/Markdown";
import { CompanySearch } from "../components/CompanySearch";
import { Card, CardHeader, Chip, GhostButton, PrimaryButton, Skeleton, StatTile } from "../components/ui";

const DONUT_COLORS = ["#00E5FF", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#64748B", "#06B6D4"];

function sharpeBadge(s: number): { label: string; tone: "positive" | "warning" | "negative" } {
  if (s >= 2) return { label: "Strong", tone: "positive" };
  if (s >= 1) return { label: "Moderate", tone: "warning" };
  return { label: "Weak", tone: "negative" };
}

/* ── Portfolio-scoped Lakshya chat ────────────────────────────────────── */
interface ChatMsg { id: string; role: "user" | "assistant"; text: string; streaming?: boolean }
const mid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

function PortfolioChat({ userId }: { userId: string }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [composer, setComposer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const scroll = () => requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }));

  const send = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return;
    const userMsg: ChatMsg = { id: mid(), role: "user", text };
    const aId = mid();
    setComposer("");
    setStreaming(true);
    setMessages((m) => [...m, userMsg, { id: aId, role: "assistant", text: "", streaming: true }]);
    scroll();
    let acc = "";
    try {
      await streamChatQuery(
        { user_id: userId, query: `[Portfolio question] ${text}`, expertise_level: "advanced" },
        {
          onToken: (t) => {
            acc += t;
            setMessages((m) => m.map((x) => (x.id === aId ? { ...x, text: acc } : x)));
            scroll();
          },
          onError: (d) => setMessages((m) => m.map((x) => (x.id === aId ? { ...x, streaming: false, text: `⚠️ ${d}` } : x))),
        }
      );
    } catch {
      /* ignore */
    } finally {
      setMessages((m) => m.map((x) => (x.id === aId ? { ...x, streaming: false } : x)));
      setStreaming(false);
      scroll();
    }
  }, [userId, streaming]);

  return (
    <Card className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-sm px-md py-md border-b border-outline-variant">
        <Icon name="auto_awesome" className="text-primary text-[18px]" />
        <h3 className="text-card-title font-card-title text-on-surface">Lakshya AI Assistant</h3>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-md py-md space-y-md min-h-[240px]">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center py-lg">
            <Icon name="insights" className="text-[28px] text-on-surface-variant mb-sm" />
            <p className="text-body-sm text-on-surface-variant max-w-[240px]">Analyze portfolio drift, suggest rebalancing trades, or query sector exposure.</p>
          </div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex justify-end">
                <div className="max-w-[90%] bg-bg-2 border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface">{m.text}</div>
              </div>
            ) : (
              <div key={m.id} className="bg-bg-0 border border-outline-variant rounded-lg px-md py-sm text-body-sm">
                <Markdown>{m.text}</Markdown>
                {m.streaming && <span className="inline-block w-[2px] h-3 bg-primary align-middle animate-blink ml-[2px]" />}
                {m.streaming && !m.text && <span className="text-on-surface-variant">Analysing…</span>}
              </div>
            )
          )
        )}
      </div>
      <div className="p-md border-t border-outline-variant">
        <div className="flex gap-xs flex-wrap mb-sm">
          {["Optimize Sharpe Ratio", "Reduce Tech Exposure", "Am I overexposed to oil?"].map((c) => (
            <button key={c} onClick={() => void send(c)} disabled={streaming} className="text-caption text-on-surface-variant bg-bg-2 border border-outline-variant rounded-full px-sm py-[3px] hover:text-on-surface disabled:opacity-50">{c}</button>
          ))}
        </div>
        <div className="flex items-center bg-bg-0 border border-outline-variant rounded-lg px-md py-xs focus-within:border-primary/50">
          <input
            value={composer}
            onChange={(e) => setComposer(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), void send(composer))}
            placeholder="Ask Lakshya about your portfolio…"
            className="flex-1 bg-transparent text-body-sm text-on-surface focus:outline-none placeholder:text-on-surface-variant"
          />
          <button onClick={() => void send(composer)} disabled={streaming || !composer.trim()} className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center disabled:opacity-40">
            <Icon name={streaming ? "progress_activity" : "arrow_upward"} className={`text-[18px] ${streaming ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>
    </Card>
  );
}

/* ── View ─────────────────────────────────────────────────────────────── */
export function PortfolioView() {
  const userId = useMemo(() => getUserId(), []);
  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [portfolioName, setPortfolioName] = useState("Portfolio");
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [addCompany, setAddCompany] = useState<AICompany | null>(null);
  const [addQty, setAddQty] = useState("");
  const [mutating, setMutating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchPortfolios(userId);
      if (list.length === 0) {
        setMetrics(null);
        return;
      }
      const primary = list.find((p) => p.is_primary) ?? list[0];
      setPortfolioId(primary.id);
      setPortfolioName(primary.name);
      setMetrics(await fetchPortfolioMetrics(primary.id));
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const holdings: AIHoldingDetail[] = metrics?.holdings ?? [];
  const ret = useMemo(() => {
    const tw = holdings.reduce((a, h) => a + (h.weight ?? 0), 0) || 1;
    return holdings.reduce((a, h) => a + (h.weight ?? 0) * (h.return_pct ?? 0), 0) / tw;
  }, [holdings]);

  const sectorData = useMemo(
    () => Object.entries(metrics?.sector_allocation ?? {}).map(([name, w]) => ({ name, value: Math.round(w * 100) / 100 })).sort((a, b) => b.value - a.value),
    [metrics]
  );

  const onAdd = async () => {
    if (!portfolioId || !addCompany) return;
    const qty = Number(addQty);
    if (!qty || qty <= 0) return;
    setMutating(true);
    try {
      await addHolding(portfolioId, addCompany.id, qty);
      setAddCompany(null);
      setAddQty("");
      await load();
    } finally {
      setMutating(false);
    }
  };

  const onRemove = async (holdingId: string) => {
    if (!portfolioId) return;
    setMutating(true);
    try {
      await deleteHolding(portfolioId, holdingId);
      await load();
    } finally {
      setMutating(false);
    }
  };

  const sharpe = metrics?.sharpe_ratio ?? 0;
  const badge = sharpeBadge(sharpe);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg items-start">
      {/* Main */}
      <div className="lg:col-span-8 space-y-lg">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-md">
          <div>
            <h2 className="text-headline-lg-mobile md:text-headline-lg text-on-surface">{portfolioName}</h2>
            <p className="text-body-sm text-on-surface-variant mt-xs flex items-center gap-xs">
              <Icon name="schedule" className="text-[15px]" /> Last synced: {new Date().toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
            </p>
          </div>
          <div className="flex gap-sm shrink-0">
            <GhostButton>Export Report</GhostButton>
            <PrimaryButton>+ New Strategy</PrimaryButton>
          </div>
        </div>

        {/* Stat tiles */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[132px]" />)
          ) : (
            <>
              <StatTile accent label="Total Value" value={formatINR(metrics?.total_value_inr ?? 0)} sub={<span className="flex items-center gap-xs"><Icon name="trending_up" className="text-[15px] text-positive" /><span className="text-positive">{formatPct(ret)}</span> return</span>} />
              <StatTile label="Portfolio Return" value={formatPct(ret)} valueClass={ret >= 0 ? "text-positive" : "text-negative"} sub={`across ${metrics?.holdings_count ?? 0} holdings`} />
              <StatTile
                label="Risk Score (Sharpe)"
                value={sharpe.toFixed(2)}
                sub={
                  <div className="space-y-xs">
                    <Chip tone={badge.tone}>{badge.label}</Chip>
                    <div className="h-1.5 rounded-full bg-gradient-to-r from-positive via-warning to-negative relative">
                      <div className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-on-surface border border-bg-1" style={{ left: `${Math.min(Math.max((sharpe / 3) * 100, 4), 96)}%` }} />
                    </div>
                  </div>
                }
              />
            </>
          )}
        </div>

        {/* Sector + holdings */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-lg">
          {/* Sector allocation */}
          <Card>
            <CardHeader title="Sector Allocation" />
            <div className="px-lg pb-lg">
              {loading ? (
                <Skeleton className="h-48" />
              ) : sectorData.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant py-lg text-center">No sector data yet.</p>
              ) : (
                <>
                  <div className="relative w-44 h-44 mx-auto">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={sectorData} dataKey="value" innerRadius={58} outerRadius={80} paddingAngle={2} stroke="none">
                          {sectorData.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />)}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-[26px] font-semibold text-on-surface tabular">{sectorData.length}</span>
                      <span className="text-caption text-on-surface-variant">Sectors</span>
                    </div>
                  </div>
                  <div className="mt-lg space-y-sm">
                    {sectorData.slice(0, 5).map((s, i) => (
                      <div key={s.name} className="flex items-center justify-between text-body-sm">
                        <span className="flex items-center gap-sm text-on-surface"><span className="w-2 h-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />{s.name}</span>
                        <span className="text-on-surface-variant tabular">{s.value}%</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </Card>

          {/* Top holdings */}
          <Card>
            <CardHeader title="Top Holdings" />
            <div className="px-lg pb-lg">
              {/* Add holding */}
              <div className="flex gap-sm items-center mb-md">
                <CompanySearch placeholder="Add a company…" onSelect={setAddCompany} className="flex-1" />
                <input type="number" min="0" value={addQty} onChange={(e) => setAddQty(e.target.value)} placeholder="Qty" className="w-20 bg-bg-0 border border-outline-variant rounded px-sm py-sm text-body-sm text-on-surface focus:outline-none focus:border-primary/50" />
                <PrimaryButton onClick={() => void onAdd()} disabled={mutating || !addCompany || !addQty}>Add</PrimaryButton>
              </div>
              {addCompany && <p className="text-caption text-on-surface-variant mb-sm">Selected: {addCompany.name}</p>}

              {loading ? (
                <Skeleton className="h-48" />
              ) : holdings.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant py-md text-center">No holdings yet — add one above.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-body-sm">
                    <thead>
                      <tr className="text-label-caps font-label-caps text-on-surface-variant border-b border-outline-variant">
                        <th className="text-left py-sm">Symbol</th>
                        <th className="text-right py-sm">Weight</th>
                        <th className="text-right py-sm">Shares</th>
                        <th className="text-right py-sm">Avg Price</th>
                        <th className="py-sm" />
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((h) => (
                        <tr key={h.id} className="border-b border-outline-variant/40 group">
                          <td className="py-md">
                            <span className="text-on-surface font-medium">{h.ticker_nse ?? h.company_name ?? "—"}</span>
                            {h.ticker_nse && <span className="ml-xs text-caption text-on-surface-variant border border-outline-variant rounded-sm px-1">NSE</span>}
                          </td>
                          <td className="text-right tabular text-on-surface">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                          <td className="text-right tabular text-on-surface">{h.quantity?.toLocaleString("en-IN")}</td>
                          <td className="text-right tabular text-on-surface">{formatINR(h.average_price ?? 0)}</td>
                          <td className="text-right">
                            <button onClick={() => void onRemove(h.id)} disabled={mutating} className="text-on-surface-variant hover:text-negative opacity-0 group-hover:opacity-100 transition-opacity" title="Remove">
                              <Icon name="close" className="text-[16px]" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Right rail: portfolio chat */}
      <div className="lg:col-span-4 lg:sticky lg:top-[calc(4rem+24px)] h-[560px]">
        <PortfolioChat userId={userId} />
      </div>
    </div>
  );
}
