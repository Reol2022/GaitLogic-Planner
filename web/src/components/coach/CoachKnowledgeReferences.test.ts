import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import CoachKnowledgeReferences from "./CoachKnowledgeReferences.vue";
import CoachKnowledgeStatus from "./CoachKnowledgeStatus.vue";
import { coachRagDemoFixtures } from "@/demo/coachRagDemo";
import type {
  CoachKnowledgeEvidenceLevel,
  CoachKnowledgeStatus as KnowledgeStatus,
} from "@/types/coachAgent";

describe("CoachKnowledgeReferences", () => {
  it("hides the whole reference block when no references exist", () => {
    expect(mount(CoachKnowledgeReferences).html()).toBe("<!--v-if-->");
  });

  it("renders multiple safe references with expandable excerpts and limitations", async () => {
    const references = coachRagDemoFixtures.general.knowledge_references ?? [];
    const wrapper = mount(CoachKnowledgeReferences, { props: { references } });
    expect(wrapper.text()).toContain("训练知识依据");
    expect(wrapper.text()).toContain("2 条引用");
    expect(wrapper.text()).toContain("专家共识");
    expect(wrapper.text()).toContain("二手资料");
    expect(wrapper.text()).toContain("知识版本 corpus-v1");
    expect(wrapper.text()).toContain("适用限制");
    expect(wrapper.findAll("details")).toHaveLength(2);
    expect(wrapper.findAll("details")[0].attributes("open")).toBeUndefined();
  });

  it.each([
    ["PRIMARY", "一手来源"],
    ["SECONDARY", "二手资料"],
    ["EXPERT_CONSENSUS", "专家共识"],
    ["INTERNAL", "系统内部说明"],
    ["UNKNOWN", "证据等级未知"],
  ] as Array<[CoachKnowledgeEvidenceLevel, string]>)(
    "maps %s to a public Chinese evidence label",
    (evidenceLevel, expected) => {
      const reference = {
        ...(coachRagDemoFixtures.general.knowledge_references ?? [])[0],
        evidence_level: evidenceLevel,
      };
      expect(mount(CoachKnowledgeReferences, {
        props: { references: [reference] },
      }).text()).toContain(expected);
    },
  );

  it("wraps long text, renders HTML as text, and never exposes internal fields", () => {
    const reference = {
      ...(coachRagDemoFixtures.general.knowledge_references ?? [])[0],
      title: "很长的虚构标题".repeat(20),
      excerpt: '<img src=x onerror="alert(1)">' + "很长的虚构摘录".repeat(80),
    };
    const wrapper = mount(CoachKnowledgeReferences, {
      props: { references: [reference] },
    });
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("<img src=x");
    const html = wrapper.html();
    for (const privateField of [
      "knowledge_1",
      "chunk_id",
      "retrieval_score",
      "filesystem_path",
      "embedding_vector",
      "provider",
    ]) {
      expect(html).not.toContain(privateField);
    }
  });
});

describe("CoachKnowledgeStatus", () => {
  it.each([
    ["USED", "已使用训练知识"],
    ["EMPTY", "未找到直接依据"],
    ["UNAVAILABLE", "训练知识暂时不可用"],
    ["DISABLED", "训练知识功能未启用"],
  ] as Array<[KnowledgeStatus, string]>)(
    "renders the friendly %s state",
    (status, expected) => {
      const wrapper = mount(CoachKnowledgeStatus, { props: { status } });
      expect(wrapper.text()).toContain(expected);
      expect(wrapper.text()).not.toContain("stack");
      expect(wrapper.text()).not.toContain("index_id");
    },
  );

  it("renders nothing for an old response with unknown status", () => {
    expect(mount(CoachKnowledgeStatus, {
      props: { status: null },
    }).html()).toBe("<!--v-if-->");
  });
});
