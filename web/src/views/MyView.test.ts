import { flushPromises, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import MyView from "./MyView.vue";

vi.mock("@/api/dataSync", () => ({ listDataSyncProviders: vi.fn().mockRejectedValue(new Error("disabled")) }));

describe("MyView product entries", () => {
  it("exposes training-state and AI Coach pages through the My hub", async () => {
    const wrapper = shallowMount(MyView, {
      global: {
        stubs: {
          PageHeader: { template: "<header />" },
          RouterLink: { props: ["to"], template: "<a :data-path='to.path'><slot /></a>" },
          ElIcon: { template: "<i><slot /></i>" },
          ElCollapse: { template: "<div><slot /></div>" },
          ElCollapseItem: { template: "<div><slot /></div>" },
        },
      },
    });
    await flushPromises();
    const runnerLink = wrapper.findAll("a").find((link) => link.text().includes("训练状态"));
    expect(runnerLink).toBeDefined();
    expect(runnerLink?.attributes("data-path")).toBe("/runner-state");
    const coachLink = wrapper.findAll("a").find((link) => link.text().includes("AI 教练"));
    expect(coachLink).toBeDefined();
    expect(coachLink?.attributes("data-path")).toBe("/coach");
  });
});
