import type { ReactNode } from "react";
import { Icon } from "./Icon";

/* ── Card ─────────────────────────────────────────────────────────────── */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-bg-1 border border-outline-variant rounded-lg ${className}`}>{children}</div>
  );
}

export function CardHeader({ title, icon, right }: { title: string; icon?: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-lg pt-lg pb-md">
      <div className="flex items-center gap-sm">
        {icon && <Icon name={icon} className="text-[18px] text-primary" />}
        <h3 className="text-card-title font-card-title uppercase text-on-surface">{title}</h3>
      </div>
      {right}
    </div>
  );
}

/* ── Stat tile ────────────────────────────────────────────────────────── */
export function StatTile({
  label,
  value,
  sub,
  accent = false,
  valueClass = "",
  icon,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: boolean;
  valueClass?: string;
  icon?: string;
}) {
  return (
    <div
      className={`bg-bg-1 border border-outline-variant rounded-lg p-lg ${
        accent ? "border-l-2 border-l-primary" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="text-label-caps font-label-caps text-on-surface-variant">{label}</p>
        {icon && <Icon name={icon} className="text-[18px] text-on-surface-variant" />}
      </div>
      <p className={`text-[30px] leading-tight font-semibold mt-sm tabular whitespace-nowrap ${valueClass || "text-on-surface"}`}>
        {value}
      </p>
      {sub && <div className="mt-sm text-body-sm text-on-surface-variant">{sub}</div>}
    </div>
  );
}

/* ── Chip / badge ─────────────────────────────────────────────────────── */
type ChipTone = "positive" | "negative" | "neutral" | "warning" | "tag";
const chipTone: Record<ChipTone, string> = {
  positive: "bg-positive/15 text-positive",
  negative: "bg-negative/15 text-negative",
  neutral: "bg-no-effect/15 text-no-effect",
  warning: "bg-warning/15 text-warning",
  tag: "bg-bg-2 text-on-surface-variant border border-outline-variant",
};

export function Chip({ children, tone = "tag", className = "" }: { children: ReactNode; tone?: ChipTone; className?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-sm py-[2px] text-label-caps font-label-caps ${chipTone[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
export function PrimaryButton({ children, onClick, disabled, className = "" }: { children: ReactNode; onClick?: () => void; disabled?: boolean; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`px-md py-sm rounded bg-primary text-on-primary text-body-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export function GhostButton({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-md py-sm rounded border border-outline-variant bg-bg-1 text-primary text-body-sm hover:bg-surface-container-highest transition-colors ${className}`}
    >
      {children}
    </button>
  );
}

/* ── Skeleton ─────────────────────────────────────────────────────────── */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-bg-2 ${className}`} />;
}
