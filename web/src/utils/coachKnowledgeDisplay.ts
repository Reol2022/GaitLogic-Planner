import type {
  CoachKnowledgeStatus,
  CoachQueryResponse,
} from "@/types/coachAgent";

const KNOWLEDGE_TOOL_NAME = "retrieve_training_knowledge";

export function resolveCoachKnowledgeStatus(
  response: CoachQueryResponse,
): CoachKnowledgeStatus | null {
  if ((response.knowledge_references?.length ?? 0) > 0) return "USED";

  const unavailable = response.limitations.some(
    (item) => item.code === "KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
  );
  const tool = response.tool_calls.find(
    (item) => item.tool_name === KNOWLEDGE_TOOL_NAME,
  );

  if (unavailable || (tool && tool.status !== "SUCCEEDED")) {
    return "UNAVAILABLE";
  }
  if (tool?.status === "SUCCEEDED") return "EMPTY";

  // An explicit empty collection is the v0.12 public contract. Its absence
  // identifies an older response, for which no knowledge state should be
  // invented by the client.
  if (response.knowledge_references !== undefined) return "DISABLED";
  return null;
}
