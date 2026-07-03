"use client"

import { Toaster as Sonner, type ToasterProps } from "sonner"
import { useTheme } from "@/components/ThemeProvider"

const Toaster = ({ ...props }: ToasterProps) => {
  const { isLight } = useTheme();

  return (
    <Sonner
      theme={isLight ? "light" : "dark"}
      position="bottom-center"
      richColors
      style={{
        "--normal-bg": "var(--popover)",
        "--normal-text": "var(--popover-foreground)",
        "--normal-border": "var(--border)",
        "--success-bg": "var(--popover)",
        "--success-text": "var(--cc-emerald-300)",
        "--success-border": "color-mix(in oklch, var(--cc-emerald-400) 35%, transparent)",
        "--error-bg": "var(--popover)",
        "--error-text": "var(--cc-red-300)",
        "--error-border": "color-mix(in oklch, var(--cc-red-400) 35%, transparent)",
        "--warning-bg": "var(--popover)",
        "--warning-text": "var(--cc-amber-300)",
        "--warning-border": "color-mix(in oklch, var(--cc-amber-400) 35%, transparent)",
        "--info-bg": "var(--popover)",
        "--info-text": "var(--cc-sky-300)",
        "--info-border": "color-mix(in oklch, var(--cc-sky-400) 35%, transparent)",
      } as React.CSSProperties}
      toastOptions={{
        classNames: {
          toast: "!rounded-md !shadow-lg !shadow-black/20 !border !gap-3",
          title: "!text-[13px] !font-mono !font-medium",
          description: "!text-xs !text-muted-foreground",
          actionButton: "!text-xs !font-mono !font-semibold !px-3 !py-1 !rounded-[3px] !transition-colors !cursor-pointer !bg-foreground !text-background",
          cancelButton: "!text-xs !text-muted-foreground hover:!text-foreground !cursor-pointer",
        },
      }}
      {...props}
    />
  );
}

export { Toaster }
