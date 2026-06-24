import { NAV, type ViewKey } from "../../routes";
import { Icon } from "../Icon";
import { useAuth } from "../../lib/auth";

interface Props {
  active: ViewKey;
  collapsed: boolean;
  onNavigate: (view: ViewKey) => void;
  onToggleCollapse?: () => void;
}

function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: (typeof NAV)[number];
  active: boolean;
  collapsed: boolean;
  onNavigate: (v: ViewKey) => void;
}) {
  return (
    <button
      type="button"
      title={collapsed ? item.label : undefined}
      onClick={() => onNavigate(item.key)}
      className={`w-full flex items-center gap-md ${collapsed ? "justify-center px-0" : "px-md"} py-sm rounded transition-colors duration-200 ${
        active
          ? "text-primary border-r-2 border-primary bg-surface-container-low"
          : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
      }`}
    >
      <Icon name={item.icon} className="text-[20px] shrink-0" />
      {!collapsed && <span className="text-label-caps font-label-caps whitespace-nowrap">{item.label}</span>}
    </button>
  );
}

export function Sidebar({ active, collapsed, onNavigate, onToggleCollapse }: Props) {
  const { user, logout } = useAuth();
  const groups: Array<(typeof NAV)[number][]> = [
    NAV.filter((n) => n.group === "main"),
    NAV.filter((n) => n.group === "research"),
    NAV.filter((n) => n.group === "tools"),
  ];
  const footer = NAV.filter((n) => n.group === "footer");

  return (
    <nav className="h-full w-full border-r border-outline-variant bg-bg-0 flex flex-col py-lg">
      {/* Brand */}
      <div className={`${collapsed ? "px-0 flex justify-center" : "px-lg"} mb-xl`}>
        <div className="flex items-center gap-sm">
          <div className="w-8 h-8 bg-primary rounded flex items-center justify-center text-on-primary font-bold shrink-0">L</div>
          {!collapsed && (
            <div>
              <h1 className="text-section-header text-on-surface tracking-tight font-bold">Lakshya</h1>
              <p className="text-caption text-on-surface-variant">Research Console</p>
            </div>
          )}
        </div>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto px-sm space-y-xs">
        {groups.map((group, gi) => (
          <div key={gi} className="space-y-xs">
            {gi > 0 && <div className="my-md border-t border-outline-variant/50 mx-md" />}
            {group.map((n) => (
              <NavLink key={n.key} item={n} active={active === n.key} collapsed={collapsed} onNavigate={onNavigate} />
            ))}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-sm mt-auto space-y-xs pt-md border-t border-outline-variant/50">
        {footer.map((n) => (
          <NavLink key={n.key} item={n} active={active === n.key} collapsed={collapsed} onNavigate={onNavigate} />
        ))}

        {/* Signed-in user + logout */}
        {!collapsed && user && (
          <div className="px-md pt-sm pb-xs">
            <div className="text-label-caps font-label-caps text-on-surface-variant truncate">
              {user.full_name || "Signed in"}
            </div>
            <div className="text-caption text-on-surface-variant truncate">{user.email}</div>
          </div>
        )}
        <button
          type="button"
          onClick={() => logout()}
          title={collapsed ? "Sign out" : undefined}
          className={`w-full flex items-center gap-md ${collapsed ? "justify-center px-0" : "px-md"} py-sm rounded text-on-surface-variant hover:text-negative hover:bg-surface-container-low transition-colors`}
        >
          <Icon name="logout" className="text-[20px] shrink-0" />
          {!collapsed && <span className="text-label-caps font-label-caps">Sign out</span>}
        </button>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title={collapsed ? "Expand" : "Collapse"}
            className={`hidden md:flex w-full items-center gap-md ${collapsed ? "justify-center px-0" : "px-md"} py-sm rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low transition-colors`}
          >
            <Icon name={collapsed ? "chevron_right" : "chevron_left"} className="text-[20px] shrink-0" />
            {!collapsed && <span className="text-label-caps font-label-caps">Collapse</span>}
          </button>
        )}
      </div>
    </nav>
  );
}
