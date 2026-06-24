import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchCompanyDetail,
  fetchCompanyQuote,
  fetchCompanyFinancials,
  fetchCompanyRatios,
  fetchHistoricalPrices,
  fetchCompanyInsights,
  streamChatQuery,
  type AICompany,
  type AIQuote,
  type AIFinancials,
  type AIRatios,
  type AIHistoricalPrice,
  type CompanyInsights,
} from "../lib/api";
import { typeMeta } from "./InsightsView";
import { Card, CardHeader, Chip, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { Markdown } from "../components/Markdown";
import { CompanySearch } from "../components/CompanySearch";
import { formatINR, formatPct } from "../lib/format";
import { getUserId } from "../lib/user";

const RANGES: { label: string; days: number }[] = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
];

interface Props {
  companyId: string | null;
  onOpenCompany: (id: string) => void;
}

export function CompanyView({ companyId, onOpenCompany }: Props) {
  if (!companyId) {
    return (
      <div className="max-w-xl mx-auto mt-2xl text-center space-y-lg">
        <div>
          <h1 className="text-headline-lg font-semibold text-on-surface">
            Company Workspace
          </h1>
          <p className="text-body-sm text-on-surface-variant mt-1">
            Search a company to open its research workspace.
          </p>
        </div>
        <CompanySearch
          placeholder="Search ticker, company, or concept…"
          onSelect={(c) => onOpenCompany(c.id)}
        />
      </div>
    );
  }
  return <Workspace companyId={companyId} onOpenCompany={onOpenCompany} />;
}

function Workspace({
  companyId,
  onOpenCompany,
}: {
  companyId: string;
  onOpenCompany: (id: string) => void;
}) {
  const [detail, setDetail] = useState<AICompany | null>(null);
  const [quote, setQuote] = useState<AIQuote | null>(null);
  const [financials, setFinancials] = useState<AIFinancials | null>(null);
  const [ratios, setRatios] = useState<AIRatios | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    setQuote(null);
    setFinancials(null);
    setRatios(null);
    Promise.allSettled([
      fetchCompanyDetail(companyId),
      fetchCompanyQuote(companyId),
      fetchCompanyFinancials(companyId, 4),
      fetchCompanyRatios(companyId),
    ]).then(([d, q, f, r]) => {
      if (cancelled) return;
      if (d.status === "fulfilled") setDetail(d.value);
      else setError("Could not load this company.");
      if (q.status === "fulfilled") setQuote(q.value);
      if (f.status === "fulfilled") setFinancials(f.value);
      if (r.status === "fulfilled") setRatios(r.value);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const ticker = detail?.ticker_nse ?? detail?.ticker_bse ?? "";
  const up = (quote?.change_pct ?? 0) >= 0;

  return (
    <div className="space-y-lg">
      {/* Header + switcher */}
      <div className="flex flex-col gap-md md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-sm mb-sm">
            {ticker && (
              <Chip tone="neutral">
                {detail?.ticker_nse ? "NSE" : "BSE"}: {ticker}
              </Chip>
            )}
            {detail?.sector && <Chip tone="tag">{detail.sector}</Chip>}
          </div>
          {loading && !detail ? (
            <Skeleton className="h-9 w-72" />
          ) : (
            <h1 className="text-headline-lg font-semibold text-on-surface truncate">
              {detail?.name ?? "Unknown company"}
            </h1>
          )}
        </div>

        <div className="flex flex-col items-start md:items-end gap-sm shrink-0">
          {quote?.last_price != null ? (
            <>
              <div className="flex items-baseline gap-sm">
                <span className="text-headline-lg font-semibold text-on-surface tabular">
                  {formatINR(quote.last_price)}
                </span>
                <span
                  className={`text-card-title font-medium tabular ${
                    up ? "text-positive" : "text-negative"
                  }`}
                >
                  <Icon
                    name={up ? "arrow_upward" : "arrow_downward"}
                    className="text-[16px]"
                  />
                  {formatPct(Math.abs(quote.change_pct ?? 0))}
                </span>
              </div>
              {quote.fetched_at && (
                <span className="text-caption text-on-surface-variant">
                  As of {new Date(quote.fetched_at).toLocaleString("en-IN")}
                </span>
              )}
            </>
          ) : (
            <div className="w-40">
              <CompanySearch
                placeholder="Switch company…"
                onSelect={(c) => onOpenCompany(c.id)}
              />
            </div>
          )}
        </div>
      </div>

      {error && !detail ? (
        <Card className="text-body-sm text-negative">{error}</Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
          {/* Left / main */}
          <div className="lg:col-span-8 space-y-lg">
            <PriceChart companyId={companyId} />
            <KpiRow quote={quote} detail={detail} ratios={ratios} loading={loading} />
            <FinancialsCard financials={financials} ratios={ratios} loading={loading} />
            <InsightsPanel companyId={companyId} />
          </div>

          {/* Right / Lakshya */}
          <div className="lg:col-span-4">
            <LakshyaPanel companyId={companyId} name={detail?.name} />
          </div>
        </div>
      )}
    </div>
  );
}

function PriceChart({ companyId }: { companyId: string }) {
  const [range, setRange] = useState(RANGES[0]);
  const [prices, setPrices] = useState<AIHistoricalPrice[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchHistoricalPrices(companyId, range.days)
      .then((r) => !cancelled && setPrices(r.prices))
      .catch(() => !cancelled && setPrices([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [companyId, range.days]);

  const gain = useMemo(() => {
    if (!prices || prices.length < 2) return true;
    return prices[prices.length - 1].close >= prices[0].close;
  }, [prices]);
  const color = gain ? "#22c55e" : "#ef4444";

  return (
    <Card>
      <CardHeader
        title="Price Movement"
        icon="show_chart"
        right={
          <div className="flex items-center gap-1 bg-bg-0 border border-outline-variant rounded-md p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => setRange(r)}
                className={`px-sm py-[3px] rounded text-label-caps font-label-caps transition-colors ${
                  r.label === range.label
                    ? "bg-bg-2 text-on-surface"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      />

      <div className="px-lg pb-lg">
      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : !prices || prices.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-body-sm text-on-surface-variant">
          No price history available.
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={prices} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                tickFormatter={(d: string) =>
                  new Date(d).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                  })
                }
                minTickGap={40}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                width={48}
                tickFormatter={(v: number) => `₹${Math.round(v)}`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "rgb(var(--bg-1))",
                  border: "1px solid rgb(var(--outline-variant))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "rgb(var(--text-muted))" }}
                formatter={(v: number) => [formatINR(v), "Close"]}
                labelFormatter={(d: string) =>
                  new Date(d).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                }
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={color}
                strokeWidth={2}
                fill="url(#priceFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      </div>
    </Card>
  );
}

function KpiRow({
  quote,
  detail,
  ratios,
  loading,
}: {
  quote: AIQuote | null;
  detail: AICompany | null;
  ratios: AIRatios | null;
  loading: boolean;
}) {
  const r = ratios?.ratios ?? {};
  const marketCap = quote?.market_cap ?? detail?.market_cap_inr;
  const tiles = [
    {
      label: "Market Cap",
      value: marketCap ? formatINR(marketCap, { compact: true }) : "—",
    },
    {
      label: "P/E Ratio",
      value: r.pe_ratio != null ? r.pe_ratio.toFixed(2) : "—",
    },
    {
      label: "ROE",
      value: r.roe != null ? formatPct(r.roe * 100, 1) : "—",
    },
    {
      label: "Debt / Equity",
      value: r.debt_to_equity != null ? r.debt_to_equity.toFixed(2) : "—",
    },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
      {tiles.map((t) => (
        <Card key={t.label} className="p-lg">
          <div className="text-label-caps font-label-caps text-on-surface-variant">
            {t.label}
          </div>
          {loading ? (
            <Skeleton className="h-7 w-20 mt-sm" />
          ) : (
            <div className="text-card-title font-semibold text-on-surface tabular mt-1">
              {t.value}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

// Maps a financial line item to its YoY growth ratio, when available.
const GROWTH_KEY: Record<string, string> = {
  Revenue: "revenue_growth_yoy",
  "Net Profit": "pat_growth_yoy",
};

function FinancialsCard({
  financials,
  ratios,
  loading,
}: {
  financials: AIFinancials | null;
  ratios: AIRatios | null;
  loading: boolean;
}) {
  const latest = financials?.periods?.[0];
  const growth = ratios?.ratios ?? {};

  return (
    <Card>
      <CardHeader
        title="Key Financials"
        icon="account_balance"
        right={
          latest?.period_end ? (
            <span className="text-caption text-on-surface-variant">
              as of {latest.period_end}
            </span>
          ) : undefined
        }
      />
      <div className="px-lg pb-lg">
      {loading ? (
        <div className="space-y-sm">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      ) : !latest || latest.items.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">
          No financial statements on file yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="text-label-caps font-label-caps text-on-surface-variant border-b border-outline-variant">
                <th className="text-left font-normal py-sm">Metric</th>
                <th className="text-right font-normal py-sm">Value</th>
                <th className="text-right font-normal py-sm">YoY</th>
              </tr>
            </thead>
            <tbody>
              {latest.items.map((it) => {
                const g = growth[GROWTH_KEY[it.line_item]];
                const gUp = (g ?? 0) >= 0;
                return (
                  <tr
                    key={it.line_item}
                    className="border-b border-outline-variant/50 last:border-0"
                  >
                    <td className="py-sm text-on-surface">{it.line_item}</td>
                    <td className="py-sm text-right text-on-surface tabular">
                      {it.value != null
                        ? `${it.value.toLocaleString("en-IN")} ${it.unit}`
                        : "—"}
                    </td>
                    <td className="py-sm text-right tabular">
                      {g != null ? (
                        <span className={gUp ? "text-positive" : "text-negative"}>
                          {gUp ? "▲" : "▼"} {formatPct(Math.abs(g * 100), 1)}
                        </span>
                      ) : (
                        <span className="text-on-surface-variant">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      </div>
    </Card>
  );
}

function InsightsPanel({ companyId }: { companyId: string }) {
  const [data, setData] = useState<CompanyInsights | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    fetchCompanyInsights(companyId, 12)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  return (
    <Card>
      <CardHeader
        title="Investor Signals"
        icon="lightbulb"
        right={
          data && data.digest.total > 0 ? (
            <span className="text-caption text-on-surface-variant">{data.digest.total} extracted</span>
          ) : undefined
        }
      />
      <div className="px-lg pb-lg">
        {loading ? (
          <div className="space-y-sm">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        ) : !data || data.insights.length === 0 ? (
          <p className="text-body-sm text-on-surface-variant">
            No document insights yet. Lakshya enriches concalls & filings as they're ingested.
          </p>
        ) : (
          <ul className="space-y-md">
            {data.insights.map((it) => {
              const meta = typeMeta(it.insight_type);
              return (
                <li key={it.id} className="flex gap-md">
                  <Icon
                    name={meta.icon}
                    className={`text-[18px] shrink-0 mt-0.5 ${
                      it.severity === "high"
                        ? "text-negative"
                        : it.severity === "medium"
                        ? "text-warning"
                        : "text-on-surface-variant"
                    }`}
                  />
                  <div className="min-w-0">
                    <div className="text-body-md text-on-surface font-medium">{it.title}</div>
                    {it.plain_summary && (
                      <div className="text-body-sm text-on-surface mt-0.5">{it.plain_summary}</div>
                    )}
                    {it.detail && (
                      <div className="text-body-sm text-on-surface-variant mt-0.5">{it.detail}</div>
                    )}
                    {it.source_quote && (
                      <div className="text-caption text-on-surface-variant italic mt-1 border-l-2 border-outline-variant pl-sm">
                        “{it.source_quote}”
                      </div>
                    )}
                    <div className="text-caption text-on-surface-variant mt-1">
                      {meta.label}
                      {it.doc_type ? ` · ${it.doc_type}` : ""}
                      {it.period ? ` · ${it.period}` : ""}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}

function LakshyaPanel({
  companyId,
  name,
}: {
  companyId: string;
  name?: string;
}) {
  const [text, setText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function run() {
    if (!name) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setText("");
    setError(null);
    setStreaming(true);
    streamChatQuery(
      {
        user_id: getUserId(),
        company_id: companyId,
        expertise_level: "advanced",
        query: `Give a concise research briefing on ${name}: recent performance, the single most important risk factor, and the near-term outlook. Keep it under 180 words.`,
      },
      {
        onToken: (t) => setText((prev) => prev + t),
        onDone: () => setStreaming(false),
        onError: (d) => {
          setError(d);
          setStreaming(false);
        },
      },
      controller.signal
    ).catch(() => setStreaming(false));
  }

  useEffect(() => {
    run();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, name]);

  return (
    <Card className="lg:sticky lg:top-[calc(4rem+24px)] flex flex-col max-h-[calc(100vh-8rem)] p-lg">
      <div className="flex items-center justify-between mb-md shrink-0">
        <div className="flex items-center gap-sm">
          <Icon name="bolt" className="text-primary text-[20px]" />
          <span className="text-card-title font-semibold text-on-surface">
            Lakshya Analysis
          </span>
        </div>
        {streaming ? (
          <span className="flex items-center gap-1.5 text-label-caps font-label-caps text-primary">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-blink" />
            STREAMING
          </span>
        ) : (
          <button
            onClick={run}
            title="Regenerate"
            className="text-on-surface-variant hover:text-primary transition-colors"
          >
            <Icon name="refresh" className="text-[18px]" />
          </button>
        )}
      </div>

      <div className="overflow-y-auto flex-1 min-h-[120px]">
        {error && !text ? (
          <p className="text-body-sm text-negative">{error}</p>
        ) : !text && streaming ? (
          <div className="space-y-sm">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : (
          <Markdown>{text}</Markdown>
        )}
      </div>
    </Card>
  );
}
