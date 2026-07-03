import { cn } from "@/lib/utils";

type SectionHeaderProps = {
  title: string;
  action?: React.ReactNode;
  className?: string;
};

export function SectionHeader({ title, action, className }: SectionHeaderProps) {
  return (
    <div className={cn("flex items-center justify-between", className)}>
      {/* Stepped down from .section-label's 13px — page eyebrows own that size */}
      <p className="section-label text-[11px]">{title}</p>
      {action}
    </div>
  );
}
