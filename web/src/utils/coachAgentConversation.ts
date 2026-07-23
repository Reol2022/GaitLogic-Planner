import type { CoachConversationMessage, CoachQueryResponse } from "@/types/coachAgent";

export const MAX_COACH_TURNS = 8;
const MAX_CONTEXT_CHARS = 6000;
const MAX_CONTEXT_ITEM_CHARS = 900;

export interface CoachConversationTurn {
  id: string;
  question: string;
  response: CoachQueryResponse;
}

export interface CoachConversationContextResult {
  messages: CoachConversationMessage[];
  trimmed: boolean;
}

export function buildCoachConversationContext(
  turns: CoachConversationTurn[],
): CoachConversationContextResult {
  const candidates: CoachConversationMessage[] = turns.flatMap((turn) => {
    const assistant = turn.response.summary || turn.response.answer || "本轮未返回可展示正文。";
    return [
      { role: "user" as const, content: turn.question.slice(0, MAX_CONTEXT_ITEM_CHARS) },
      { role: "assistant" as const, content: assistant.slice(0, MAX_CONTEXT_ITEM_CHARS) },
    ];
  });
  const messages: CoachConversationMessage[] = [];
  let total = 0;
  for (const item of [...candidates].reverse()) {
    if (total + item.content.length > MAX_CONTEXT_CHARS) break;
    messages.unshift(item);
    total += item.content.length;
  }
  return { messages, trimmed: messages.length < candidates.length };
}

export function appendCoachTurn(
  turns: CoachConversationTurn[],
  turn: CoachConversationTurn,
): { turns: CoachConversationTurn[]; trimmed: boolean } {
  const next = [...turns, turn];
  return {
    turns: next.slice(-MAX_COACH_TURNS),
    trimmed: next.length > MAX_COACH_TURNS,
  };
}
