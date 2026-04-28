"use client";

import { useState, useEffect } from "react";
import { Heart, MessageCircle, Share2, Paperclip } from "lucide-react";

export interface Post {
  id: string;
  author: {
    name: string;
    handle: string;
    avatarColor?: string;
  };
  content: string;
  createdAt: string;
  attachments?: { type: "image" | "file"; url: string; name: string }[];
  likes: number;
  comments: number;
  liked?: boolean;
}

function formatDate(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `${diffMin}min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}d`;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function Avatar({ name, color }: { name: string; color?: string }) {
  return (
    <div
      className="flex items-center justify-center w-10 h-10 rounded-full text-white font-semibold text-sm shrink-0 select-none"
      style={{ backgroundColor: color ?? "var(--primary-teal)" }}
    >
      {name.charAt(0).toUpperCase()}
    </div>
  );
}

export default function PostCard({ post }: { post: Post }) {
  const [liked, setLiked] = useState(post.liked ?? false);
  const [likeCount, setLikeCount] = useState(post.likes);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  function toggleLike() {
    setLiked((v) => !v);
    setLikeCount((n) => (liked ? n - 1 : n + 1));
  }

  return (
    <article className="glass rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Avatar name={post.author.name} color={post.author.avatarColor} />
        <div className="flex-1 min-w-0">
          <div className="text-[var(--text-offwhite)] font-medium text-sm leading-tight truncate">
            {post.author.name}
          </div>
          <div className="text-[var(--text-offwhite)]/50 text-xs" suppressHydrationWarning>
            @{post.author.handle}{mounted ? ` · ${formatDate(post.createdAt)}` : ""}
          </div>
        </div>
      </div>

      {/* Content */}
      <p className="text-[var(--text-offwhite)]/90 text-sm leading-relaxed whitespace-pre-wrap">
        {post.content}
      </p>

      {/* Attachments */}
      {post.attachments && post.attachments.length > 0 && (
        <div className="space-y-2">
          {post.attachments.map((att, i) =>
            att.type === "image" ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={i}
                src={att.url}
                alt={att.name}
                className="w-full rounded-lg object-cover max-h-72"
              />
            ) : (
              <div
                key={i}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.06] text-[var(--text-offwhite)]/70 text-xs"
              >
                <Paperclip size={14} strokeWidth={1.75} />
                {att.name}
              </div>
            )
          )}
        </div>
      )}

      {/* Actions */}
      <div
        className="flex items-center gap-6 pt-3"
        style={{ borderTop: "1px solid rgba(224,224,224,0.06)" }}
      >
        <button
          onClick={toggleLike}
          className={`flex items-center gap-1.5 text-xs transition-colors ${
            liked
              ? "text-[var(--primary-teal)]"
              : "text-[var(--text-offwhite)]/50 hover:text-[var(--primary-teal)]"
          }`}
        >
          <Heart
            size={15}
            strokeWidth={1.75}
            fill={liked ? "currentColor" : "none"}
          />
          {likeCount}
        </button>

        <button className="flex items-center gap-1.5 text-xs text-[var(--text-offwhite)]/50 hover:text-[var(--primary-teal)] transition-colors">
          <MessageCircle size={15} strokeWidth={1.75} />
          {post.comments}
        </button>

        <button className="flex items-center gap-1.5 text-xs text-[var(--text-offwhite)]/50 hover:text-[var(--primary-teal)] transition-colors ml-auto">
          <Share2 size={15} strokeWidth={1.75} />
          Compartilhar
        </button>
      </div>
    </article>
  );
}
