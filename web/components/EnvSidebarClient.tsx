"use client";

import { useState, useEffect, useRef } from "react";
import type { Editor } from "@tiptap/react";
import CopyButton from "@/components/CopyButton";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { TermPanel } from "@/components/ui/term-panel";
import { Button } from "@/components/ui/button";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Markdown } from "tiptap-markdown";
import { Bold, Italic, List, ListOrdered, Maximize2, Minimize2 } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";

export function TicketsClient({
  envId,
  initialTickets,
}: {
  envId: number;
  initialTickets: string[];
}) {
  const [tickets, setTickets] = useState<string[]>(initialTickets);
  const [ticketInput, setTicketInput] = useState("");

  async function addTicket() {
    const id = ticketInput.replace(/\D/g, "").trim();
    if (!id || tickets.includes(id)) { setTicketInput(""); return; }
    const next = [...tickets, id];
    setTickets(next);
    setTicketInput("");
    await fetch(`/api/env/${envId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_ids: next }),
    });
  }

  async function removeTicket(id: string) {
    const next = tickets.filter((t) => t !== id);
    setTickets(next);
    await fetch(`/api/env/${envId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_ids: next }),
    });
  }

  return (
    <div className="flex flex-wrap gap-2">
      {tickets.map((id) => (
        <div key={id} className="group flex items-center gap-1.5 border border-border/50 rounded-[3px] px-2.5 py-1">
          <a
            href={`https://www.odoo.com/odoo/project.task/${id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-amber-500/70 hover:text-amber-400 text-xs font-mono transition-colors"
          >
            #{id}
          </a>
          <CopyButton text={id} size="w-3 h-3" className="text-muted-foreground/60 hover:text-muted-foreground ml-0.5" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => removeTicket(id)}
            className="w-4 h-4 text-muted-foreground/60 hover:text-red-400 hover:bg-transparent cursor-pointer"
          >
            <XMarkIcon className="w-3 h-3" />
          </Button>
        </div>
      ))}
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          value={ticketInput}
          onChange={(e) => setTicketInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTicket()}
          placeholder="Add ticket..."
          className="bg-transparent border border-border/50 rounded-[3px] px-2.5 py-1 text-xs font-mono text-muted-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-cyan-400/60 w-28 transition-colors"
        />
        <Button
          variant="ghost"
          size="icon"
          onClick={addTicket}
          disabled={!ticketInput.trim()}
          className="w-5 h-5 text-muted-foreground hover:text-foreground hover:bg-transparent cursor-pointer disabled:opacity-40"
        >
          <PlusIcon className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

function NotesEditor({ initialContent, onSave, onLiveChange, onEditorReady, expanded, frameless, className }: {
  initialContent: string;
  onSave: (html: string) => void;
  onLiveChange?: (html: string) => void;
  onEditorReady?: (editor: Editor) => void;
  expanded?: boolean;
  /** Drop the standalone input frame — for use inside a TermPanel body. */
  frameless?: boolean;
  className?: string;
}) {
  const [wordCount, setWordCount] = useState(0);
  const editor = useEditor({ immediatelyRender: false,
    extensions: [
      StarterKit,
      Image.configure({ inline: false, allowBase64: false }),
      Markdown.configure({ transformPastedText: true, transformCopiedText: true }),
    ],
    content: initialContent,
    parseOptions: { preserveWhitespace: "full" },
    editorProps: {
      attributes: {
        class: "focus:outline-none text-sm text-foreground/70 leading-relaxed h-full",
      },
      handlePaste(view, event) {
        const items = Array.from(event.clipboardData?.items ?? []);
        const imageItem = items.find(i => i.type.startsWith("image/"));
        if (!imageItem) return false;
        const file = imageItem.getAsFile();
        if (!file) return false;
        const form = new FormData();
        form.append("file", file);
        fetch("/api/notes/images", { method: "POST", body: form })
          .then(r => r.json())
          .then(({ url }) => {
            const node = view.state.schema.nodes.image.create({ src: url });
            view.dispatch(view.state.tr.replaceSelectionWith(node));
          });
        return true;
      },
    },
    onBlur: ({ editor }) => {
      onSave(editor.getHTML());
    },
    onUpdate: ({ editor }) => {
      const text = editor.getText();
      setWordCount(text.trim() ? text.trim().split(/\s+/).length : 0);
      onLiveChange?.(editor.getHTML());
    },
    onCreate: ({ editor }) => {
      onEditorReady?.(editor);
    },
  });

  if (!editor) return null;

  const toolbarButtons = [
    { icon: <Bold className="w-3.5 h-3.5" />, action: () => editor.chain().focus().toggleBold().run(), active: editor.isActive("bold"), title: "Bold (Ctrl+B)" },
    { icon: <Italic className="w-3.5 h-3.5" />, action: () => editor.chain().focus().toggleItalic().run(), active: editor.isActive("italic"), title: "Italic (Ctrl+I)" },
    { icon: <List className="w-3.5 h-3.5" />, action: () => editor.chain().focus().toggleBulletList().run(), active: editor.isActive("bulletList"), title: "Bullet list" },
    { icon: <ListOrdered className="w-3.5 h-3.5" />, action: () => editor.chain().focus().toggleOrderedList().run(), active: editor.isActive("orderedList"), title: "Numbered list" },
  ];

  return (
    <div className={className}>
      <div className="flex items-center gap-0.5 mb-2">
        {toolbarButtons.map((btn, i) => (
          <Button key={i} variant="ghost" size="icon-sm" onClick={btn.action} title={btn.title}
            className={btn.active ? "text-foreground/80" : "text-muted-foreground/70 hover:text-muted-foreground"}>
            {btn.icon}
          </Button>
        ))}
        {wordCount > 0 && (
          <span className="ml-2 text-[10px] text-muted-foreground/70 tabular-nums">{wordCount}w</span>
        )}
      </div>
      <EditorContent
        editor={editor}
        className={[
          frameless
            ? "w-full overflow-y-auto"
            : "w-full border border-border/50 hover:border-border rounded-md px-4 py-3 transition-colors overflow-y-auto",
          "[&::-webkit-scrollbar]:hidden [scrollbar-width:none]",
          "[&_.ProseMirror]:outline-none [&_.ProseMirror]:h-full",
          "[&_.ProseMirror_p]:leading-relaxed [&_.ProseMirror_p+p]:mt-1",
          "[&_.ProseMirror_strong]:text-foreground [&_.ProseMirror_strong]:font-semibold",
          "[&_.ProseMirror_em]:italic",
          "[&_.ProseMirror_h1]:text-base [&_.ProseMirror_h1]:font-semibold [&_.ProseMirror_h1]:text-foreground/80 [&_.ProseMirror_h1]:mb-1",
          "[&_.ProseMirror_h2]:text-sm [&_.ProseMirror_h2]:font-semibold [&_.ProseMirror_h2]:text-foreground/80",
          "[&_.ProseMirror_h3]:text-sm [&_.ProseMirror_h3]:font-semibold [&_.ProseMirror_h3]:text-foreground/70",
          "[&_.ProseMirror_ul]:list-disc [&_.ProseMirror_ul]:list-inside [&_.ProseMirror_ul]:space-y-0.5",
          "[&_.ProseMirror_ol]:list-decimal [&_.ProseMirror_ol]:list-inside [&_.ProseMirror_ol]:space-y-0.5",
          "[&_.ProseMirror_li_p]:inline",
          "[&_.ProseMirror_blockquote]:border-l-2 [&_.ProseMirror_blockquote]:border-border [&_.ProseMirror_blockquote]:pl-3 [&_.ProseMirror_blockquote]:text-muted-foreground [&_.ProseMirror_blockquote]:italic",
          "[&_.ProseMirror_a]:text-violet-400 [&_.ProseMirror_a]:underline [&_.ProseMirror_a]:cursor-pointer [&_.ProseMirror_a:hover]:text-violet-300",
          "[&_.ProseMirror_code]:bg-muted [&_.ProseMirror_code]:text-foreground/70 [&_.ProseMirror_code]:px-1 [&_.ProseMirror_code]:py-0.5 [&_.ProseMirror_code]:rounded [&_.ProseMirror_code]:text-xs [&_.ProseMirror_code]:font-mono",
          "[&_.ProseMirror_pre]:bg-muted [&_.ProseMirror_pre]:border [&_.ProseMirror_pre]:border-border [&_.ProseMirror_pre]:rounded-lg [&_.ProseMirror_pre]:px-4 [&_.ProseMirror_pre]:py-3 [&_.ProseMirror_pre]:overflow-x-auto [&_.ProseMirror_pre]:my-2",
          "[&_.ProseMirror_img]:max-w-full [&_.ProseMirror_img]:rounded-lg [&_.ProseMirror_img]:my-2 [&_.ProseMirror_img]:block",
          "[&_.ProseMirror_.is-editor-empty:first-child::before]:content-['Add_a_note...'] [&_.ProseMirror_.is-editor-empty:first-child::before]:text-muted-foreground/60 [&_.ProseMirror_.is-editor-empty:first-child::before]:float-left [&_.ProseMirror_.is-editor-empty:first-child::before]:pointer-events-none [&_.ProseMirror_.is-editor-empty:first-child::before]:h-0",
          expanded ? "h-full" : "min-h-40",
        ].join(" ")}
      />
    </div>
  );
}

export function NotesClient({
  envId,
  initialNotes,
}: {
  envId: number;
  initialNotes: string | null;
}) {
  const [notesSaving, setNotesSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [liveContent, setLiveContent] = useState(initialNotes ?? "");
  const inlineEditorRef = useRef<Editor | null>(null);
  const dialogEditorRef = useRef<Editor | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "e") {
        e.preventDefault();
        setExpanded(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function extractImageFilenames(html: string): Set<string> {
    const matches = html.matchAll(/\/api\/notes\/images\/([a-f0-9-]+\.[a-z]+)/g);
    return new Set([...matches].map(m => m[1]));
  }

  async function saveNotes(value: string) {
    const removed = [...extractImageFilenames(liveContent)].filter(f => !extractImageFilenames(value).has(f));
    for (const filename of removed) {
      fetch(`/api/notes/images/${filename}`, { method: "DELETE" }).catch(() => {});
    }
    setLiveContent(value);
    setNotesSaving(true);
    await fetch(`/api/env/${envId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: value || null }),
    }).finally(() => setNotesSaving(false));
  }

  // Single close path for the full-screen editor — saves the dialog editor's
  // current HTML (not the possibly-stale liveContent state) then syncs the inline
  // editor. The collapse button and Escape/backdrop both route through here.
  function closeExpanded() {
    const ed = dialogEditorRef.current;
    const latest = ed && !ed.isDestroyed ? ed.getHTML() : liveContent;
    saveNotes(latest);
    inlineEditorRef.current?.commands.setContent(latest);
    setExpanded(false);
  }

  function handleOpenChange(open: boolean) {
    if (open) {
      setExpanded(true);
    } else {
      closeExpanded();
    }
  }

  return (
    <>
      <TermPanel
        title="notes"
        right={
          <>
            {notesSaving && <span className="text-[10px] text-muted-foreground/70">Saving...</span>}
            <Button variant="ghost" size="icon-sm" onClick={() => setExpanded(true)} className="text-muted-foreground/70 hover:text-muted-foreground" title="Expand">
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          </>
        }
        bodyClassName="px-4 py-3"
      >
        <NotesEditor
          frameless
          initialContent={initialNotes ?? ""}
          onSave={saveNotes}
          onLiveChange={setLiveContent}
          onEditorReady={(ed) => { inlineEditorRef.current = ed; }}
        />
      </TermPanel>

      <Dialog open={expanded} onOpenChange={handleOpenChange}>
        <DialogContent showCloseButton={false} className="sm:max-w-[80vw] w-[80vw] h-[95vh] bg-background border-border/50 flex flex-col gap-0 p-0 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
            <p className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-[0.3em]">Notes</p>
            <div className="flex items-center gap-2">
              {notesSaving && <span className="text-[10px] text-muted-foreground/70">Saving...</span>}
              <Button variant="ghost" size="icon-sm" onClick={closeExpanded} className="text-muted-foreground/70 hover:text-muted-foreground" title="Collapse">
                <Minimize2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-hidden p-4">
            <NotesEditor
              key="dialog"
              initialContent={liveContent}
              onSave={saveNotes}
              onLiveChange={setLiveContent}
              onEditorReady={(ed) => { dialogEditorRef.current = ed; }}
              expanded
              className="h-full flex flex-col"
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
