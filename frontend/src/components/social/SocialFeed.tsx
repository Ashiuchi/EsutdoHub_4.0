"use client";

import { useState } from "react";
import { Send, ImageIcon } from "lucide-react";
import PostCard, { type Post } from "./PostCard";

const MOCK_POSTS: Post[] = [
  {
    id: "1",
    author: { name: "Ana Beatriz", handle: "anabeatriz", avatarColor: "#6366f1" },
    content:
      "Acabei de concluir os estudos sobre Direito Administrativo para o concurso do TRF. Alguém mais está nessa maratona? 📚",
    createdAt: new Date(Date.now() - 12 * 60_000).toISOString(),
    likes: 14,
    comments: 3,
  },
  {
    id: "2",
    author: { name: "Carlos Mendes", handle: "cmendes", avatarColor: "#f59e0b" },
    content:
      "Dica de ouro para quem vai fazer o ENEM: resolva provas anteriores cronometradas. Faz toda a diferença na gestão de tempo!\n\nUsando o Cockpit do EstudoHub pra organizar os editais e recomendo demais. 🚀",
    createdAt: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    likes: 37,
    comments: 9,
    liked: true,
  },
  {
    id: "3",
    author: { name: "Rafaela Costa", handle: "rafaelac", avatarColor: "#10b981" },
    content:
      "Alguém tem material de Raciocínio Lógico para compartilhar? Estou travada nos exercícios de sequências numéricas. Qualquer ajuda vale!",
    createdAt: new Date(Date.now() - 6 * 3_600_000).toISOString(),
    likes: 8,
    comments: 15,
  },
];

export default function SocialFeed() {
  const [posts, setPosts] = useState<Post[]>(MOCK_POSTS);
  const [draft, setDraft] = useState("");

  function handlePost() {
    const text = draft.trim();
    if (!text) return;
    const newPost: Post = {
      id: Date.now().toString(),
      author: { name: "Você", handle: "voce" },
      content: text,
      createdAt: new Date().toISOString(),
      likes: 0,
      comments: 0,
    };
    setPosts((prev) => [newPost, ...prev]);
    setDraft("");
  }

  return (
    <section className="space-y-4">
      {/* Compose box */}
      <div className="glass rounded-xl p-4 space-y-3">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handlePost();
          }}
          placeholder="O que você está estudando hoje?"
          rows={3}
          className="w-full bg-transparent resize-none text-sm text-[var(--text-offwhite)] placeholder:text-[var(--text-offwhite)]/40 outline-none leading-relaxed"
        />
        <div
          className="flex items-center justify-between pt-3"
          style={{ borderTop: "1px solid rgba(224,224,224,0.06)" }}
        >
          <button className="flex items-center gap-1.5 text-xs text-[var(--text-offwhite)]/40 hover:text-[var(--text-offwhite)] transition-colors">
            <ImageIcon size={15} strokeWidth={1.75} />
            Imagem
          </button>
          <button
            onClick={handlePost}
            disabled={!draft.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-[var(--primary-teal)] text-white disabled:opacity-40 hover:brightness-110 transition-all"
          >
            <Send size={13} strokeWidth={2} />
            Postar
          </button>
        </div>
      </div>

      {/* Post list */}
      {posts.map((post) => (
        <PostCard key={post.id} post={post} />
      ))}
    </section>
  );
}
