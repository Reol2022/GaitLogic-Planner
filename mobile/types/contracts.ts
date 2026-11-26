export interface User { id: number; username: string; nickname?: string | null; role: string; status: string }
export interface Conversation { id: string; title: string; status: string; message_count: number }
export interface Message { id: string; role: string; content: string | null; status: string; sequence_no: number;
  warnings: Array<{ code: string; message: string }>; limitations: Array<{ code: string; message: string }> }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Progress { stage: string; sequence: number; terminal: boolean; summary: Array<{ code: string; message: string; count?: number | null }> }
export interface TurnStatus { message_status: string; client_turn_id: string; progress: Progress }
export interface MessageResult { conversation_id: string; message_id: string; status: string; content: string | null;
  response?: { warnings?: Array<{code: string; message: string}>; limitations?: Array<{code: string; message: string}> } | null }
