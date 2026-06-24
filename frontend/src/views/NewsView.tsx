import { useEffect, useMemo, useState } from "react";
import {
  fetchNewsRadar,
  fetchCausalMarket,
  type EnrichedNewsItem,
  type CausalMarketData,
} from "../lib/api";
import { Card, CardHeader, Chip, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { timeAgo } from "../lib/format";

type SentimentFilter = "all" | "positive" | "negative" | "neutral";

const SENTIMENTS: SentimentFilter[] = ["all", "positive", "negative", "neutral"];

function sentimentTone(s: string): { tone: "positive" | "negative" | "neutral"; icon: string; label: string } {
  const v = s.toLowerCase();
  if (v.includes("pos")) return { tone: "positive", icon: "trending_up", label: "Positive" };
  if (v.includes("neg")) return { tone: "negative", icon: "trending_down", label: "Negative" };
  return { tone: "neutral", icon: "remove", label: "Neutral" };
}

export function NewsView() {
  const [items, setItems] = useState<EnrichedNewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<SentimentFilter>("all");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [market, setMarket] = useState<CausalMarketData | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        let n = await fetchNewsRadar(40, query || undefined);
        // Self-heal a thin/stale cache with a one-off fresh pull.
        if (!query && n.length < 10) {
          n = await fetchNewsRadar(40, undefined, "intermediate", true).catch(() => n);
        }
        if (!cancelled) setItems(n);
      } catch {
        if (!cancelled) setError("Could not load the news feed.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [query]);

  useEffect(() => {
    fetchCausalMarket()
      .then(setMarket)
      .catch(() => setMarket(null));
  }, []);

  const filtered = useMemo(
    () =>
      filter === "all"
        ? items
        : items.filter((i) => sentimentTone(i.sentiment).tone === filter),
    [items, filter]
  );

  const pulse = useMemo(() => {
    if (items.length === 0) return null;
    let pos = 0, neg = 0, neu = 0;
    for (const i of items) {
      const t = sentimentTone(i.sentiment).tone;
      if (t === "positive") pos++;
      else if (t === "negative") neg++;
      else neu++;
    }
    const total = items.length;
    // Net-sentiment score: 50 = balanced. Positive lift raises it, negative lowers it.
    const score = Math.round(Math.min(100, Math.max(0, 50 + ((pos - neg) / total) * 50)));
    const label = score > 55 ? "Bullish bias" : score < 45 ? "Bearish bias" : "Neutral bias";
    const tone: "positive" | "negative" | "neutral" =
      score > 55 ? "positive" : score < 45 ? "negative" : "neutral";
    return {
      score,
      label,
      tone,
      pos: (pos / total) * 100,
      neu: (neu / total) * 100,
      neg: (neg / total) * 100,
      counts: { pos, neu, neg },
    };
  }, [items]);

  const commodities = useMemo(() => {
    if (!market?.commodity_trends) return [];
    return Object.values(market.commodity_trends)
      .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
      .slice(0, 5);
  }, [market]);

  return (
    <div className="space-y-lg">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-md">
        <div>
          <h1 className="text-headline-lg font-semibold text-on-surface">Market News</h1>
          <p className="text-body-sm text-on-surface-variant mt-1 max-w-xl">
            Real-time financial news processed with sentiment analysis.
          </p>
        </div>
        <div className="flex items-center gap-sm flex-wrap">
          {SENTIMENTS.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`h-9 px-md rounded-lg text-body-sm capitalize border transition-colors ${
                filter === s
                  ? "bg-primary/15 border-primary/40 text-primary"
                  : "bg-bg-1 border-outline-variant text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center bg-bg-1 border border-outline-variant rounded-lg px-md h-11 focus-within:border-primary/50 transition-colors max-w-xl">
        <Icon name="search" className="text-on-surface-variant text-[18px] mr-sm" />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setQuery(draft.trim())}
          placeholder="Search news, tickers, or events…"
          className="bg-transparent text-body-sm text-on-surface focus:outline-none w-full placeholder:text-on-surface-variant"
        />
        {query && (
          <button
            onClick={() => {
              setDraft("");
              setQuery("");
            }}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <Icon name="close" className="text-[16px]" />
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* Feed */}
        <div className="lg:col-span-8 space-y-md">
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="p-lg space-y-sm">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-full" />
              </Card>
            ))
          ) : error ? (
            <Card className="p-lg text-body-sm text-negative">{error}</Card>
          ) : filtered.length === 0 ? (
            <Card className="p-2xl text-center text-body-sm text-on-surface-variant">
              No stories match this filter.
            </Card>
          ) : (
            filtered.map((n, i) => <NewsCard key={`${n.url}-${i}`} n={n} />)
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-4 space-y-lg">
          <Card>
            <CardHeader title="Global Sentiment Pulse" icon="monitoring" />
            <div className="px-lg pb-lg">
              {pulse ? (
                <>
                  <div className="flex items-baseline gap-sm">
                    <span
                      className={`text-[2rem] font-semibold tabular ${
                        pulse.tone === "positive"
                          ? "text-positive"
                          : pulse.tone === "negative"
                          ? "text-negative"
                          : "text-on-surface"
                      }`}
                    >
                      {pulse.score}%
                    </span>
                    <span className="text-body-sm text-on-surface-variant">{pulse.label}</span>
                  </div>
                  <div className="flex h-2 rounded-full overflow-hidden mt-md bg-bg-2">
                    <div className="bg-positive" style={{ width: `${pulse.pos}%` }} />
                    <div className="bg-on-surface-variant/40" style={{ width: `${pulse.neu}%` }} />
                    <div className="bg-negative" style={{ width: `${pulse.neg}%` }} />
                  </div>
                  <div className="flex items-center justify-between text-caption text-on-surface-variant mt-sm">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-positive" /> Positive {pulse.counts.pos}</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-on-surface-variant/40" /> Neutral {pulse.counts.neu}</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-negative" /> Negative {pulse.counts.neg}</span>
                  </div>
                </>
              ) : (
                <Skeleton className="h-16 w-full" />
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Trending Commodities" icon="oil_barrel" />
            <div className="px-lg pb-lg space-y-sm">
              {commodities.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant">No commodity data.</p>
              ) : (
                commodities.map((c) => {
                  const up = c.change_pct >= 0;
                  return (
                    <div key={c.name} className="flex items-center justify-between">
                      <span className="text-body-sm text-on-surface truncate pr-sm">
                        {c.name.replace(/_/g, " ")}
                      </span>
                      <span className="flex items-center gap-sm shrink-0">
                        <span className="text-body-sm tabular text-on-surface">
                          {c.current_price.toLocaleString("en-IN")}
                        </span>
                        <span className={`text-caption tabular ${up ? "text-positive" : "text-negative"}`}>
                          {up ? "▲" : "▼"} {Math.abs(c.change_pct).toFixed(2)}%
                        </span>
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function NewsCard({ n }: { n: EnrichedNewsItem }) {
  const s = sentimentTone(n.sentiment);
  const inner = (
    <>
      <div className="flex items-center gap-sm text-caption text-on-surface-variant">
        <Chip tone={s.tone}>
          <Icon name={s.icon} className="text-[13px] mr-1" />
          {s.label}
        </Chip>
        <span>• {timeAgo(n.published_at)}</span>
        {n.source && <span>• {n.source}</span>}
      </div>
      <h3 className="text-card-title font-semibold text-on-surface mt-sm group-hover:text-primary transition-colors">
        {n.title}
      </h3>
      {n.summary && (
        <p className="text-body-sm text-on-surface-variant mt-sm line-clamp-3">{n.summary}</p>
      )}
      {n.categories?.length > 0 && (
        <div className="flex flex-wrap gap-xs mt-md">
          {n.categories.slice(0, 4).map((c) => (
            <span key={c} className="text-caption text-on-surface-variant">
              #{c.replace(/\s+/g, "")}
            </span>
          ))}
        </div>
      )}
    </>
  );

  return (
    <Card className="p-lg group">
      {n.url ? (
        <a href={n.url} target="_blank" rel="noreferrer" className="block">
          {inner}
        </a>
      ) : (
        inner
      )}
    </Card>
  );
}
