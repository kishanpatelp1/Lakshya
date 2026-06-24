import { Icon } from "../components/Icon";

export function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center">
      <div className="w-14 h-14 rounded-full bg-bg-1 border border-outline-variant flex items-center justify-center mb-md">
        <Icon name="construction" className="text-[26px] text-on-surface-variant" />
      </div>
      <h2 className="text-section-header text-on-surface">{title}</h2>
      <p className="text-body-md text-on-surface-variant mt-xs max-w-md">
        This view is being rebuilt from the new design. Coming next.
      </p>
    </div>
  );
}
