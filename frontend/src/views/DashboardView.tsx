import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import {
  aiGet,
  fetchMarketHeadlines,
  fetchPortfolioMetrics,
  fetchPortfolios,
  fetchTimeline,
  streamPortfolioSuggestions,
  type NewsDataArticle,
  type PortfolioMetrics,
  type TimelineEvent,
} from "../lib/api";
import { getUserId } from "../lib/user";
import { formatINR, formatPct, timeAgo } from "../lib/format";
import type { ViewKey } from "../routes";
import { Icon } from "../components/Icon";
import { Markdown } from "../components/Markdown";
import { Card, CardHeader, GhostButton, PrimaryButton, Skeleton, StatTile } from "../components/ui";

const DONUT_COLORS = ["#00E5FF", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#64748B"];

export function DashboardView({ onNavigate }: { onNavigate: (v: ViewKey) => void }) {
  const userId = useMemo(() => getUserId(), []);
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [simBalance, setSimBalance] = useState<number | null>(null);
  const [headlines, setHeadlines] = useState<NewsDataArticle[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState("");
  const [insightsLoading, setInsightsLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [portfolios, headlinesRes, timelineRes, simRes] = await Promise.allSettled([
        fetchPortfolios(userId),
        fetchMarketHeadlines(6),
        fetchTimeline(userId, undefined, 8),
        aiGet<{ balance?: number }>(`/simulator/stats?user_id=${userId}`),
      ]);
      if (!alive) return;

      if (portfolios.status === "fulfilled" && portfolios.value.length > 0) {
        const primary = portfolios.value.find((p) => p.is_primary) ?? portfolios.value[0];
        try {
          const m = await fetchPortfolioMetrics(primary.id);
          if (alive) setMetrics(m);
        } catch { /* ignore */ }
      }
      if (headlinesRes.status === "fulfilled") setHeadlines(headlinesRes.value.results ?? []);
      if (timelineRes.status === "fulfilled") setTimeline(timelineRes.value);
      if (simRes.status === "fulfilled") setSimBalance(simRes.value.balance ?? null);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [userId]);

  // Stream AI market insights
  useEffect(() => {
    let acc = "";
    setInsightsLoading(true);
    streamPortfolioSuggestions(userId, {
      onToken: (t) => {
        acc += t;
        setInsights(acc);
        setInsightsLoading(false);
      },
      onError: () => {
        setInsights("AI insights are temporarily unavailable.");
        setInsightsLoading(false);
      },
    })
      .catch(() => setInsights("AI insights are temporarily unavailable."))
      .finally(() => setInsightsLoading(false));
  }, [userId]);

  const dayChange = useMemo(() => {
    const holdings = metrics?.holdings ?? [];
    const totalWeight = holdings.reduce((a, h) => a + (h.weight ?? 0), 0) || 1;
    const wRet = holdings.reduce((a, h) => a + (h.weight ?? 0) * (h.return_pct ?? 0), 0) / totalWeight;
    const value = ((metrics?.total_value_inr ?? 0) * wRet) / 100;
    return { pct: wRet, value };
  }, [metrics]);

  const sectorData = useMemo(
    () =>
      Object.entries(metrics?.sector_allocation ?? {})
        .map(([name, weight]) => ({ name, value: Math.round(weight * 100) / 100 }))
        .sort((a, b) => b.value - a.value),
    [metrics]
  );

  return (
    <>
      {/* Page header */}
      <div className="flex flex-col gap-md sm:flex-row sm:justify-between sm:items-end mb-lg">
        <div>
          <h2 className="text-headline-lg-mobile md:text-headline-lg text-on-surface">Dashboard overview</h2>
          <p className="text-body-md text-on-surface-variant mt-xs">Real-time portfolio metrics and AI-driven market analysis.</p>
        </div>
        <div className="flex gap-sm shrink-0">
          <GhostButton>Export PDF</GhostButton>
          <PrimaryButton onClick={() => onNavigate("lakshya")}>New Analysis</PrimaryButton>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[132px]" />)
        ) : (
          <>
            <StatTile
              accent
              label="Portfolio Value"
              value={formatINR(metrics?.total_value_inr ?? 0)}
              sub={
                <span className="flex items-center gap-xs">
                  <Icon name="trending_up" className="text-[16px] text-positive" />
                  <span className="text-positive">{formatPct(dayChange.pct)}</span> since inception
                </span>
              }
            />
            <StatTile
              label="Day Change"
              value={`${dayChange.value >= 0 ? "+" : "-"}${formatINR(Math.abs(dayChange.value))}`}
              valueClass={dayChange.value >= 0 ? "text-positive" : "text-negative"}
              sub={
                <span className="flex items-center gap-xs">
                  <Icon name={dayChange.value >= 0 ? "arrow_upward" : "arrow_downward"} className={`text-[15px] ${dayChange.value >= 0 ? "text-positive" : "text-negative"}`} />
                  <span className={dayChange.value >= 0 ? "text-positive" : "text-negative"}>{formatPct(dayChange.pct)}</span>
                  <span className="text-on-surface-variant">portfolio return</span>
                </span>
              }
            />
            <StatTile label="Holdings" value={metrics?.holdings_count ?? 0} sub={<span className="flex items-center gap-xs"><Icon name="check_circle" className="text-[15px]" /> live portfolio</span>} icon="account_balance_wallet" />
            <StatTile label="Sim Balance" value={formatINR(simBalance ?? 0)} sub="Paper trading mode" icon="query_stats" />
          </>
        )}
      </div>

      {/* AI Insights + Headlines */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-md">
        {/* AI Insights */}
        <Card className="lg:col-span-3 flex flex-col">
          <CardHeader
            title="AI Insights"
            icon="bolt"
            right={
              <span className="flex items-center gap-sm text-primary text-body-sm">
                <span className="w-8 h-4 rounded-full bg-primary/30 relative"><span className="absolute right-0 top-0 w-4 h-4 rounded-full bg-primary" /></span>
                {insightsLoading ? "Analysing Markets…" : "Live"}
              </span>
            }
          />
          <div className="px-lg pb-lg flex flex-col min-h-0">
            <div className="max-h-[360px] overflow-y-auto pr-sm -mr-sm">
              {insightsLoading && !insights ? (
                <div className="space-y-sm">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                </div>
              ) : (
                <div className="text-body-md">
                  <Markdown>{insights}</Markdown>
                  {insightsLoading && <span className="inline-block w-[2px] h-4 bg-primary align-middle animate-blink ml-[2px]" />}
                </div>
              )}
            </div>
            <div className="flex gap-sm mt-md pt-md border-t border-outline-variant/50">
              <button className="text-body-sm text-on-surface-variant bg-bg-2 rounded-full px-md py-xs hover:text-on-surface" onClick={() => onNavigate("lakshya")}>Ask follow-up</button>
              <button className="text-body-sm text-on-surface-variant bg-bg-2 rounded-full px-md py-xs hover:text-on-surface" onClick={() => onNavigate("lakshya")}>Deep dive</button>
            </div>
          </div>
        </Card>

        {/* Market Headlines */}
        <Card className="lg:col-span-2">
          <CardHeader title="Market Headlines" right={<Icon name="rss_feed" className="text-[18px] text-on-surface-variant" />} />
          <div className="px-lg pb-lg divide-y divide-outline-variant/50">
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 my-sm" />)
            ) : headlines.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant py-md">No headlines available.</p>
            ) : (
              headlines.slice(0, 4).map((h, i) => (
                <a key={h.article_id ?? i} href={h.link ?? "#"} target="_blank" rel="noreferrer" className="block py-md group">
                  <div className="flex items-center justify-between mb-xs">
                    <span className="text-caption text-on-surface-variant">{h.source_name} · {timeAgo(h.pubDate)}</span>
                  </div>
                  <p className="text-body-sm text-on-surface group-hover:text-primary transition-colors line-clamp-2">{h.title}</p>
                </a>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Sector Allocation + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-md">
        {/* Donut */}
        <Card className="lg:col-span-2">
          <CardHeader title="Sector Allocation" />
          <div className="px-lg pb-lg">
            {sectorData.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant py-lg text-center">No holdings to allocate yet.</p>
            ) : (
              <div className="flex items-center gap-lg">
                <div className="relative w-40 h-40 shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={sectorData} dataKey="value" innerRadius={52} outerRadius={72} paddingAngle={2} stroke="none">
                        {sectorData.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-label-caps text-on-surface-variant">TOTAL</span>
                    <span className="text-[24px] font-semibold text-on-surface tabular">{metrics?.holdings_count ?? 0}</span>
                  </div>
                </div>
                <div className="flex-1 space-y-sm">
                  {sectorData.slice(0, 5).map((s, i) => (
                    <div key={s.name} className="flex items-center justify-between text-body-sm">
                      <span className="flex items-center gap-sm text-on-surface"><span className="w-2 h-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />{s.name}</span>
                      <span className="text-on-surface-variant tabular">{s.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Activity */}
        <Card className="lg:col-span-3">
          <CardHeader title="Recent Activity" />
          <div className="px-lg pb-lg">
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 my-sm" />)
            ) : timeline.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant py-md">No recent activity.</p>
            ) : (
              <ol className="space-y-md">
                {timeline.slice(0, 5).map((ev) => (
                  <li key={ev.id} className="flex gap-md">
                    <span className="mt-[6px] w-2 h-2 rounded-full bg-primary shrink-0" />
                    <div>
                      <p className="text-caption text-on-surface-variant">{new Date(ev.timestamp).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</p>
                      <p className="text-body-sm text-on-surface">{ev.title}</p>
                      {ev.summary && <p className="text-caption text-on-surface-variant line-clamp-1">{ev.summary}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
