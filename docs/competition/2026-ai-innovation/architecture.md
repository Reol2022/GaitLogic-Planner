# Architecture relationship

The public product repository contains the running frontend and backend, reusable runner-state and training-knowledge data structures, generic rule-engine and plan-validation frameworks, dynamic-adjustment framework, agent-tool interfaces, anonymous fixtures, and public API documentation.

The private competition repository contains only competition-specific work products and references a product commit through a manifest. It must not copy the product source tree. No competition-specific business implementation is implied by this document.

Runner State Model v1 is a public product capability. It calculates an on-demand,
non-persistent snapshot from the authenticated runner's canonical training plan
and workout-log records. Garmin and other provider activities enter the model
only after the existing normalization, resolution, and workout-log merge flow;
competition data and competition-specific thresholds are not part of this layer.

Runner State Inference v1 is also a public product capability layered on the
Foundation snapshot. It adds versioned, validated heuristic configuration,
an independent previous-21-day baseline, deterministic volume trend,
consistency and fatigue-signal inference, and traceable Evidence/Reason Codes.
It does not infer fitness, modify plans, persist snapshots, or call a language
model. Real-user evaluation, competition experiments, private tuning parameters,
survey responses and presentation materials remain exclusively in the private
competition repository.

Runner State Presentation v1 is the public product display layer for the
on-demand current snapshot. It maps the existing authenticated current-state
GET response into human-readable status cards, deterministic summary copy,
traceable Evidence, data-quality details and responsive layouts. Refreshing the
page does not save a snapshot or write to the database. Historical snapshots,
real-user screenshots, private demonstrations, interview findings and
competition evaluation results are outside this public presentation layer.
