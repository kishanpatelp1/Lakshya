import { useEffect, useState } from "react";
import {
  fetchCompanyDetail,
  fetchCompanyQuote,
  fetchCompanyRatios,
  compareCompanies,
  type AICompany,
  type AIQuote,
  type AIRatios,
  type CompareResponse,
  type CompareWinner,
} from "../lib/api";
import { Card, CardHeader, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { Markdown } from "../components/Markdown";
import { CompanySearch } from "../components/CompanySearch";
import { formatINR, formatPct } from "../lib/format";
import { getUserId } from "../lib/user";

interface Slot {
  company: AICompany;
  quote: AIQuote | null;
  ratios: AIRatios | null;
}

type Side = "A" | "B";

// Higher-is-better unless noted; used to pick the winning cell.
const METRICS: {
  label: string;
  get: (s: Slot) => number | null | undefined;
  fmt: (v: number) => string;
  lowerBetter?: boolean;
}[] = [
  { label: "Market Cap", get: (s) => s.quote?.market_cap ?? s.company.market_cap_inr, fmt: (v) => formatINR(v, { compact: true }) },
  { label: "Last Price", get: (s) => s.quote?.last_price, fmt: (v) => formatINR(v) },
  { label: "Day Change", get: (s) => s.quote?.change_pct, fmt: (v) => `${v >= 0 ? "+" : ""}${formatPct(v)}` },
  { label: "P/E Ratio", get: (s) => s.ratios?.ratios?.pe_ratio, fmt: (v) => v.toFixed(2), lowerBetter: true },
  { label: "ROE", get: (s) => s.ratios?.ratios?.roe, fmt: (v) => formatPct(v * 100, 1) },
  { label: "Net Margin", get: (s) => s.ratios?.ratios?.net_margin, fmt: (v) => formatPct(v * 100, 1) },
  { label: "Debt / Equity", get: (s) => s.ratios?.ratios?.debt_to_equity, fmt: (v) => v.toFixed(2), lowerBetter: true },
];

export function CompareView() {
  const [a, setA] = useState<Slot | null>(null);
  const [b, setB] = useState<Slot | null>(null);
  const [verdict, setVerdict] = useState<CompareResponse | null>(null);
  const [verdictLoading, setVerdictLoading] = useState(false);
  const [verdictError, setVerdictError] = useState<string | null>(null);

  async function pick(side: Side, id: string) {
    const set = side === "A" ? setA : setB;
    try {
      const [detail, quote, ratios] = await Promise.all([
        fetchCompanyDetail(id),
        fetchCompanyQuote(id).catch(() => null),
        fetchCompanyRatios(id).catch(() => null),
      ]);
      set({ company: detail, quote, ratios });
    } catch {
      /* ignore */
    }
  }

  // Run the Lakshya verdict whenever both companies are chosen (or changed).
  const aId = a?.company.id;
  const bId = b?.company.id;
  useEffect(() => {
    if (!a || !b) {
      setVerdict(null);
      setVerdictError(null);
      return;
    }
    let cancelled = false;
    setVerdict(null);
    setVerdictError(null);
    setVerdictLoading(true);
    compareCompanies({
      user_id: getUserId(),
      company_names: [a.company.name, b.company.name],
    })
      .then((resp) => {
        if (!cancelled) setVerdict(resp);
      })
      .catch(() => {
        if (!cancelled)
          setVerdictError(
            "Lakshya could not synthesize a verdict. The metric comparison above is still valid."
          );
      })
      .finally(() => {
        if (!cancelled) setVerdictLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aId, bId]);

  const both = a && b;

  return (
    <div className="space-y-lg">
      <div>
        <h1 className="text-headline-lg font-semibold text-on-surface">Compare</h1>
        <p className="text-body-sm text-on-surface-variant mt-1">
          Deep-dive structural analysis of two entities, side by side.
        </p>
      </div>

      {/* Company header cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
        <SlotCard slot={a} onPick={(id) => pick("A", id)} onClear={() => setA(null)} label="Company A" />
        <SlotCard slot={b} onPick={(id) => pick("B", id)} onClear={() => setB(null)} label="Company B" />
      </div>

      {!both ? (
        <Card className="text-center py-2xl px-lg">
          <Icon name="compare_arrows" className="text-on-surface-variant text-[32px] mb-sm" />
          <p className="text-body-sm text-on-surface-variant">
            Select two companies to compare their fundamentals and get a Lakshya verdict.
          </p>
        </Card>
      ) : (
        <>
          {/* Metrics table */}
          <Card>
            <CardHeader title="Key Metrics" icon="table_rows" />
            <div className="px-lg pb-lg overflow-x-auto">
              <table className="w-full text-body-sm">
                <thead>
                  <tr className="text-label-caps font-label-caps text-on-surface-variant border-b border-outline-variant">
                    <th className="text-left font-normal py-sm">Metric</th>
                    <th className="text-right font-normal py-sm">{a.company.name}</th>
                    <th className="text-right font-normal py-sm">{b.company.name}</th>
                  </tr>
                </thead>
                <tbody>
                  {METRICS.map((m) => {
                    const va = m.get(a);
                    const vb = m.get(b);
                    let winner: Side | null = null;
                    if (va != null && vb != null && va !== vb) {
                      const aWins = m.lowerBetter ? va < vb : va > vb;
                      winner = aWins ? "A" : "B";
                    }
                    return (
                      <tr key={m.label} className="border-b border-outline-variant/50 last:border-0">
                        <td className="py-sm text-on-surface-variant">{m.label}</td>
                        <Cell value={va} fmt={m.fmt} win={winner === "A"} />
                        <Cell value={vb} fmt={m.fmt} win={winner === "B"} />
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Lakshya verdict */}
          <VerdictCard
            aName={a.company.name}
            bName={b.company.name}
            verdict={verdict}
            loading={verdictLoading}
            error={verdictError}
          />
        </>
      )}
    </div>
  );
}

function Cell({ value, fmt, win }: { value: number | null | undefined; fmt: (v: number) => string; win: boolean }) {
  return (
    <td className={`py-sm text-right tabular ${win ? "text-primary font-semibold" : "text-on-surface"}`}>
      <span className="inline-flex items-center gap-1.5 justify-end">
        {win && <span className="w-1 h-4 rounded bg-primary" />}
        {value != null ? fmt(value) : "—"}
      </span>
    </td>
  );
}

function SlotCard({
  slot,
  onPick,
  onClear,
  label,
}: {
  slot: Slot | null;
  onPick: (id: string) => void;
  onClear: () => void;
  label: string;
}) {
  if (!slot) {
    return (
      <Card className="p-lg">
        <div className="text-label-caps font-label-caps text-on-surface-variant mb-sm">{label}</div>
        <CompanySearch placeholder="Search a company…" onSelect={(c) => onPick(c.id)} />
      </Card>
    );
  }
  const q = slot.quote;
  const up = (q?.change_pct ?? 0) >= 0;
  const ticker = slot.company.ticker_nse ?? slot.company.ticker_bse ?? "";
  return (
    <Card className="p-lg">
      <div className="flex items-start justify-between gap-sm">
        <div className="min-w-0">
          <div className="text-card-title font-semibold text-on-surface truncate">{slot.company.name}</div>
          <div className="text-body-sm text-on-surface-variant truncate">
            {ticker && <>{slot.company.ticker_nse ? "NSE" : "BSE"}: {ticker} · </>}
            {slot.company.sector ?? "—"}
          </div>
        </div>
        <button onClick={onClear} className="text-on-surface-variant hover:text-on-surface shrink-0" title="Change">
          <Icon name="close" className="text-[18px]" />
        </button>
      </div>
      {q?.last_price != null && (
        <div className="flex items-baseline gap-sm mt-md">
          <span className="text-headline-lg font-semibold text-on-surface tabular">{formatINR(q.last_price)}</span>
          <span className={`text-body-md font-medium tabular ${up ? "text-positive" : "text-negative"}`}>
            {up ? "▲" : "▼"} {formatPct(Math.abs(q.change_pct ?? 0))}
          </span>
        </div>
      )}
    </Card>
  );
}

const DIMENSIONS: { key: keyof CompareResponse["comparison"]; label: string }[] = [
  { key: "growth", label: "Growth" },
  { key: "profitability", label: "Profitability" },
  { key: "risk", label: "Risk" },
  { key: "valuation", label: "Valuation" },
];

function VerdictCard({
  aName,
  bName,
  verdict,
  loading,
  error,
}: {
  aName: string;
  bName: string;
  verdict: CompareResponse | null;
  loading: boolean;
  error: string | null;
}) {
  function winnerName(w: CompareWinner): string {
    if (w === "A") return aName;
    if (w === "B") return bName;
    return "Tie";
  }
  return (
    <Card className="p-lg">
      <div className="flex items-center justify-between mb-md">
        <div className="flex items-center gap-sm">
          <Icon name="bolt" className="text-primary text-[20px]" />
          <span className="text-card-title font-semibold text-on-surface">Lakshya Verdict</span>
        </div>
        {loading && (
          <span className="flex items-center gap-1.5 text-label-caps font-label-caps text-primary">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-blink" />
            Synthesizing…
          </span>
        )}
      </div>

      {loading ? (
        <div className="space-y-sm">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-3/4" />
          <p className="text-caption text-on-surface-variant pt-xs">
            Lakshya is analysing both entities — this can take up to a minute.
          </p>
        </div>
      ) : error ? (
        <p className="text-body-sm text-on-surface-variant">{error}</p>
      ) : verdict ? (
        <div className="space-y-lg">
          {/* dimension winners */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-sm">
            {DIMENSIONS.map((d) => {
              const w = verdict.comparison[d.key];
              return (
                <div key={d.key} className="bg-bg-0 border border-outline-variant rounded-lg p-sm">
                  <div className="text-label-caps font-label-caps text-on-surface-variant">{d.label}</div>
                  <div className="text-body-sm font-medium text-on-surface truncate mt-1">
                    {winnerName(w)}
                  </div>
                </div>
              );
            })}
          </div>

          {verdict.final_verdict && (
            <div className="text-body-md text-on-surface">
              <Markdown>{verdict.final_verdict}</Markdown>
            </div>
          )}

          {verdict.insights?.length > 0 && (
            <div className="space-y-sm">
              <div className="text-label-caps font-label-caps text-on-surface-variant">Key insights</div>
              {verdict.insights.map((ins, i) => (
                <div key={i} className="flex items-start gap-sm text-body-sm text-on-surface-variant">
                  <Icon name="arrow_right" className="text-primary text-[18px] shrink-0 mt-0.5" />
                  <span>{ins}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </Card>
  );
}
