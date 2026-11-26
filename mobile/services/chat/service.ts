import { ApiError } from '../api/client';
import type { RequestOperation } from '../../adapters/transport/types';
import type { Conversation, Message, Page, Progress, TurnStatus, MessageResult } from '../../types/contracts';

export interface ChatTransport {
  get<T>(path: string): RequestOperation<T>;
  post<T>(path: string, data?: unknown, timeout?: number): RequestOperation<T>;
}

/** Current backend returns one JSON response; never pretend it is token streaming. */
export class ChatService {
  readonly transportMode = 'JSON_WITH_STATUS_POLLING';
  private reads = new Set<() => void>();
  constructor(private api: ChatTransport) {}
  private read<T>(path: string): Promise<T> {
    const operation = this.api.get<T>(path);
    this.reads.add(operation.cancel);
    return operation.promise.finally(() => this.reads.delete(operation.cancel));
  }
  cancelReads() { for (const cancel of [...this.reads]) cancel(); this.reads.clear(); }
  listConversations() { return this.read<Page<Conversation>>('/coach/conversations?page=1&page_size=20&status=active'); }
  createConversation() { return this.api.post<Conversation>('/coach/conversations', {}).promise; }
  messages(id: string, page = 1) {
    return this.read<Page<Message>>(`/coach/conversations/${encodeURIComponent(id)}/messages?page=${page}&page_size=50`);
  }
  turnStatus(id: string, turnId: string) {
    return this.read<TurnStatus>(`/coach/conversations/${encodeURIComponent(id)}/turns/${encodeURIComponent(turnId)}/status`);
  }
  send(id: string, message: string, clientTurnId: string, onProgress?: (value: Progress) => void): RequestOperation<MessageResult> {
    const base = `/coach/conversations/${encodeURIComponent(id)}`;
    const send = this.api.post<MessageResult>(`${base}/messages`, { message, client_turn_id: clientTurnId }, 180000);
    let stopped = false, timer: ReturnType<typeof setTimeout> | undefined;
    let poll: RequestOperation<TurnStatus> | undefined;
    let sequence = -1, tries = 0;
    const stop = () => { stopped = true; if (timer !== undefined) clearTimeout(timer); poll?.cancel(); };
    const check = async () => {
      if (stopped || tries >= 60) return;
      tries++;
      try {
        poll = this.api.get<TurnStatus>(`${base}/turns/${encodeURIComponent(clientTurnId)}/status`);
        const status = await poll.promise;
        if (stopped) return;
        if (status.progress.sequence > sequence) { sequence = status.progress.sequence; onProgress?.(status.progress); }
        if (status.progress.terminal) return;
      } catch (error) {
        if (stopped) return;
        // A status GET can race the POST reservation. Other failures do not
        // trigger re-sending the paid/model-generating POST.
        if (!(error instanceof ApiError && error.status === 404 && tries <= 4)) return;
      }
      if (!stopped) timer = setTimeout(check, Math.min(1500 + tries * 100, 4000));
    };
    timer = setTimeout(check, 600);
    return { promise: send.promise.finally(stop), cancel() { stop(); send.cancel(); } };
  }
}
