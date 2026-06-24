import { useCallback, useEffect, useState } from "react";
import {
  fetchWatchlists,
  createWatchlist,
  addWatchlistCompany,
  removeWatchlistCompany,
  fetchCompanyDetail,
  fetchCompanyQuote,
  type Watchlist,
  type AICompany,
  type AIQuote,
} from "../lib/api";
import { Card, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { CompanySearch } from "../components/CompanySearch";
import { formatINR, formatPct } from "../lib/format";
import { getUserId } from "../lib/user";

interface Row {
  company: AICompany;
  quote: AIQuote | null;
}

interface Props {
  onOpenCompany: (id: string) => void;
}

export function WatchlistView({ onOpenCompany }: Props) {
  const userId = getUserId();
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [loadingLists, setLoadingLists] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [adding, setAdding] = useState(false);

  const loadLists = useCallback(async () => {
    setLoadingLists(true);
    try {
      let ls = await fetchWatchlists(userId);
      if (ls.length === 0) {
        await createWatchlist(userId, "My Watchlist");
        ls = await fetchWatchlists(userId);
      }
      setLists(ls);
      setActiveId((prev) => prev && ls.some((l) => l.id === prev) ? prev : ls[0]?.id ?? null);
    } catch {
      setLists([]);
    } finally {
      setLoadingLists(false);
    }
  }, [userId]);

  useEffect(() => {
    loadLists();
  }, [loadLists]);

  const active = lists.find((l) => l.id === activeId) ?? null;

  // Resolve company ids → detail + quote for the active list.
  useEffect(() => {
    if (!active) {
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoadingRows(true);
    Promise.all(
      active.companies.map(async (cid) => {
        const [company, quote] = await Promise.all([
          fetchCompanyDetail(cid).catch(() => null),
          fetchCompanyQuote(cid).catch(() => null),
        ]);
        return company ? ({ company, quote } as Row) : null;
      })
    )
      .then((res) => {
        if (!cancelled) setRows(res.filter((r): r is Row => r !== null));
      })
      .finally(() => {
        if (!cancelled) setLoadingRows(false);
      });
    return () => {
      cancelled = true;
    };
  }, [active?.id, active?.companies.join(",")]);

  async function onAdd(company: AICompany) {
    if (!active) return;
    setAdding(false);
    try {
      await addWatchlistCompany(active.id, company.id);
      await loadLists();
    } catch {
      /* ignore */
    }
  }

  async function onRemove(companyId: string) {
    if (!active) return;
    // optimistic
    setRows((rs) => rs.filter((r) => r.company.id !== companyId));
    try {
      await removeWatchlistCompany(active.id, companyId);
      await loadLists();
    } catch {
      loadLists();
    }
  }

  async function onNewList() {
    const name = window.prompt("Name your new watchlist");
    if (!name?.trim()) return;
    const wl = await createWatchlist(userId, name.trim());
    await loadLists();
    setActiveId(wl.id);
  }

  return (
    <div className="space-y-lg">
      {/* Header */}
      <div className="flex items-center justify-between gap-md">
        <h1 className="text-headline-lg font-semibold text-on-surface">Watchlists</h1>
        {active && (
          <button
            onClick={() => setAdding((s) => !s)}
            className="inline-flex items-center gap-sm h-10 px-md rounded-lg bg-primary text-on-primary font-medium text-body-sm hover:brightness-95 transition shrink-0"
          >
            <Icon name="add" className="text-[18px]" />
            <span className="hidden sm:inline">Add Company</span>
          </button>
        )}
      </div>

      {/* Tabs */}
      {loadingLists ? (
        <Skeleton className="h-8 w-64" />
      ) : (
        <div className="flex items-center gap-lg border-b border-outline-variant overflow-x-auto no-scrollbar">
          {lists.map((l) => (
            <button
              key={l.id}
              onClick={() => setActiveId(l.id)}
              className={`pb-sm -mb-px border-b-2 text-body-sm whitespace-nowrap transition-colors ${
                l.id === activeId
                  ? "border-primary text-primary font-medium"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {l.name}{" "}
              <span className="text-on-surface-variant">({l.companies.length})</span>
            </button>
          ))}
          <button
            onClick={onNewList}
            className="pb-sm text-body-sm text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 whitespace-nowrap"
          >
            <Icon name="add_circle" className="text-[16px]" /> New List
          </button>
        </div>
      )}

      {/* Add company inline */}
      {adding && active && (
        <Card className="p-md">
          <CompanySearch placeholder="Search a company to add…" onSelect={onAdd} />
        </Card>
      )}

      {/* Table */}
      <Card>
        {loadingRows ? (
          <div className="p-lg space-y-sm">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !active || rows.length === 0 ? (
          <div className="text-center py-2xl px-lg">
            <Icon name="visibility" className="text-on-surface-variant text-[32px] mb-sm" />
            <p className="text-body-sm text-on-surface-variant">
              This watchlist is empty. Use <span className="text-on-surface">Add Company</span> to track a stock.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-body-sm min-w-[640px]">
              <thead>
                <tr className="text-label-caps font-label-caps text-on-surface-variant border-b border-outline-variant">
                  <th className="text-left font-normal px-lg py-md">Company</th>
                  <th className="text-right font-normal px-md py-md">Price</th>
                  <th className="text-right font-normal px-md py-md">Change</th>
                  <th className="text-left font-normal px-md py-md">Sector</th>
                  <th className="px-lg py-md" />
                </tr>
              </thead>
              <tbody>
                {rows.map(({ company, quote }) => {
                  const ticker = company.ticker_nse ?? company.ticker_bse ?? "";
                  const up = (quote?.change_pct ?? 0) >= 0;
                  return (
                    <tr
                      key={company.id}
                      className="border-b border-outline-variant/50 last:border-0 hover:bg-bg-2/50 transition-colors group"
                    >
                      <td className="px-lg py-md">
                        <button
                          onClick={() => onOpenCompany(company.id)}
                          className="flex items-center gap-md text-left"
                        >
                          <div className="w-9 h-9 rounded-md bg-bg-2 flex items-center justify-center text-label-caps font-label-caps text-on-surface-variant shrink-0">
                            {(ticker || company.name).slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="text-on-surface font-medium truncate">
                              {ticker || company.name}
                            </div>
                            <div className="text-caption text-on-surface-variant truncate">
                              {company.name}
                            </div>
                          </div>
                        </button>
                      </td>
                      <td className="px-md py-md text-right tabular text-on-surface">
                        {quote?.last_price != null ? formatINR(quote.last_price) : "—"}
                      </td>
                      <td className="px-md py-md text-right tabular">
                        {quote?.change_pct != null ? (
                          <span className={up ? "text-positive" : "text-negative"}>
                            {up ? "▲" : "▼"} {formatPct(Math.abs(quote.change_pct))}
                          </span>
                        ) : (
                          <span className="text-on-surface-variant">—</span>
                        )}
                      </td>
                      <td className="px-md py-md text-on-surface-variant truncate max-w-[180px]">
                        {company.sector ?? "—"}
                      </td>
                      <td className="px-lg py-md text-right">
                        <button
                          onClick={() => onRemove(company.id)}
                          title="Remove"
                          className="text-on-surface-variant hover:text-negative opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Icon name="close" className="text-[18px]" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
