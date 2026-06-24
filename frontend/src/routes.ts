export type ViewKey =
  | "dashboard"
  | "lakshya"
  | "discovery"
  | "company"
  | "compare"
  | "portfolio"
  | "watchlist"
  | "domino"
  | "insights"
  | "filings"
  | "news"
  | "simulator"
  | "profile"
  | "settings";

export interface NavItem {
  key: ViewKey;
  label: string;
  icon: string; // Material Symbols name
  group: "main" | "research" | "tools" | "footer";
}

export const NAV: NavItem[] = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard", group: "main" },
  { key: "lakshya", label: "Lakshya", icon: "bolt", group: "main" },
  { key: "discovery", label: "Discovery", icon: "explore", group: "main" },
  { key: "company", label: "Company", icon: "business", group: "main" },
  { key: "compare", label: "Compare", icon: "compare_arrows", group: "main" },
  { key: "portfolio", label: "Portfolio", icon: "account_balance_wallet", group: "research" },
  { key: "watchlist", label: "Watchlist", icon: "visibility", group: "research" },
  { key: "domino", label: "Domino Effect", icon: "account_tree", group: "research" },
  { key: "insights", label: "Insights", icon: "lightbulb", group: "research" },
  { key: "filings", label: "Filings", icon: "description", group: "research" },
  { key: "news", label: "News", icon: "newspaper", group: "research" },
  { key: "simulator", label: "Simulator", icon: "query_stats", group: "tools" },
  { key: "profile", label: "Profile", icon: "person", group: "footer" },
  { key: "settings", label: "Settings", icon: "settings", group: "footer" },
];
