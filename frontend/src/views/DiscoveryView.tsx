import { useEffect, useMemo, useState } from "react";
import { fetchThematicScreen, type ThematicResult } from "../lib/api";
import { Card, CardHeader, Chip, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { formatINR } from "../lib/format";

const PRESET_THEMES = [
  "EV supply chain",
  "Semiconductor Fab",
  "Green Hydrogen",
  "Defense Indigenization",
  "Rural Consumption",
];

interface Props {
  onOpenCompany: (id: string) => void;
}

export function DiscoveryView({ onOpenCompany }: Props) {
  const [theme, setTheme] = useState(PRESET_THEMES[0]);
  const [draft, setDraft] = useState("");
  const [results, setResults] = useState<ThematicResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchThematicScreen(theme, 9)
      .then((r) => {
        if (!cancelled) setResults(r);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load thematic matches.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [theme]);

  function submitSearch() {
    const q = draft.trim();
    if (q) setTheme(q);
  }

  const chips = useMemo(() => {
    const preset = [...PRESET_THEMES];
    if (!preset.includes(theme)) preset.unshift(theme);
    return preset;
  }, [theme]);

  // Derive an honest theme context from the real matches.
  const context = useMemo(() => {
    if (!results.length) return null;
    const sectorCounts = new Map<string, number>();
    for (const r of results) {
      const s = r.sector ?? "Uncategorised";
      sectorCounts.set(s, (sectorCounts.get(s) ?? 0) + 1);
    }
    const sectors = [...sectorCounts.entries()].sort((a, b) => b[1] - a[1]);
    const top = results[0];
    const avg =
      results.reduce((a, r) => a + r.relevance_score, 0) / results.length;
    return { sectors, top, avg, count: results.length };
  }, [results]);

  return (
    <div className="space-y-lg">
      {/* Header */}
      <div>
        <h1 className="text-headline-lg font-semibold text-on-surface">
          Thematic Discovery
        </h1>
        <p className="text-body-sm text-on-surface-variant mt-1 max-w-2xl">
          Uncover high-conviction ideas based on semantic themes, supply-chain
          linkages, and sector exposure across the listed universe.
        </p>
      </div>

      {/* Search */}
      <div className="flex items-center bg-bg-1 border border-outline-variant rounded-lg px-md py-sm focus-within:border-primary/50 transition-colors max-w-2xl">
        <Icon name="search" className="text-on-surface-variant text-[20px] mr-sm" />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
          placeholder="Explore a theme — e.g. “data centres”, “export manufacturing”…"
          className="bg-transparent text-body-md text-on-surface focus:outline-none w-full placeholder:text-on-surface-variant"
        />
        {draft.trim() && (
          <button
            onClick={submitSearch}
            className="ml-sm text-label-caps font-label-caps text-primary hover:text-primary-fixed-dim shrink-0"
          >
            EXPLORE
          </button>
        )}
      </div>

      {/* Theme chips */}
      <div className="flex flex-wrap gap-sm">
        {chips.map((t) => {
          const active = t === theme;
          return (
            <button
              key={t}
              onClick={() => setTheme(t)}
              className={`inline-flex items-center gap-1.5 rounded-full px-md py-sm text-body-sm transition-colors border ${
                active
                  ? "bg-primary/15 border-primary/40 text-primary"
                  : "bg-bg-1 border-outline-variant text-on-surface-variant hover:text-on-surface hover:border-outline"
              }`}
            >
              {active && <Icon name="auto_awesome" className="text-[16px]" />}
              {t}
            </button>
          );
        })}
      </div>

      {/* Body: context + results grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* Theme context */}
        <div className="lg:col-span-4 space-y-lg">
          <Card>
            <CardHeader title="Theme Context" icon="insights" />
            <div className="px-lg pb-lg">
            {loading ? (
              <div className="space-y-sm">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : context ? (
              <div className="space-y-md">
                <p className="text-body-sm text-on-surface-variant leading-relaxed">
                  <span className="text-on-surface font-medium">
                    {context.count} companies
                  </span>{" "}
                  surface for{" "}
                  <span className="text-on-surface">“{theme}”</span>. Strongest
                  exposure is{" "}
                  <span className="text-on-surface font-medium">
                    {context.top.company_name}
                  </span>
                  {context.top.sector ? ` (${context.top.sector})` : ""}.
                </p>
                <div>
                  <div className="text-label-caps font-label-caps text-on-surface-variant mb-sm">
                    Sector spread
                  </div>
                  <div className="space-y-xs">
                    {context.sectors.slice(0, 5).map(([sector, n]) => (
                      <div
                        key={sector}
                        className="flex items-center justify-between text-body-sm"
                      >
                        <span className="text-on-surface-variant truncate pr-sm">
                          {sector}
                        </span>
                        <span className="tabular text-on-surface shrink-0">
                          {n}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex flex-wrap gap-sm pt-xs">
                  <Chip tone="positive">
                    <Icon name="trending_up" className="text-[14px] mr-1" />
                    {Math.round(context.avg * 100)}% avg match
                  </Chip>
                  {context.sectors.length > 3 && (
                    <Chip tone="warning">
                      <Icon name="hub" className="text-[14px] mr-1" />
                      Broad-based
                    </Chip>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-body-sm text-on-surface-variant">
                No strong matches for this theme yet.
              </p>
            )}
            </div>
          </Card>
        </div>

        {/* Results grid */}
        <div className="lg:col-span-8">
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="p-md">
                  <Skeleton className="h-5 w-2/3 mb-sm" />
                  <Skeleton className="h-4 w-1/2 mb-md" />
                  <Skeleton className="h-4 w-full" />
                </Card>
              ))}
            </div>
          ) : error ? (
            <Card className="text-body-sm text-negative p-lg">{error}</Card>
          ) : results.length === 0 ? (
            <Card className="text-center py-2xl px-lg">
              <Icon
                name="search_off"
                className="text-on-surface-variant text-[32px] mb-sm"
              />
              <p className="text-body-sm text-on-surface-variant">
                No companies matched “{theme}”. Try a broader theme.
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md">
              {results.map((r) => (
                <MatchCard
                  key={r.company_id}
                  r={r}
                  onClick={() => onOpenCompany(r.company_id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MatchCard({
  r,
  onClick,
}: {
  r: ThematicResult;
  onClick: () => void;
}) {
  const ticker = r.ticker_nse ?? r.ticker_bse ?? "";
  const pct = Math.round(r.relevance_score * 100);
  const tags = [r.sector, r.industry].filter(Boolean) as string[];
  return (
    <button
      onClick={onClick}
      className="group text-left bg-bg-1 border border-outline-variant rounded-lg p-md hover:border-primary/40 hover:bg-bg-2 transition-colors flex flex-col gap-md"
    >
      <div className="flex items-start justify-between gap-sm">
        <div className="min-w-0">
          <div className="text-card-title font-semibold text-on-surface truncate">
            {ticker || r.company_name}
          </div>
          <div className="text-body-sm text-on-surface-variant truncate">
            {r.company_name}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-card-title font-semibold text-primary tabular">
            {pct}%
          </div>
          <div className="text-label-caps font-label-caps text-on-surface-variant">
            MATCH
          </div>
        </div>
      </div>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-xs">
          {tags.slice(0, 2).map((t) => (
            <Chip key={t} tone="tag">
              {t}
            </Chip>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-xs border-t border-outline-variant/60">
        <span className="text-body-sm text-on-surface-variant">
          {r.market_cap_inr
            ? formatINR(r.market_cap_inr, { compact: true })
            : "—"}
        </span>
        <Icon
          name="arrow_forward"
          className="text-on-surface-variant text-[18px] group-hover:text-primary group-hover:translate-x-0.5 transition-all"
        />
      </div>
    </button>
  );
}
