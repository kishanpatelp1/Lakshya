import { useCallback, useEffect, useState } from "react";
import {
  fetchSimStats,
  fetchSimPositions,
  fetchSimHistory,
  executeSimTrade,
  topupBalance,
  type SimStats,
  type SimPosition,
  type SimClosedTrade,
  type SimTradeResult,
  type AICompany,
} from "../lib/api";
import { Card, CardHeader, StatTile, Skeleton } from "../components/ui";
import { Icon } from "../components/Icon";
import { CompanySearch } from "../components/CompanySearch";
import { formatINR, formatSignedINR, formatPct } from "../lib/format";
import { getUserId } from "../lib/user";

export function SimulatorView() {
  const userId = getUserId();
  const [stats, setStats] = useState<SimStats | null>(null);
  const [positions, setPositions] = useState<SimPosition[]>([]);
  const [history, setHistory] = useState<SimClosedTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<{ ok: boolean; msg: string } | null>(null);

  const load = useCallback(async () => {
    const [s, p, h] = await Promise.allSettled([
      fetchSimStats(userId),
      fetchSimPositions(userId),
      fetchSimHistory(userId),
    ]);
    if (s.status === "fulfilled") setStats(s.value);
    if (p.status === "fulfilled") setPositions(p.value.positions);
    if (h.status === "fulfilled") setHistory(h.value.trades);
    setLoading(false);
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  function showFlash(ok: boolean, msg: string) {
    setFlash({ ok, msg });
    setTimeout(() => setFlash(null), 4000);
  }

  async function onSell(pos: SimPosition) {
    try {
      const r = await executeSimTrade(userId, pos.company_id, "sell", pos.quantity);
      const pnl = r.pnl ?? 0;
      showFlash(pnl >= 0, `Sold ${r.quantity} ${r.ticker ?? r.company_name} · P&L ${formatSignedINR(pnl)}`);
      load();
    } catch {
      showFlash(false, "Sell failed. Try again.");
    }
  }

  async function onTopup() {
    try {
      await topupBalance(userId, 100000);
      showFlash(true, "Added ₹1,00,000 to your simulation balance.");
      load();
    } catch {
      showFlash(false, "Top-up failed.");
    }
  }

  const portfolioValue = positions.reduce(
    (sum, p) => sum + (p.current_price ?? p.entry_price) * p.quantity,
    0
  );

  return (
    <div className="space-y-lg">
      <div className="flex items-center justify-between gap-md">
        <div>
          <h1 className="text-headline-lg font-semibold text-on-surface">Trading Simulator</h1>
          <p className="text-body-sm text-on-surface-variant mt-1">
            Practise with ₹ paper money at live market prices — zero risk.
          </p>
        </div>
        <button
          onClick={onTopup}
          className="inline-flex items-center gap-sm h-10 px-md rounded-lg border border-outline-variant text-on-surface font-medium text-body-sm hover:bg-bg-1 transition shrink-0"
        >
          <Icon name="add_card" className="text-[18px]" />
          <span className="hidden sm:inline">Top up</span>
        </button>
      </div>

      {flash && (
        <div
          className={`flex items-center gap-sm rounded-lg px-md py-sm text-body-sm border ${
            flash.ok
              ? "bg-positive/10 border-positive/30 text-positive"
              : "bg-negative/10 border-negative/30 text-negative"
          }`}
        >
          <Icon name={flash.ok ? "check_circle" : "error"} className="text-[18px]" />
          {flash.msg}
        </div>
      )}

      {/* Stat tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-md">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-lg">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-7 w-24 mt-sm" />
            </Card>
          ))
        ) : (
          <>
            <StatTile label="Cash Balance" value={formatINR(stats.balance)} icon="account_balance_wallet" />
            <StatTile label="Open Value" value={formatINR(portfolioValue)} icon="donut_small" />
            <StatTile
              label="Realised P&L"
              value={formatSignedINR(stats.total_pnl)}
              valueClass={stats.total_pnl >= 0 ? "text-positive" : "text-negative"}
              icon="trending_up"
            />
            <StatTile
              label="Win Rate"
              value={`${Math.round(stats.win_rate_pct)}%`}
              sub={`${stats.winning_trades}/${stats.total_trades} trades`}
              icon="military_tech"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* Main */}
        <div className="lg:col-span-8 space-y-lg">
          <TradePanel userId={userId} onDone={(r) => { showFlash(true, `Bought ${r.quantity} ${r.ticker ?? r.company_name} @ ${formatINR(r.price)} · +${r.xp_earned} XP`); load(); }} onError={() => showFlash(false, "Trade failed — check your balance.")} />

          {/* Open positions */}
          <Card>
            <CardHeader title="Open Positions" icon="candlestick_chart" />
            <div className="px-lg pb-lg">
              {loading ? (
                <Skeleton className="h-24 w-full" />
              ) : positions.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant py-md">
                  No open positions. Buy a stock above to get started.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-body-sm min-w-[620px]">
                    <thead>
                      <tr className="text-label-caps font-label-caps text-on-surface-variant border-b border-outline-variant">
                        <th className="text-left font-normal py-sm">Stock</th>
                        <th className="text-right font-normal py-sm">Qty</th>
                        <th className="text-right font-normal py-sm">Entry</th>
                        <th className="text-right font-normal py-sm">Current</th>
                        <th className="text-right font-normal py-sm">P&L</th>
                        <th className="py-sm" />
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p) => {
                        const up = (p.unrealised_pnl ?? 0) >= 0;
                        return (
                          <tr key={p.trade_id} className="border-b border-outline-variant/50 last:border-0">
                            <td className="py-md">
                              <div className="text-on-surface font-medium">{p.ticker ?? p.company_name}</div>
                              <div className="text-caption text-on-surface-variant truncate max-w-[160px]">{p.company_name}</div>
                            </td>
                            <td className="py-md text-right tabular text-on-surface">{p.quantity}</td>
                            <td className="py-md text-right tabular text-on-surface-variant">{formatINR(p.entry_price)}</td>
                            <td className="py-md text-right tabular text-on-surface">
                              {p.current_price != null ? formatINR(p.current_price) : "—"}
                            </td>
                            <td className={`py-md text-right tabular ${up ? "text-positive" : "text-negative"}`}>
                              {p.unrealised_pnl != null ? formatSignedINR(p.unrealised_pnl) : "—"}
                              {p.return_pct != null && (
                                <div className="text-caption">{up ? "+" : ""}{formatPct(p.return_pct)}</div>
                              )}
                            </td>
                            <td className="py-md text-right">
                              <button
                                onClick={() => onSell(p)}
                                className="h-8 px-md rounded-md border border-outline-variant text-on-surface text-caption font-medium hover:border-negative hover:text-negative transition-colors"
                              >
                                Sell
                              </button>
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

          {/* History */}
          <Card>
            <CardHeader title="Trade History" icon="history" />
            <div className="px-lg pb-lg">
              {loading ? (
                <Skeleton className="h-16 w-full" />
              ) : history.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant py-md">No closed trades yet.</p>
              ) : (
                <div className="divide-y divide-outline-variant/50">
                  {history.slice(0, 12).map((t) => {
                    const isSell = t.trade_type === "sell";
                    const pnl = t.pnl ?? 0;
                    return (
                      <div key={t.trade_id} className="flex items-center justify-between py-sm gap-md">
                        <div className="flex items-center gap-sm min-w-0">
                          <span
                            className={`text-label-caps font-label-caps px-sm py-[2px] rounded ${
                              isSell ? "bg-negative/15 text-negative" : "bg-positive/15 text-positive"
                            }`}
                          >
                            {t.trade_type}
                          </span>
                          <span className="text-body-sm text-on-surface truncate">
                            {t.quantity} {t.ticker ?? t.company_name}
                          </span>
                        </div>
                        <div className="flex items-center gap-lg shrink-0 text-body-sm">
                          <span className="tabular text-on-surface-variant">{formatINR(t.total_value)}</span>
                          {isSell && (
                            <span className={`tabular ${pnl >= 0 ? "text-positive" : "text-negative"}`}>
                              {formatSignedINR(pnl)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-4 space-y-lg">
          {stats && <LevelCard stats={stats} />}
          {stats?.daily_challenge?.text && (
            <Card>
              <CardHeader title="Daily Challenge" icon="flag" />
              <div className="px-lg pb-lg">
                <p className="text-body-sm text-on-surface">{stats.daily_challenge.text}</p>
                <div className={`mt-sm inline-flex items-center gap-1 text-caption ${stats.daily_challenge.done ? "text-positive" : "text-on-surface-variant"}`}>
                  <Icon name={stats.daily_challenge.done ? "check_circle" : "radio_button_unchecked"} className="text-[14px]" />
                  {stats.daily_challenge.done ? "Completed" : "In progress"}
                </div>
              </div>
            </Card>
          )}
          {stats && (
            <Card>
              <CardHeader title="Badges" icon="workspace_premium" />
              <div className="px-lg pb-lg grid grid-cols-2 gap-sm">
                {stats.badges.map((b) => (
                  <div
                    key={b.id}
                    className={`flex items-center gap-sm rounded-lg border p-sm ${
                      b.earned
                        ? "border-primary/40 bg-primary/10 text-on-surface"
                        : "border-outline-variant bg-bg-0 text-on-surface-variant opacity-60"
                    }`}
                  >
                    <Icon name={b.earned ? "military_tech" : "lock"} className={`text-[18px] ${b.earned ? "text-primary" : ""}`} />
                    <span className="text-caption truncate">{b.name}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function LevelCard({ stats }: { stats: SimStats }) {
  const lvl = stats.level;
  return (
    <Card className="p-lg">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-label-caps font-label-caps text-on-surface-variant">Level {lvl.level}</div>
          <div className="text-card-title font-semibold text-on-surface">{lvl.level_name}</div>
        </div>
        <div className="w-11 h-11 rounded-full bg-primary/15 text-primary flex items-center justify-center font-semibold tabular">
          {lvl.level}
        </div>
      </div>
      <div className="mt-md">
        <div className="h-2 rounded-full bg-bg-2 overflow-hidden">
          <div className="h-full bg-primary transition-all" style={{ width: `${Math.min(100, lvl.progress_pct)}%` }} />
        </div>
        <div className="flex items-center justify-between text-caption text-on-surface-variant mt-1 tabular">
          <span>{lvl.xp} XP</span>
          <span>{lvl.next_level_xp} XP</span>
        </div>
      </div>
      <div className="flex items-center gap-lg mt-md pt-md border-t border-outline-variant/50 text-caption text-on-surface-variant">
        <span>Streak <span className="text-on-surface tabular">{stats.current_streak}</span></span>
        <span>Best <span className="text-on-surface tabular">{stats.best_streak}</span></span>
      </div>
    </Card>
  );
}

function TradePanel({
  userId,
  onDone,
  onError,
}: {
  userId: string;
  onDone: (r: SimTradeResult) => void;
  onError: () => void;
}) {
  const [company, setCompany] = useState<AICompany | null>(null);
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);

  async function buy() {
    const q = parseInt(qty, 10);
    if (!company || !q || q < 1) return;
    setBusy(true);
    try {
      const r = await executeSimTrade(userId, company.id, "buy", q);
      onDone(r);
      setCompany(null);
      setQty("");
    } catch {
      onError();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Place a Trade" icon="add_shopping_cart" />
      <div className="px-lg pb-lg space-y-md">
        {company ? (
          <div className="flex items-center justify-between bg-bg-0 border border-outline-variant rounded-lg px-md h-11">
            <span className="text-body-sm text-on-surface truncate">
              {company.name}{" "}
              <span className="text-on-surface-variant">
                {company.ticker_nse ?? company.ticker_bse ?? ""}
              </span>
            </span>
            <button onClick={() => setCompany(null)} className="text-on-surface-variant hover:text-on-surface">
              <Icon name="close" className="text-[18px]" />
            </button>
          </div>
        ) : (
          <CompanySearch placeholder="Search a stock to buy…" onSelect={setCompany} />
        )}

        <div className="flex items-center gap-md">
          <input
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="Quantity"
            className="w-32 bg-bg-0 border border-outline-variant rounded-lg px-md h-11 text-body-md text-on-surface tabular focus:outline-none focus:border-primary/60 placeholder:text-on-surface-variant"
          />
          <button
            onClick={buy}
            disabled={!company || !qty || busy}
            className="flex-1 h-11 rounded-lg bg-primary text-on-primary font-semibold text-body-md hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {busy ? "Placing…" : "Buy at market price"}
          </button>
        </div>
        <p className="text-caption text-on-surface-variant">
          Executes at the current live price. Sell open positions below to realise P&L.
        </p>
      </div>
    </Card>
  );
}
