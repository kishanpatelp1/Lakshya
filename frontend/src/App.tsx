import { useEffect, useState } from "react";
import { AppShell } from "./components/shell/AppShell";
import { NAV, type ViewKey } from "./routes";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DashboardView } from "./views/DashboardView";
import { DominoView } from "./views/DominoView";
import { LakshyaView } from "./views/LakshyaView";
import { PortfolioView } from "./views/PortfolioView";
import { DiscoveryView } from "./views/DiscoveryView";
import { CompanyView } from "./views/CompanyView";
import { CompareView } from "./views/CompareView";
import { WatchlistView } from "./views/WatchlistView";
import { NewsView } from "./views/NewsView";
import { FilingsView } from "./views/FilingsView";
import { InsightsView } from "./views/InsightsView";
import { SimulatorView } from "./views/SimulatorView";
import { ProfileView } from "./views/ProfileView";
import { SettingsView } from "./views/SettingsView";
import { AuthView, OnboardingView } from "./views/AuthView";
import { Placeholder } from "./views/Placeholder";
import { useAuth } from "./lib/auth";
import { Icon } from "./components/Icon";

const VALID_VIEWS = new Set(NAV.map((n) => n.key));

function parseHash(): { view: ViewKey; companyId: string | null } {
  const raw = window.location.hash.replace(/^#\/?/, ""); // "#/company/<id>" or "#news"
  const [v, id] = raw.split("/");
  const view = (VALID_VIEWS.has(v as ViewKey) ? v : "dashboard") as ViewKey;
  return { view, companyId: v === "company" && id ? id : null };
}

export default function App() {
  const { user, loading, needsOnboarding } = useAuth();
  const initial = parseHash();
  const [view, setView] = useState<ViewKey>(initial.view);
  const [companyId, setCompanyId] = useState<string | null>(initial.companyId);
  const label = NAV.find((n) => n.key === view)?.label ?? view;

  // Two-way sync between app state and the URL hash so refresh + deep-links work
  // and browser back/forward navigates views.
  useEffect(() => {
    const target = view === "company" && companyId ? `#/company/${companyId}` : `#/${view}`;
    if (window.location.hash !== target) window.location.hash = target;
  }, [view, companyId]);

  useEffect(() => {
    const onHash = () => {
      const { view: v, companyId: c } = parseHash();
      setView(v);
      setCompanyId(c);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-0 flex items-center justify-center">
        <Icon name="progress_activity" className="text-primary text-[32px] animate-spin" />
      </div>
    );
  }

  if (!user) return <AuthView />;
  if (needsOnboarding) return <OnboardingView />;

  function openCompany(id: string) {
    setCompanyId(id);
    setView("company");
  }

  function renderView() {
    switch (view) {
      case "dashboard":
        return <DashboardView onNavigate={setView} />;
      case "lakshya":
        return <LakshyaView />;
      case "portfolio":
        return <PortfolioView />;
      case "domino":
        return <DominoView />;
      case "discovery":
        return <DiscoveryView onOpenCompany={openCompany} />;
      case "company":
        return <CompanyView companyId={companyId} onOpenCompany={openCompany} />;
      case "compare":
        return <CompareView />;
      case "watchlist":
        return <WatchlistView onOpenCompany={openCompany} />;
      case "news":
        return <NewsView />;
      case "filings":
        return <FilingsView />;
      case "insights":
        return <InsightsView onOpenCompany={openCompany} />;
      case "simulator":
        return <SimulatorView />;
      case "profile":
        return <ProfileView />;
      case "settings":
        return <SettingsView />;
      default:
        return <Placeholder title={label} />;
    }
  }

  return (
    <AppShell active={view} onNavigate={setView}>
      <ErrorBoundary key={view}>{renderView()}</ErrorBoundary>
    </AppShell>
  );
}
