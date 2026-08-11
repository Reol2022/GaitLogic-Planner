# MCP Evaluation

`python scripts/evaluate_agent.py --suite mcp` uses the existing unified registry and runs the real offline MCP regression tests. The 45 fixed public checks cover discovery, calls, identity, transports, resources, prompts, RAG safety, observability and read-only behavior. The versioned baseline is human-maintained, never overwritten by the runner.
