"use client";

import { useState } from "react";
import { ClipboardDocumentIcon, CheckIcon } from "@heroicons/react/24/outline";

export default function CopyButton({
  text,
  className = "text-muted-foreground hover:text-foreground",
  size = "w-4 h-4",
}: {
  text: string;
  className?: string;
  size?: string;
}) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      onClick={copy}
      title={`Copy: ${text}`}
      className={`shrink-0 transition-colors cursor-pointer ${className}`}
    >
      {copied ? (
        <CheckIcon className={size} />
      ) : (
        <ClipboardDocumentIcon className={size} />
      )}
    </button>
  );
}
