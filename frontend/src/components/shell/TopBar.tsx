import { useTheme } from "../../lib/theme";
import { Icon } from "../Icon";

interface Props {
  leftClass: string; // md:left-16 | md:left-60
  onOpenMobile: () => void;
}

export function TopBar({ leftClass, onOpenMobile }: Props) {
  const { theme, toggle } = useTheme();

  return (
    <header
      className={`fixed top-0 right-0 left-0 ${leftClass} z-40 border-b border-outline-variant bg-bg-0/80 backdrop-blur-md flex justify-between items-center h-16 px-margin-mobile md:px-margin-desktop`}
    >
      {/* Left: hamburger (mobile) + search */}
      <div className="flex items-center gap-sm md:gap-md min-w-0">
        <button type="button" onClick={onOpenMobile} className="md:hidden text-on-surface-variant hover:text-on-surface" aria-label="Open menu">
          <Icon name="menu" className="text-[24px]" />
        </button>
        <div className="flex items-center bg-bg-1 border border-outline-variant rounded px-md py-sm focus-within:border-primary transition-colors min-w-0">
          <Icon name="search" className="text-on-surface-variant text-[20px] mr-sm shrink-0" />
          <input
            className="bg-transparent border-none text-body-md text-on-surface focus:outline-none focus:ring-0 placeholder:text-on-surface-variant w-28 sm:w-48 lg:w-64 min-w-0"
            placeholder="Search tickers, news…"
            type="text"
          />
          <span className="hidden sm:inline text-caption text-on-surface-variant border border-outline-variant rounded px-xs py-[2px] ml-sm">⌘K</span>
        </div>
      </div>

      {/* Right cluster */}
      <div className="flex items-center gap-md md:gap-lg shrink-0">
        <span className="hidden sm:inline text-label-caps font-label-caps text-on-surface-variant border border-outline-variant rounded px-sm py-xs">LIVE</span>
        <button type="button" onClick={toggle} className="text-on-surface-variant hover:text-on-surface transition-colors" aria-label="Toggle theme">
          <Icon name={theme === "dark" ? "light_mode" : "dark_mode"} className="text-[20px]" />
        </button>
        <div className="hidden sm:block h-6 w-px bg-outline-variant" />
        <button type="button" className="flex items-center gap-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <div className="w-8 h-8 rounded-full border border-outline-variant bg-bg-2 flex items-center justify-center shrink-0">
            <Icon name="person" className="text-[18px]" />
          </div>
          <span className="hidden lg:inline text-body-md">Profile</span>
          <Icon name="expand_more" className="hidden lg:inline text-[16px]" />
        </button>
      </div>
    </header>
  );
}
