"""
Sourced-assertion memory substrate for the agent framework.

Stack A' (SQLite + sqlite-vec + sentence-transformers + FastMCP) per the
Phase 3 tooling decision brief. Scoped initially to use case #1 — the
framework's own memory of agent discussions.

The atomic unit is the **sourced assertion**: subject, predicate, object,
plus a portable source_ref URI that always allows resurfacing the original
passage. Conclusions are not stored; only source-bound assertions.
"""
