# Architecture relationship

The public product repository contains the running frontend and backend, reusable runner-state and training-knowledge data structures, generic rule-engine and plan-validation frameworks, dynamic-adjustment framework, agent-tool interfaces, anonymous fixtures, and public API documentation.

The private competition repository contains only competition-specific work products and references a product commit through a manifest. It must not copy the product source tree. No competition-specific business implementation is implied by this document.
