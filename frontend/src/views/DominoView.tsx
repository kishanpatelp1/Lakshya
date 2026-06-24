import { Fragment, useEffect, useMemo, useState } from "react";
import {
  analyzeCausalTrigger,
  fetchCausalMarket,
  type CausalChainItem,
  type CausalGeoEvent,
  type CausalLLMData,
  type CausalMarketData,
} from "../lib/api";
import { timeAgo } from "../lib/format";
import { Icon } from "../components/Icon";
import { Card, CardHeader, Chip, Skeleton } from "../components/ui";

/* ── Commodity ticker ─────────────────────────────────────────────────── */
function CommodityTicker({ trends }: { trends: CausalMarketData["commodity_trends"] }) {
  const items = Object.entries(trends);
  if (items.length === 0) return null;
  return (
    <div className="flex items-stretch gap-0 overflow-x-auto rounded-lg border border-outline-variant bg-bg-1 no-scrollbar">
      {items.map(([sym, t], i) => {
        const up = t.change_pct >= 0;
        return (
          <div key={sym} className={`flex items-center gap-sm px-lg py-md whitespace-nowrap ${i > 0 ? "border-l border-outline-variant" : ""}`}>
            <span className="text-label-caps font-label-caps text-on-surface-variant">{t.name || sym}</span>
            <span className={`text-body-sm font-semibold tabular ${up ? "text-positive" : "text-negative"}`}>
              {up ? "+" : ""}
              {t.change_pct.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Causal flow graph (responsive) ───────────────────────────────────── */
type Tone = "serious" | "moderate" | "target" | "muted";
interface FlowNode {
  tier: string;
  name: string;
  sub?: string;
  tone: Tone;
}

const nodeTone: Record<Tone, string> = {
  serious: "border-serious text-serious shadow-[0_0_20px_rgba(239,68,68,0.15)]",
  moderate: "border-moderate text-moderate shadow-[0_0_15px_rgba(245,158,11,0.12)]",
  target: "border-primary text-primary bg-primary/10 shadow-[0_0_20px_rgba(0,229,255,0.15)]",
  muted: "border-no-effect text-no-effect",
};

/** Pick a Material Symbol that reflects the commodity/sector in a node. */
function iconFor(name: string, target = false): string {
  const n = (name || "").toLowerCase();
  const map: [RegExp, string][] = [
    [/crude|brent|wti|oil|petrol|diesel|\bfuel|naphtha/, "local_fire_department"],
    [/natural gas|\blng\b|\bgas\b/, "mode_heat"],
    [/gold|xau|silver|xag|bullion/, "toll"],
    [/copper|alumin|steel|zinc|iron|metal|foundr/, "foundry"],
    [/coal/, "workspaces"],
    [/sugar|wheat|corn|grain|coffee|agri|cane|ethanol/, "grass"],
    [/aviation|airline|flight|\bjet\b|\batf\b|\bair\b/, "flight"],
    [/bank|financ|nbfc|lend/, "account_balance"],
    [/auto|car|vehicle|\bev\b/, "directions_car"],
    [/power|energy|electric|utilit/, "bolt"],
    [/pharma|health|drug|medic/, "medical_services"],
    [/software|\bit\b|tech|semiconduc|chip/, "memory"],
    [/fmcg|consumer|retail/, "shopping_cart"],
    [/real estate|realty|property|housing/, "home_work"],
    [/telecom|mobile/, "cell_tower"],
    [/cement|infra|construc/, "apartment"],
    [/textile|apparel|cotton/, "checkroom"],
    [/transport|logistic|shipping|freight|truck/, "local_shipping"],
    [/margin|eps|earnings|profit/, "trending_down"],
    [/usd|inr|rupee|currency|forex/, "currency_exchange"],
  ];
  for (const [re, icon] of map) if (re.test(n)) return icon;
  return target ? "domain" : "hub";
}

function Node({ node }: { node: FlowNode }) {
  return (
    <div className="flex flex-col items-center shrink-0">
      <div className={`w-16 h-16 rounded-full bg-bg-2 border-2 flex items-center justify-center transition-transform hover:scale-105 ${nodeTone[node.tone]}`}>
        <Icon name={iconFor(node.name, node.tone === "target")} className="text-[24px]" />
      </div>
      <div className={`mt-sm text-center bg-bg-0 border rounded p-xs min-w-[120px] max-w-[160px] ${node.tone === "target" ? "border-primary" : "border-outline-variant"}`}>
        <div className={`text-label-caps font-label-caps ${node.tone === "target" ? "text-primary" : "text-on-surface-variant"}`}>{node.tier}</div>
        <div className="text-body-md text-on-surface font-semibold truncate">{node.name}</div>
        {node.sub && <div className="text-caption text-on-surface-variant truncate">{node.sub.replace(/_/g, " ")}</div>}
      </div>
    </div>
  );
}

/** Dashed connector aligned to the node circles: a growing horizontal line on
 * desktop, a short vertical line on mobile, with the relationship label on it. */
function Connector({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center md:flex-1 md:h-16">
      <div className="relative flex items-center justify-center h-8 w-8 md:h-full md:w-full">
        <div className="md:hidden h-8 border-l-2 border-dashed border-outline-variant/70" />
        <div className="hidden md:block w-full border-t-2 border-dashed border-outline-variant/70" />
        {label && (
          <span className="absolute bg-bg-1 border border-outline-variant rounded-sm px-xs py-[1px] text-caption text-on-surface-variant whitespace-nowrap max-w-[120px] truncate">
            {label.replace(/_/g, " ")}
          </span>
        )}
      </div>
    </div>
  );
}

function FlowGraph({ chain }: { chain: CausalChainItem }) {
  const nodes: FlowNode[] = [
    { tier: "TRIGGER", name: chain.trigger_value, tone: "serious" },
    { tier: "HOP 1", name: chain.hop1_target, tone: "moderate" },
  ];
  if (chain.hop2_target) nodes.push({ tier: "HOP 2", name: chain.hop2_target, tone: "serious" });
  if (chain.hop3_target) nodes.push({ tier: "TARGET IMPACT", name: chain.hop3_target, tone: "target" });

  const relationships = [chain.hop1_relationship, chain.hop2_relationship, chain.hop3_relationship];

  return (
    // Outer flexbox centres the whole flow vertically; inner group aligns the
    // circles to the top so the dashed path lines up across nodes.
    <div className="flex-1 flex flex-col items-center justify-center py-lg min-h-[300px] gap-md">
      <div className="flex flex-col md:flex-row items-center md:items-start w-full">
        {nodes.map((n, i) => (
          <Fragment key={i}>
            <Node node={n} />
            {i < nodes.length - 1 && <Connector label={relationships[i] ?? undefined} />}
          </Fragment>
        ))}
      </div>
      {(chain.affected_companies?.length ?? 0) > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-sm">
          <span className="text-label-caps font-label-caps text-on-surface-variant">
            Stocks likely affected
          </span>
          {chain.affected_companies!.map((c) => (
            <span
              key={c.id}
              title={c.name}
              className="text-caption font-medium text-on-surface bg-bg-2 border border-outline-variant rounded-full px-sm py-[2px]"
            >
              {c.ticker || c.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── GDELT feed ───────────────────────────────────────────────────────── */
const badgeToneClass: Record<"negative" | "warning" | "neutral", string> = {
  negative: "bg-negative/10 text-negative",
  warning: "bg-moderate/10 text-moderate",
  neutral: "bg-no-effect/10 text-no-effect",
};

/** Real Goldstein when the feed provides it; else fall back to the event category
 * (the free GDELT feed does not carry a Goldstein scale). */
function eventBadge(ev: CausalGeoEvent): { label: string; tone: "negative" | "warning" | "neutral" } {
  if (ev.goldstein_scale !== null && ev.goldstein_scale !== undefined) {
    const g = ev.goldstein_scale;
    return { label: `Goldstein: ${g.toFixed(1)}`, tone: g <= -5 ? "negative" : g < 0 ? "warning" : "neutral" };
  }
  const cat = (ev.category || "event").toLowerCase();
  const tone = /conflict|war|crisis|disrupt/.test(cat) ? "negative" : /econom|trade|policy/.test(cat) ? "warning" : "neutral";
  return { label: (ev.category || "Signal").toUpperCase(), tone };
}

function GdeltFeed({ events }: { events: CausalGeoEvent[] }) {
  return (
    <Card className="flex flex-col flex-1 min-h-0">
      <CardHeader title="Global Events (GDELT)" icon="public" right={<span className="text-caption text-on-surface-variant">{events.length}</span>} />
      <div className="px-md pb-md flex flex-col gap-sm overflow-y-auto max-h-[420px]">
        {events.length === 0 ? (
          <p className="text-body-sm text-on-surface-variant py-md">No significant geopolitical events right now.</p>
        ) : (
          events.map((ev, i) => {
            const badge = eventBadge(ev);
            return (
              <div key={i} className="bg-bg-0 border border-outline-variant rounded p-sm hover:border-primary/50 transition-colors">
                <div className="flex justify-between items-start mb-xs gap-sm">
                  <span className={`text-label-caps font-label-caps rounded-sm px-xs py-[2px] ${badgeToneClass[badge.tone]}`}>{badge.label}</span>
                  <span className="text-caption text-on-surface-variant shrink-0">{timeAgo(ev.date)}</span>
                </div>
                <p className="text-body-sm text-on-surface mb-xs line-clamp-3">{ev.title}</p>
                <div className="flex items-center gap-xs text-caption text-on-surface-variant">
                  <Icon name="link" className="text-[14px]" /> {ev.country || ev.category || "Global"}
                </div>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}

/* ── Lakshya synthesis ────────────────────────────────────────────────── */
function LakshyaSynthesis({ chain }: { chain: CausalChainItem | null }) {
  const [data, setData] = useState<CausalLLMData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setData(null);
  }, [chain?.id]);

  const run = async () => {
    if (!chain) return;
    setLoading(true);
    try {
      const trigger = `${chain.name}: ${chain.trigger_value} affecting ${chain.hop1_target}${chain.hop2_target ? ` and ${chain.hop2_target}` : ""}`;
      const res = await analyzeCausalTrigger(trigger);
      setData(res);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-bg-2 border border-primary/30 rounded-lg p-md relative overflow-hidden">
      <div className="absolute top-0 right-0 p-sm opacity-20 pointer-events-none">
        <Icon name="auto_awesome" className="text-[48px] text-primary" />
      </div>
      <h3 className="text-card-title font-card-title text-primary mb-sm flex items-center gap-xs">
        <Icon name="psychology" className="text-[16px]" /> Lakshya Synthesis
      </h3>
      {loading ? (
        <div className="space-y-sm mb-md">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <Skeleton className="h-3 w-3/4" />
        </div>
      ) : data ? (
        <div className="text-body-sm text-on-surface leading-relaxed mb-md space-y-sm max-h-[220px] overflow-y-auto pr-xs">
          {data.hidden_impacts.slice(0, 3).map((h, i) => (
            <p key={i}>
              <span className={`font-semibold ${h.direction === "positive" ? "text-positive" : h.direction === "negative" ? "text-negative" : "text-on-surface"}`}>{h.sector}</span>{" "}
              <span className="text-on-surface-variant">— {h.reasoning}</span>
              {(h.companies?.length ?? 0) > 0 && (
                <span className="block mt-0.5">
                  {h.companies!.slice(0, 3).map((c) => (
                    <span key={c.id} title={c.name} className="inline-block text-caption text-on-surface bg-bg-1 border border-outline-variant rounded-full px-sm py-[1px] mr-xs">
                      {c.ticker || c.name}
                    </span>
                  ))}
                </span>
              )}
            </p>
          ))}
          {data.opportunities.length > 0 && (
            <div className="flex flex-wrap gap-xs pt-xs">
              {data.opportunities.slice(0, 3).map((o, i) => <Chip key={i} tone="positive">{o}</Chip>)}
            </div>
          )}
        </div>
      ) : (
        <p className="text-body-sm text-on-surface-variant leading-relaxed mb-md">
          Run a deep AI analysis of this chain to uncover hidden 2nd/3rd-order impacts, opportunities and risks — grounded in the verified exposure graph.
        </p>
      )}
      <div className="flex gap-sm">
        <button onClick={run} disabled={!chain || loading} className="flex-1 bg-primary text-on-primary text-label-caps font-label-caps py-sm rounded font-bold hover:opacity-90 transition-opacity disabled:opacity-50">
          {loading ? "ANALYSING…" : "RUN ANALYSIS"}
        </button>
      </div>
    </div>
  );
}

/* ── View ─────────────────────────────────────────────────────────────── */
export function DominoView() {
  const [market, setMarket] = useState<CausalMarketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchCausalMarket()
      .then((m) => {
        if (!alive) return;
        setMarket(m);
        setSelectedId(m.causal_chains[0]?.id ?? null);
      })
      .catch(() => {})
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const selected = useMemo(
    () => market?.causal_chains.find((c) => c.id === selectedId) ?? market?.causal_chains[0] ?? null,
    [market, selectedId]
  );

  const confidence = Math.round((selected?.confidence ?? 0) * 100);

  return (
    <>
      {/* Header */}
      <div className="mb-md">
        <h2 className="text-headline-lg-mobile md:text-headline-lg text-on-surface">Domino Effect</h2>
        <p className="text-body-md text-on-surface-variant mt-xs">Real-time causal intelligence &amp; market ripple analysis.</p>
      </div>

      {/* Commodity ticker */}
      {loading ? <Skeleton className="h-14" /> : <CommodityTicker trends={market?.commodity_trends ?? {}} />}

      {/* Chain selector */}
      {!loading && (market?.causal_chains.length ?? 0) > 0 && (
        <div className="flex gap-sm overflow-x-auto no-scrollbar pb-xs">
          {market!.causal_chains.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              className={`shrink-0 px-md py-sm rounded-full text-body-sm border transition-colors whitespace-nowrap ${
                selected?.id === c.id ? "bg-primary text-on-primary border-primary" : "bg-bg-1 text-on-surface-variant border-outline-variant hover:text-on-surface"
              }`}
            >
              {c.is_active_now && (
                <span title={c.activating_event ?? "Live event matches this chain"} className="mr-1">⚡</span>
              )}
              {c.name}
            </button>
          ))}
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* Hero flow */}
        <div className="lg:col-span-8 bg-bg-1 border border-outline-variant rounded-lg p-lg relative overflow-hidden flex flex-col">
          <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at 10% 20%, rgba(0,229,255,0.12) 0%, transparent 40%)" }} />
          {loading ? (
            <Skeleton className="h-[360px]" />
          ) : !selected ? (
            <div className="flex flex-col items-center justify-center min-h-[360px] text-center">
              <Icon name="account_tree" className="text-[36px] text-on-surface-variant mb-sm" />
              <p className="text-body-md text-on-surface-variant">No active causal chains tracked yet.</p>
            </div>
          ) : (
            <>
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-sm mb-md relative z-10">
                <div>
                  <div className="flex items-center gap-sm mb-xs">
                    <Icon name="warning" className="text-serious text-[20px]" />
                    <h3 className="text-section-header text-on-surface">Active Causal Chain: {selected.name}</h3>
                  </div>
                  <p className="text-body-sm text-on-surface-variant">Trigger: {selected.trigger_type.replace(/_/g, " ")}</p>
                </div>
                <div className="flex items-center gap-sm bg-bg-2 border border-outline-variant rounded-full px-md py-xs shrink-0 self-start">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-label-caps font-label-caps text-primary">LIVE MONITORING</span>
                </div>
              </div>

              <FlowGraph chain={selected} />

              {/* Confidence footer */}
              <div className="mt-auto pt-md border-t border-outline-variant flex flex-col sm:flex-row sm:justify-between sm:items-center gap-sm bg-bg-0 p-sm rounded relative z-10">
                <div className="flex items-center gap-md">
                  <div className="text-label-caps font-label-caps text-on-surface-variant">CHAIN CONFIDENCE</div>
                  <div className="flex items-center gap-sm">
                    <div className="w-32 h-1.5 bg-surface-container rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${confidence >= 70 ? "bg-positive" : confidence >= 40 ? "bg-moderate" : "bg-negative"}`} style={{ width: `${confidence}%` }} />
                    </div>
                    <span className="text-body-sm text-on-surface font-semibold">{confidence}%</span>
                  </div>
                  {selected.verified_confidence != null && (
                    <div
                      className="text-caption text-positive mt-1"
                      title="Backed by 2 years of real price history"
                    >
                      ✓ market-verified {Math.round(selected.verified_confidence * 100)}%
                      {(selected.verified_lag_days ?? 0) > 0 && (
                        <span className="text-on-surface-variant"> · leads by ~{selected.verified_lag_days}d</span>
                      )}
                    </div>
                  )}
                  {selected.is_active_now && selected.activating_event && (
                    <div className="text-caption text-warning mt-1" title={selected.activating_event}>
                      ⚡ Live: {selected.activating_event.slice(0, 60)}
                    </div>
                  )}
                </div>
                {selected.current_commodity_change_pct !== undefined && (
                  <span className="text-caption text-on-surface-variant flex items-center gap-1">
                    <Icon name="show_chart" className="text-[14px]" /> Commodity move: {selected.current_commodity_change_pct >= 0 ? "+" : ""}
                    {selected.current_commodity_change_pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </>
          )}
        </div>

        {/* Right rail */}
        <div className="lg:col-span-4 flex flex-col gap-lg">
          {loading ? <Skeleton className="h-64" /> : <GdeltFeed events={market?.geopolitical_events ?? []} />}
          <LakshyaSynthesis chain={selected} />
        </div>
      </div>
    </>
  );
}
