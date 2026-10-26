import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import CoachConversationList from "./CoachConversationList.vue";

const conversation = {
  id: "conversation-1",
  title: "读取本月训练并分析",
  status: "active" as const,
  created_at: "2026-10-01T08:00:00+08:00",
  updated_at: "2026-10-26T19:57:00+08:00",
  last_message_at: "2026-10-26T19:57:00+08:00",
  message_count: 4,
};

const stubs = {
  ElButton: { template: "<button @click='$emit(\"click\")'><slot /></button>" },
  ElIcon: { template: "<span><slot /></span>" },
  ElSkeleton: { template: "<div class='skeleton' />" },
};

describe("CoachConversationList", () => {
  it("presents conversation context and emits navigation actions", async () => {
    const wrapper = mount(CoachConversationList, {
      props: { items: [conversation], activeId: conversation.id },
      global: { stubs },
    });

    expect(wrapper.text()).toContain("训练对话");
    expect(wrapper.text()).toContain("读取本月训练并分析");
    expect(wrapper.text()).toContain("4 条消息");
    expect(wrapper.find(".conversation-item").classes()).toContain("active");

    await wrapper.find(".conversation-select").trigger("click");
    await wrapper.find('[aria-label="重命名会话"]').trigger("click");
    await wrapper.find('[aria-label="归档会话"]').trigger("click");
    await wrapper.find('[aria-label="删除会话"]').trigger("click");

    expect(wrapper.emitted("select")?.[0]).toEqual([conversation.id]);
    expect(wrapper.emitted("rename")?.[0]).toEqual([conversation.id, conversation.title]);
    expect(wrapper.emitted("archive")?.[0]).toEqual([conversation.id]);
    expect(wrapper.emitted("delete")?.[0]).toEqual([conversation.id]);
  });

  it("shows a useful empty state", () => {
    const wrapper = mount(CoachConversationList, {
      props: { items: [] },
      global: { stubs },
    });

    expect(wrapper.text()).toContain("还没有训练对话");
    expect(wrapper.text()).toContain("新建对话，开始分析你的训练");
  });
});
