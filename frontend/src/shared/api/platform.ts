import {
  type AICompany,
  type AICompanyListResponse,
  type AIFinancials,
  type AIHistoricalPrices,
  type AIHolding,
  type AIPortfolio,
  type AIPortfolioDetail,
  type AIRatios,
  type AIQuote,
  type AppProfile,
  type ChatQueryRequest,
  type ChatQueryResponse,
  type ChatSessionItem,
  type CompareRequest,
  type CompareResponse,
  type PortfolioMetrics,
  type ThematicResult,
  type TimelineEvent,
  type UserTransaction,
  type CausalMarketData,
  type CausalChainItem,
  type CausalCompanyData,
  type CausalLLMData,
  type Watchlist,
} from "../types/api";
import { AI_BACKEND_URL, aiDelete, aiGet, aiPost, ApiError, getSse, postSse } from "./core";

// ------------------------------------------------------------------ //
//  Profile persistence API                                             //
// ------------------------------------------------------------------ //

export async function listProfiles(): Promise<AppProfile[]> {
  return aiGet<AppProfile[]>("/profiles/");
}

export async function createProfile(
  name: string,
  avatarColor?: string
): Promise<AppProfile> {
  return aiPost<AppProfile>("/profiles/", {
    name,
    avatar_color: avatarColor,
  });
}

export async function fetchThematicScreen(
  query: string,
  limit = 15
): Promise<ThematicResult[]> {
  const params = new URLSearchParams();
  params.set("q", query);
  params.set("limit", String(limit));
  return aiGet<ThematicResult[]>(`/screens/thematic?${params.toString()}`);
}

export async function fetchPortfolioMetrics(
  portfolioId: string
): Promise<PortfolioMetrics> {
  return aiGet<PortfolioMetrics>(`/portfolios/${portfolioId}/metrics`);
}

/** Stream AI portfolio suggestions over SSE (stage/token/done/error). */
export async function streamPortfolioSuggestions(
  userId: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await getSse(
    `/portfolios/suggestions/stream?user_id=${userId}`,
    (evt) => {
      if (evt.event === "stage") {
        handlers.onStage?.(String(evt.data.stage ?? ""), String(evt.data.detail ?? ""));
      } else if (evt.event === "token") {
        handlers.onToken?.(String(evt.data.text ?? ""));
      } else if (evt.event === "done") {
        handlers.onDone?.(evt.data as { session_id: string; sources?: Record<string, unknown>[] });
      } else if (evt.event === "error") {
        handlers.onError?.(String(evt.data.detail ?? "stream error"));
      }
    },
    signal,
  );
}



export async function sendChatQuery(req: ChatQueryRequest): Promise<ChatQueryResponse> {
  return aiPost<ChatQueryResponse>("/chat/query", req, 300000);
}

export interface ChatStreamHandlers {
  onStage?: (stage: string, detail: string, tasks?: string[]) => void;
  onToken?: (text: string) => void;
  onDone?: (data: { session_id: string; sources?: Record<string, unknown>[] }) => void;
  onError?: (detail: string) => void;
}

/** Stream a chat query over SSE, surfacing stage / token / done / error events. */
export async function streamChatQuery(
  req: ChatQueryRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await postSse(
    "/chat/query/stream",
    req,
    (evt) => {
      if (evt.event === "stage") {
        handlers.onStage?.(
          String(evt.data.stage ?? ""),
          String(evt.data.detail ?? ""),
          evt.data.tasks as string[] | undefined,
        );
      } else if (evt.event === "token") {
        handlers.onToken?.(String(evt.data.text ?? ""));
      } else if (evt.event === "done") {
        handlers.onDone?.(evt.data as { session_id: string; sources?: Record<string, unknown>[] });
      } else if (evt.event === "error") {
        handlers.onError?.(String(evt.data.detail ?? "stream error"));
      }
    },
    signal,
  );
}

export async function listChatSessions(userId: string): Promise<ChatSessionItem[]> {
  return aiGet<ChatSessionItem[]>(`/chat/sessions/${userId}`);
}

export async function fetchCompanies(
  limit = 50,
  offset = 0,
  search?: string,
  sector?: string
): Promise<AICompanyListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (search) params.set("search", search);
  if (sector) params.set("sector", sector);
  return aiGet<AICompanyListResponse>(`/companies/?${params.toString()}`);
}

export async function fetchCompanyDetail(id: string): Promise<AICompany> {
  return aiGet<AICompany>(`/companies/${id}`);
}

export async function fetchCompanyFinancials(id: string, periods = 4): Promise<AIFinancials> {
  return aiGet<AIFinancials>(`/companies/${id}/financials?periods=${periods}`);
}

export async function fetchCompanyRatios(id: string): Promise<AIRatios> {
  return aiGet<AIRatios>(`/companies/${id}/ratios`);
}

export async function fetchCompanyQuote(id: string): Promise<AIQuote> {
  return aiGet<AIQuote>(`/companies/${id}/quote`);
}

export async function fetchHistoricalPrices(id: string, days = 30): Promise<AIHistoricalPrices> {
  return aiGet<AIHistoricalPrices>(`/companies/${id}/historical-prices?days=${days}`);
}

export async function enrichCompany(
  id: string
): Promise<{ company_id: string; enriched: boolean; updated_fields?: string[]; source?: string }> {
  return aiPost(`/companies/${id}/enrich`, {});
}

export async function searchCompaniesDB(
  query: string,
  limit = 20
): Promise<AICompany[]> {
  const params = new URLSearchParams();
  params.set("q", query);
  params.set("limit", String(limit));
  return aiGet<AICompany[]>(`/companies/search?${params.toString()}`);
}

export async function fetchPortfolios(userId: string): Promise<AIPortfolio[]> {
  return aiGet<AIPortfolio[]>(`/portfolios/?user_id=${userId}`);
}

export async function createPortfolio(userId: string, name: string): Promise<AIPortfolio> {
  return aiPost<AIPortfolio>("/portfolios/", { user_id: userId, name });
}

export async function fetchPortfolioDetail(id: string): Promise<AIPortfolioDetail> {
  return aiGet<AIPortfolioDetail>(`/portfolios/${id}`);
}

export async function addHolding(
  portfolioId: string,
  companyId: string,
  quantity: number,
  averagePrice?: number
): Promise<AIHolding> {
  return aiPost<AIHolding>(`/portfolios/${portfolioId}/holdings`, {
    company_id: companyId,
    quantity,
    average_price: averagePrice,
  });
}

export async function deletePortfolio(portfolioId: string, userId: string): Promise<void> {
  return aiDelete(`/portfolios/${portfolioId}?user_id=${userId}`);
}

export async function deleteHolding(portfolioId: string, holdingId: string): Promise<void> {
  return aiDelete(`/portfolios/${portfolioId}/holdings/${holdingId}`);
}

export async function topupBalance(
  userId: string,
  amount: number
): Promise<{ simulation_balance: number }> {
  return aiPost<{ simulation_balance: number }>(`/users/${userId}/balance/topup`, { amount });
}

export async function fetchTransactions(
  userId: string,
  limit = 50
): Promise<UserTransaction[]> {
  return aiGet<UserTransaction[]>(`/users/${userId}/transactions?limit=${limit}`);
}

export async function compareCompanies(req: CompareRequest): Promise<CompareResponse> {
  return aiPost<CompareResponse>("/compare/", req, 300000);
}

export async function fetchTimeline(
  userId?: string,
  companyId?: string,
  limit = 20
): Promise<TimelineEvent[]> {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  if (companyId) params.set("company_id", companyId);
  params.set("limit", String(limit));
  return aiGet<TimelineEvent[]>(`/timeline/?${params.toString()}`);
}

export async function uploadDocument(
  userId: string,
  file: File,
  sessionId?: string
): Promise<{ upload_id: string; filename: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  if (sessionId) formData.append("session_id", sessionId);

  const response = await fetch(`${AI_BACKEND_URL}/chat/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(`Upload failed with status ${response.status}`, response.status);
  }

  return response.json();
}

// ── Causal / Domino Effect API ────────────────────────────────────────────

export async function fetchCausalMarket(): Promise<CausalMarketData> {
  return aiGet<CausalMarketData>("/causal/market");
}

export async function fetchCausalPortfolioCompanies(userId: string): Promise<{ companies: CausalCompanyData[]; chains?: CausalChainItem[]; last_refreshed_at?: string | null }> {
  return aiGet(`/causal/portfolio/companies?user_id=${userId}`);
}

export async function fetchCausalCompany(companyId: string): Promise<CausalCompanyData> {
  return aiGet<CausalCompanyData>(`/causal/company/${companyId}`);
}

export async function analyzeCausalTrigger(trigger: string, companyId?: string): Promise<CausalLLMData> {
  return aiPost<CausalLLMData>("/causal/llm-analyze", { trigger, company_id: companyId ?? null }, 300000);
}

// ------------------------------------------------------------------ //
//  Watchlists                                                          //
// ------------------------------------------------------------------ //

export async function fetchWatchlists(userId: string): Promise<Watchlist[]> {
  return aiGet<Watchlist[]>(`/watchlists/?user_id=${userId}`);
}

export async function createWatchlist(userId: string, name: string): Promise<Watchlist> {
  return aiPost<Watchlist>("/watchlists/", { user_id: userId, name });
}

export async function addWatchlistCompany(
  watchlistId: string,
  companyId: string
): Promise<{ status: string }> {
  return aiPost<{ status: string }>(`/watchlists/${watchlistId}/companies`, {
    company_id: companyId,
  });
}

export async function removeWatchlistCompany(
  watchlistId: string,
  companyId: string
): Promise<void> {
  return aiDelete(`/watchlists/${watchlistId}/companies/${companyId}`);
}

// ------------------------------------------------------------------ //
//  Company filings (by id)                                             //
// ------------------------------------------------------------------ //

export interface CompanyFiling {
  id: string;
  filing_type: string;
  title: string;
  filing_date: string;
  source_url?: string | null;
  status?: string;
  period_start?: string | null;
  period_end?: string | null;
}

export async function fetchCompanyFilings(
  companyId: string,
  limit = 25,
  filingType?: string
): Promise<CompanyFiling[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (filingType) params.set("filing_type", filingType);
  return aiGet<CompanyFiling[]>(`/companies/${companyId}/filings?${params.toString()}`);
}

// ------------------------------------------------------------------ //
//  Simulator (paper trading)                                           //
// ------------------------------------------------------------------ //

export interface SimTradeResult {
  trade_type: string;
  company_name: string;
  ticker?: string | null;
  quantity: number;
  price: number;
  total_value: number;
  balance_after: number;
  xp_earned: number;
  badges_earned: string[];
  pnl?: number;
}

export interface SimPosition {
  trade_id: string;
  company_id: string;
  company_name: string;
  ticker?: string | null;
  quantity: number;
  entry_price: number;
  current_price?: number | null;
  total_invested: number;
  unrealised_pnl?: number | null;
  return_pct?: number | null;
}

export interface SimClosedTrade {
  trade_id: string;
  company_name: string;
  ticker?: string | null;
  trade_type: string;
  quantity: number;
  entry_price: number;
  total_value: number;
  pnl?: number | null;
  opened_at: string;
  closed_at?: string | null;
}

export interface SimLevel {
  level: number;
  level_name: string;
  xp: number;
  next_level_xp: number;
  progress_pct: number;
}

export interface SimBadge {
  id: string;
  name: string;
  earned: boolean;
}

export interface SimDailyChallenge {
  id?: string;
  text?: string;
  sector?: string;
  done?: boolean;
}

export interface SimStats {
  balance: number;
  total_pnl: number;
  total_trades: number;
  winning_trades: number;
  win_rate_pct: number;
  best_trade_pnl: number;
  worst_trade_pnl: number;
  xp: number;
  level: SimLevel;
  badges: SimBadge[];
  current_streak: number;
  best_streak: number;
  daily_challenge: SimDailyChallenge;
}

export async function executeSimTrade(
  userId: string,
  companyId: string,
  tradeType: "buy" | "sell",
  quantity: number
): Promise<SimTradeResult> {
  return aiPost<SimTradeResult>("/simulator/trade", {
    user_id: userId,
    company_id: companyId,
    trade_type: tradeType,
    quantity,
  });
}

export async function fetchSimPositions(userId: string): Promise<{ positions: SimPosition[] }> {
  return aiGet<{ positions: SimPosition[] }>(`/simulator/positions?user_id=${userId}`);
}

export async function fetchSimHistory(userId: string): Promise<{ trades: SimClosedTrade[] }> {
  return aiGet<{ trades: SimClosedTrade[] }>(`/simulator/history?user_id=${userId}`);
}

export async function fetchSimStats(userId: string): Promise<SimStats> {
  return aiGet<SimStats>(`/simulator/stats?user_id=${userId}`);
}

// ------------------------------------------------------------------ //
//  Document insights                                                   //
// ------------------------------------------------------------------ //

export interface Insight {
  id: string;
  company_id: string;
  company_name?: string | null;
  ticker?: string | null;
  sector?: string | null;
  insight_type: string;
  title: string;
  detail?: string | null;
  plain_summary?: string | null;
  severity: string;
  source_quote?: string | null;
  period?: string | null;
  doc_type?: string | null;
  filing_id?: string | null;
  filing_title?: string | null;
  created_at?: string | null;
}

export interface CompanyInsights {
  company_id: string;
  company_name?: string | null;
  digest: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
  };
  insights: Insight[];
}

export async function fetchInsightsFeed(opts?: {
  insight_type?: string;
  severity?: string;
  sector?: string;
  limit?: number;
}): Promise<Insight[]> {
  const p = new URLSearchParams();
  if (opts?.insight_type) p.set("insight_type", opts.insight_type);
  if (opts?.severity) p.set("severity", opts.severity);
  if (opts?.sector) p.set("sector", opts.sector);
  p.set("limit", String(opts?.limit ?? 60));
  return aiGet<Insight[]>(`/insights/feed?${p.toString()}`);
}

export async function fetchCompanyInsights(
  companyId: string,
  limit = 50
): Promise<CompanyInsights> {
  return aiGet<CompanyInsights>(`/insights/company/${companyId}?limit=${limit}`);
}

// ------------------------------------------------------------------ //
//  Chat message history                                                //
// ------------------------------------------------------------------ //

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
}

export async function fetchSessionMessages(
  sessionId: string,
  userId: string,
  limit = 100
): Promise<ChatMessageItem[]> {
  return aiGet<ChatMessageItem[]>(
    `/chat/session/${sessionId}/messages?user_id=${userId}&limit=${limit}`
  );
}
