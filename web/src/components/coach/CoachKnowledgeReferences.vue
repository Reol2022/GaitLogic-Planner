<template>
  <section
    v-if="references.length"
    class="knowledge-references"
    aria-labelledby="coach-knowledge-title"
  >
    <header>
      <div>
        <span>Canonical Knowledge References</span>
        <h2 id="coach-knowledge-title">训练知识依据</h2>
      </div>
      <strong>{{ references.length }} 条引用</strong>
    </header>

    <ol>
      <li v-for="(reference, index) in references" :key="referenceKey(reference, index)">
        <div class="reference-heading">
          <span>{{ index + 1 }}</span>
          <div>
            <h3>{{ reference.title }}</h3>
            <p>{{ reference.section }} · {{ reference.source_title }}</p>
          </div>
        </div>
        <div class="reference-meta">
          <span>{{ evidenceLabel(reference.evidence_level) }}</span>
          <span>知识版本 {{ reference.knowledge_version }}</span>
        </div>
        <details>
          <summary>查看知识摘录</summary>
          <p class="excerpt">{{ reference.excerpt }}</p>
          <div v-if="reference.limitations.length" class="reference-limitations">
            <strong>适用限制</strong>
            <ul>
              <li v-for="item in reference.limitations" :key="item">{{ item }}</li>
            </ul>
          </div>
        </details>
      </li>
    </ol>
    <p class="boundary-note">
      训练知识用于解释公开训练原则，不构成医疗诊断，也不会覆盖确定性训练建议。
    </p>
  </section>
</template>

<script setup lang="ts">
import type {
  CoachKnowledgeEvidenceLevel,
  CoachKnowledgeReference,
} from "@/types/coachAgent";
import { coachKnowledgeEvidenceDisplay } from "@/utils/coachAgentDisplay";

withDefaults(defineProps<{ references?: CoachKnowledgeReference[] }>(), {
  references: () => [],
});

function evidenceLabel(level: CoachKnowledgeEvidenceLevel): string {
  return coachKnowledgeEvidenceDisplay[level];
}

function referenceKey(reference: CoachKnowledgeReference, index: number): string {
  return `${reference.document_id}-${reference.knowledge_version}-${index}`;
}
</script>

<style scoped>
.knowledge-references {
  min-width: 0;
  padding: 17px;
  border: 1px solid #cfddea;
  border-radius: var(--card-radius);
  background: #fff;
  box-shadow: var(--card-shadow);
}
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}
header span { color: #527493; font-size: 11px; font-weight: 700; }
h2 { margin: 3px 0 0; color: #172033; font-size: 17px; }
header > strong {
  flex: 0 0 auto;
  padding: 5px 8px;
  border-radius: 999px;
  color: #1f5d49;
  background: #eaf6ef;
  font-size: 11px;
}
ol { display: grid; gap: 11px; margin: 14px 0 0; padding: 0; list-style: none; }
ol > li {
  min-width: 0;
  padding: 13px;
  border: 1px solid #e1e8ef;
  border-radius: 8px;
  background: #fbfcfd;
}
.reference-heading { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 9px; }
.reference-heading > span {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  color: #fff;
  background: #426e92;
  font-size: 11px;
  font-weight: 700;
}
h3 { margin: 1px 0 0; overflow-wrap: anywhere; color: #26354a; font-size: 14px; }
.reference-heading p {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  color: #667085;
  font-size: 12px;
}
.reference-meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.reference-meta span {
  padding: 4px 7px;
  border-radius: 5px;
  color: #4e6073;
  background: #eef3f7;
  font-size: 11px;
}
details { min-width: 0; }
summary { cursor: pointer; color: #315f88; font-size: 12px; font-weight: 700; }
summary:focus-visible { outline: 3px solid rgba(25, 118, 210, .3); outline-offset: 3px; }
.excerpt {
  margin: 9px 0 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  color: #344054;
  font-size: 13px;
  line-height: 1.7;
}
.reference-limitations { margin-top: 10px; padding: 9px 10px; background: #fff8e8; }
.reference-limitations strong { color: #76540f; font-size: 12px; }
.reference-limitations ul { display: grid; gap: 4px; margin: 6px 0 0; padding-left: 18px; }
.reference-limitations li { overflow-wrap: anywhere; color: #6b5a36; font-size: 12px; }
.boundary-note { margin: 12px 0 0; color: #667085; font-size: 11px; line-height: 1.6; }
@media (max-width: 520px) {
  .knowledge-references { padding: 14px; }
  header { align-items: stretch; flex-direction: column; }
  header > strong { align-self: flex-start; }
}
</style>
