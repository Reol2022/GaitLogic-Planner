import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AdaptiveProposalDiff from "./AdaptiveProposalDiff.vue";
import type { AdaptiveProposal } from "@/types/adaptivePlan";

const elementStubs = {
  ElTag: { template: "<span><slot /></span>" },
  ElAlert: { props: ["title"], template: "<div>{{ title }}</div>" },
  ElButton: {
    emits: ["click"],
    template: "<button @click='$emit(\"click\")'><slot /></button>",
  },
};

function mountProposal(status: AdaptiveProposal["status"] = "pending_approval") {
  return mount(AdaptiveProposalDiff, {
    props: { proposal: { ...proposal, status } },
    global: { stubs: elementStubs },
  });
}

const proposal: AdaptiveProposal = {
  id: 7,
  week_start: "2026-07-06",
  status: "pending_approval",
  proposal: {
    reason_codes: ["FICTIONAL_RULE"],
    warnings: ["虚构恢复关注提示"],
    limitations: [],
    changes: [{
      date: "2026-07-13",
      plan_id: 9,
      base_plan_version: 1,
      action: "reduce",
      before: { content: "轻松跑 10km", distance_km: 10, main_type: "easy" },
      after: { content: "轻松跑 8km", distance_km: 8, main_type: "easy" },
      reason: "依据虚构周事实保守减量。",
      rule_evidence: ["FICTIONAL_RULE"],
    }],
  },
  created_at: "2026-07-12T10:00:00+08:00",
  updated_at: "2026-07-12T10:00:00+08:00",
};

describe("AdaptiveProposalDiff", () => {
  it("shows before, after, reason, rule evidence and explicit human actions", () => {
    const wrapper = mountProposal();
    expect(wrapper.text()).toContain("原计划");
    expect(wrapper.text()).toContain("建议计划");
    expect(wrapper.text()).toContain("10.0 km");
    expect(wrapper.text()).toContain("8.0 km");
    expect(wrapper.text()).toContain("FICTIONAL_RULE");
    expect(wrapper.text()).toContain("确认并创建新计划版本");
    expect(wrapper.text()).toContain("拒绝并保留原计划");
  });

  it("does not show write actions after the proposal leaves pending state", () => {
    const wrapper = mountProposal("applied");
    expect(wrapper.text()).not.toContain("确认并创建新计划版本");
  });

  it("emits approve and reject without performing API calls itself", async () => {
    const wrapper = mountProposal();
    const buttons = wrapper.findAll("button");
    await buttons[0].trigger("click");
    await buttons[1].trigger("click");
    expect(wrapper.emitted("reject")).toHaveLength(1);
    expect(wrapper.emitted("approve")).toHaveLength(1);
  });
});
