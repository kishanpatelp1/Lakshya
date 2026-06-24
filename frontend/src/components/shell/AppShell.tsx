import { useEffect, useState, type ReactNode } from "react";
import type { ViewKey } from "../../routes";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface Props {
  active: ViewKey;
  onNavigate: (view: ViewKey) => void;
  children: ReactNode;
}

const COLLAPSE_KEY = "lakshya-sidebar-collapsed";

export function AppShell({ active, onNavigate, children }: Props) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const navigate = (v: ViewKey) => {
    onNavigate(v);
    setMobileOpen(false);
  };

  const mainMl = collapsed ? "md:ml-16" : "md:ml-60";
  const topLeft = collapsed ? "md:left-16" : "md:left-60";

  return (
    <div className="bg-bg-0 text-on-surface">
      {/* Desktop sidebar */}
      <div className={`hidden md:block fixed left-0 top-0 h-screen z-50 ${collapsed ? "w-16" : "w-60"} transition-[width] duration-200`}>
        <Sidebar active={active} collapsed={collapsed} onNavigate={navigate} onToggleCollapse={() => setCollapsed((c) => !c)} />
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-[60]">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-60 z-10 shadow-2xl">
            <Sidebar active={active} collapsed={false} onNavigate={navigate} />
          </div>
        </div>
      )}

      <TopBar leftClass={topLeft} onOpenMobile={() => setMobileOpen(true)} />

      <main className={`${mainMl} h-screen overflow-y-auto bg-bg-0 px-margin-mobile md:px-margin-desktop pt-[calc(4rem+24px)] pb-xl transition-[margin] duration-200`}>
        <div className="max-w-[1440px] mx-auto space-y-lg">{children}</div>
      </main>
    </div>
  );
}
