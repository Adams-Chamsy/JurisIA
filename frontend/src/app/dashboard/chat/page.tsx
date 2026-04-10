'use client';

/**
 * JurisIA — Page Assistant Juridique (Chat)
 * Interface conversationnelle avec historique, suggestions rapides et sources.
 */

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send, Plus, Scale, ExternalLink, ChevronDown, Loader2, Trash2 } from 'lucide-react';
import { Button, Spinner, Skeleton } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { apiPost, apiGet, apiDelete } from '@/services/api';
import { cn, formatDate } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────
interface Message {
  id:         string;
  role:       'user' | 'assistant';
  content:    string;
  sources?:   Source[];
  created_at: string;
}

interface Source {
  article: string;
  code:    string;
  url:     string;
}

interface Conversation {
  id:            string;
  title:         string | null;
  updated_at:    string;
  message_count: number;
  messages?:     Message[];
}

// ── Suggestions rapides ───────────────────────────────────────────────────────
const SUGGESTIONS = [
  'Comment licencier un salarié pour faute grave ?',
  'Que dit l\'AI Act pour mon entreprise ?',
  'Délais légaux pour une mise en demeure ?',
  'Mes CGV sont-elles obligatoires en B2B ?',
  'Comment calculer l\'indemnité de rupture conventionnelle ?',
  'Que risque-je si je ne suis pas conforme RGPD ?',
];

// ── Message Bubble ────────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  const [showSources, setShowSources] = useState(false);

  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div className={cn(
        'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-semibold',
        isUser ? 'bg-brand-electric text-white' : 'bg-brand-navy text-white',
      )} aria-hidden="true">
        {isUser ? 'Vous' : <Scale className="h-4 w-4" />}
      </div>

      {/* Contenu */}
      <div className={cn('max-w-[80%] space-y-2', isUser ? 'items-end' : 'items-start')}>
        <div className={cn(
          'rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-brand-electric text-white rounded-tr-none'
            : 'bg-muted text-foreground rounded-tl-none border border-border',
        )}>
          {/* Rendu du contenu avec sauts de ligne */}
          <div className="whitespace-pre-wrap">{msg.content}</div>
        </div>

        {/* Sources légales */}
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <div className="pl-0">
            <button
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              aria-expanded={showSources}
            >
              <span>📖 {msg.sources.length} référence{msg.sources.length > 1 ? 's' : ''} légale{msg.sources.length > 1 ? 's' : ''}</span>
              <ChevronDown className={cn('h-3 w-3 transition-transform', showSources && 'rotate-180')} />
            </button>
            {showSources && (
              <div className="mt-2 space-y-1 pl-2 border-l-2 border-muted">
                {msg.sources.map((src, i) => (
                  <a
                    key={i}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-brand-electric hover:underline"
                  >
                    <span>{src.article} du {src.code}</span>
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        <p className="text-2xs text-muted-foreground px-1">
          {new Date(msg.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const [inputValue,      setInputValue]      = useState('');
  const [activeConvId,    setActiveConvId]    = useState<string | null>(null);
  const [localMessages,   setLocalMessages]   = useState<Message[]>([]);
  const messagesEndRef                        = useRef<HTMLDivElement>(null);
  const inputRef                              = useRef<HTMLTextAreaElement>(null);
  const queryClient                           = useQueryClient();

  // Liste des conversations
  const { data: conversations, isLoading: convsLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn:  () => apiGet<Conversation[]>('/chat/conversations'),
  });

  // Chargement d'une conversation
  const { data: activeConv } = useQuery({
    queryKey: ['conversation', activeConvId],
    queryFn:  () => apiGet<Conversation>(`/chat/conversations/${activeConvId}`),
    enabled:  !!activeConvId,
  });

  // Synchroniser les messages locaux avec la conversation chargée
  useEffect(() => {
    if (activeConv?.messages) {
      setLocalMessages(activeConv.messages);
    }
  }, [activeConv]);

  // Scroll auto vers le bas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages]);

  // Mutation : envoi d'un message
  const sendMutation = useMutation({
    mutationFn: (message: string) =>
      apiPost<Message>('/chat/messages', {
        message,
        conversation_id: activeConvId,
      }),
    onMutate: async (message: string) => {
      // Optimistic update : ajouter le message utilisateur immédiatement
      const optimisticUserMsg: Message = {
        id:         `temp-${Date.now()}`,
        role:       'user',
        content:    message,
        created_at: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, optimisticUserMsg]);
    },
    onSuccess: (response) => {
      // Ajouter la réponse IA
      setLocalMessages((prev) => [
        ...prev.filter((m) => !m.id.startsWith('temp-')),
        response,
      ]);
      // Si c'était un nouveau chat, mettre à jour l'ID
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
    onError: (err: Error) => {
      setLocalMessages((prev) => prev.filter((m) => !m.id.startsWith('temp-')));
      toast.error('Erreur', err.message);
    },
  });

  // Mutation : supprimer une conversation
  const deleteMutation = useMutation({
    mutationFn: (convId: string) => apiDelete(`/chat/conversations/${convId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      if (activeConvId) {
        setActiveConvId(null);
        setLocalMessages([]);
      }
    },
  });

  const handleSend = () => {
    const message = inputValue.trim();
    if (!message || sendMutation.isPending) return;
    setInputValue('');
    sendMutation.mutate(message);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startNewChat = () => {
    setActiveConvId(null);
    setLocalMessages([]);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const currentMessages = activeConvId ? localMessages : localMessages;
  const isTyping = sendMutation.isPending;

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4 overflow-hidden">

      {/* Sidebar conversations */}
      <aside className="hidden lg:flex w-64 flex-col border border-border rounded-xl bg-background overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="font-semibold text-sm">Conversations</h2>
          <Button variant="ghost" size="icon" onClick={startNewChat} aria-label="Nouvelle conversation">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {convsLoading
            ? [...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)
            : conversations?.length === 0
              ? <p className="text-xs text-muted-foreground text-center py-8">Aucune conversation</p>
              : conversations?.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => { setActiveConvId(conv.id); setLocalMessages([]); }}
                    className={cn(
                      'w-full text-left rounded-lg p-3 transition-colors group flex items-start justify-between gap-2',
                      activeConvId === conv.id ? 'bg-muted' : 'hover:bg-muted/50',
                    )}
                    aria-current={activeConvId === conv.id ? 'page' : undefined}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-foreground truncate">
                        {conv.title || 'Nouvelle conversation'}
                      </p>
                      <p className="text-2xs text-muted-foreground mt-0.5">{formatDate(conv.updated_at)}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(conv.id); }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-red-500"
                      aria-label="Supprimer la conversation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </button>
                ))
          }
        </div>
      </aside>

      {/* Zone chat principale */}
      <div className="flex flex-1 flex-col border border-border rounded-xl bg-background overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-navy">
              <Scale className="h-4 w-4 text-white" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold">Assistant JurisIA</p>
              <p className="text-2xs text-green-600 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500 inline-block" aria-hidden="true" />
                En ligne · Droit français spécialisé
              </p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={startNewChat} leftIcon={<Plus className="h-3.5 w-3.5" />}>
            Nouveau
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-label="Conversation" aria-live="polite">

          {/* Message de bienvenue si pas de messages */}
          {currentMessages.length === 0 && !isTyping && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-6">
              <div>
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-navy">
                  <Scale className="h-9 w-9 text-white" aria-hidden="true" />
                </div>
                <h3 className="font-semibold text-foreground">Votre assistant juridique</h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                  Posez vos questions en droit des affaires, droit du travail, RGPD ou AI Act. 
                  Je cite toujours mes sources.
                </p>
              </div>
              <div className="grid sm:grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setInputValue(s)}
                    className="text-left text-xs rounded-lg border border-border p-3 hover:bg-muted/50 hover:border-brand-electric/40 transition-colors text-foreground/80"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {currentMessages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {/* Indicateur "en train de taper" */}
          {isTyping && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-navy">
                <Scale className="h-4 w-4 text-white" aria-hidden="true" />
              </div>
              <div className="rounded-2xl rounded-tl-none bg-muted border border-border px-4 py-3" aria-live="polite">
                <div className="flex items-center gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                      aria-hidden="true"
                    />
                  ))}
                  <span className="sr-only">JurisIA est en train de rédiger une réponse</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} aria-hidden="true" />
        </div>

        {/* Disclaimer */}
        <div className="px-4 py-1 bg-amber-50 border-t border-amber-100">
          <p className="text-2xs text-amber-700 text-center">
            ⚠️ Réponses à titre informatif — Non substituables à un conseil juridique professionnel
          </p>
        </div>

        {/* Zone de saisie */}
        <div className="p-4 border-t border-border">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Posez votre question juridique… (Entrée pour envoyer, Maj+Entrée pour retour à la ligne)"
                rows={1}
                className={cn(
                  'w-full resize-none rounded-xl border border-input bg-background px-4 py-3 pr-12',
                  'text-sm placeholder:text-muted-foreground',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  'max-h-32 min-h-[44px] transition-colors',
                )}
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const t = e.target as HTMLTextAreaElement;
                  t.style.height = 'auto';
                  t.style.height = `${Math.min(t.scrollHeight, 128)}px`;
                }}
                aria-label="Votre question juridique"
                maxLength={5000}
                disabled={isTyping}
              />
              <span className="absolute bottom-2 right-3 text-2xs text-muted-foreground/50" aria-hidden="true">
                {inputValue.length > 4000 ? `${inputValue.length}/5000` : ''}
              </span>
            </div>
            <Button
              onClick={handleSend}
              disabled={!inputValue.trim() || isTyping}
              size="icon"
              aria-label="Envoyer le message"
              className="h-11 w-11 flex-shrink-0"
            >
              {isTyping ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-2xs text-muted-foreground mt-2 text-right">Entrée pour envoyer · Maj+Entrée pour retour à la ligne</p>
        </div>
      </div>
    </div>
  );
}
