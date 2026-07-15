# Architecture relationship

The public product repository contains the running frontend and backend, reusable runner-state and training-knowledge data structures, generic rule-engine and plan-validation frameworks, dynamic-adjustment framework, agent-tool interfaces, anonymous fixtures, and public API documentation.

The private competition repository contains only competition-specific work products and references a product commit through a manifest. It must not copy the product source tree. No competition-specific business implementation is implied by this document.

Runner State Model v1 is a public product capability. It calculates an on-demand,
non-persistent snapshot from the authenticated runner's canonical training plan
and workout-log records. Garmin and other provider activities enter the model
only after the existing normalization, resolution, and workout-log merge flow;
competition data and competition-specific thresholds are not part of this layer.
