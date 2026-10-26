import { flushPromises, shallowMount } from "@vue/test-utils";
import { ElMessage, ElMessageBox } from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CoachConversationList from "@/components/coach/CoachConversationList.vue";
import CoachAgentView from "./CoachAgentView.vue";

const api = vi.hoisted(() => ({
  createCoachConversation: vi.fn(),
  deleteCoachConversation: vi.fn(),
  getCoachAgentErrorMessage: vi.fn(() => "请求失败"),
  getCoachConversationMessages: vi.fn(),
  getCoachConversationTurnStatus: vi.fn(),
  listCoachConversations: vi.fn(),
  sendCoachConversationMessage: vi.fn(),
  updateCoachConversation: vi.fn(),
}));

vi.mock("@/api/coachAgent", () => api);

const conversation = {
  id: "conversation-1",
  title: "昨天间歇练得怎么样？",
  status: "active" as const,
  created_at: "2026-10-01T08:00:00",
  updated_at: "2026-10-01T08:00:00",
  last_message_at: "2026-10-01T08:00:00",
  message_count: 2,
};

const stubs = {
  ElButton: { template: "<button @click='$emit(\"click\")'><slot /></button>" },
  ElInput: {
    props: ["modelValue", "disabled"],
    emits: ["update:modelValue", "keydown"],
    template: "<textarea :value='modelValue' :disabled='disabled' @input='$emit(\"update:modelValue\", $event.target.value)' />",
  },
  ElDrawer: { template: "<aside><slot /></aside>" },
  ElSkeleton: { template: "<div />" },
};

function mountPage() {
  return shallowMount(CoachAgentView, { global: { stubs } });
}

describe("CoachAgentView persistent chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listCoachConversations.mockResolvedValue({ items: [conversation], page: 1, page_size: 20, total: 1 });
    api.getCoachConversationMessages.mockResolvedValue({
      items: [{
        id: "message-1", role: "assistant", content: "虚构安全回答。", status: "completed", sequence_no: 2,
        evidence_refs: [], warnings: [], limitations: [], tool_calls: [], created_at: "2026-10-01T08:00:00",
      }], page: 1, page_size: 100, total: 1,
    });
    api.getCoachConversationTurnStatus.mockResolvedValue({
      conversation_id: conversation.id,
      message_id: "message-2",
      message_status: "completed",
      client_turn_id: "synthetic_turn",
      progress: { stage: "COMPLETED", sequence: 4, summary: [], terminal: true },
    });
  });

  it("restores the most recent persisted conversation without browser chat storage", async () => {
    const localSet = vi.spyOn(Storage.prototype, "setItem");
    const wrapper = mountPage();
    await flushPromises();
    expect(api.listCoachConversations).toHaveBeenCalledTimes(1);
    expect(api.getCoachConversationMessages).toHaveBeenCalledWith("conversation-1");
    expect(wrapper.text()).toContain("虚构安全回答。");
    expect(localSet).not.toHaveBeenCalled();
    localSet.mockRestore();
  });

  it("submits a message through the active persistent conversation", async () => {
    api.sendCoachConversationMessage.mockResolvedValue({
      conversation_id: conversation.id, message_id: "message-2", status: "completed", content: "虚构安全回答。",
    });
    const wrapper = mountPage();
    await flushPromises();
    const input = wrapper.find("textarea");
    await input.setValue("今天怎么练？");
    const form = wrapper.find("form");
    await form.trigger("submit");
    await flushPromises();
    expect(api.sendCoachConversationMessage).toHaveBeenCalledWith(
      conversation.id,
      "今天怎么练？",
      expect.any(String),
    );
  });

  it("renames a conversation through the existing protected update API", async () => {
    vi.spyOn(ElMessageBox, "prompt").mockResolvedValue(
      { value: "  十月赛前训练  ", action: "confirm" } as never,
    );
    vi.spyOn(ElMessage, "success").mockImplementation(() => ({ close: vi.fn() }) as never);
    api.updateCoachConversation.mockResolvedValue({ ...conversation, title: "十月赛前训练" });
    const wrapper = mountPage();
    await flushPromises();

    wrapper.findComponent(CoachConversationList).vm.$emit("rename", conversation.id, conversation.title);
    await flushPromises();

    expect(api.updateCoachConversation).toHaveBeenCalledWith(conversation.id, { title: "十月赛前训练" });
    expect(api.listCoachConversations).toHaveBeenCalledTimes(2);
  });
});
