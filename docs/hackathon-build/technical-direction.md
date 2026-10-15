# Technical direction

Status: original technical proposal preserved; implementation and tests now exist. See ../verification.md.
Reviewed October 15, 2026.

## Proposed baseline

[Likely] Use Python/FastAPI with the official FalkorDB Python client, a lightweight
web interface, and one tool-calling LLM. Start with an explicit domain graph and
4–6 tools. This reduces integration work and makes query behavior easy to verify.
Exact choices remain dependent on the product idea.

[Certain] Official Python APIs include graph selection, parameterized query calls,
read-only queries and per-query timeouts. Async APIs also exist.
Sources: [client](https://github.com/FalkorDB/falkordb-py),
[query implementation](https://github.com/FalkorDB/falkordb-py/blob/main/falkordb/graph.py).

## Agent boundary

[Likely] Each tool should own a fixed Cypher query or a small vetted query family,
typed arguments, bounded traversal depth, row limits and a timeout.
The model selects tools and explains returned evidence. It should not invent edges,
unresolved entity IDs or facts outside tool results.

Use read-only graph queries for retrieval. Explicit write tools record observations,
decisions or simulated domain actions with source IDs and timestamps.
Return source/evidence IDs, traversed paths and the graph/context version.
[Certain] GRAPH.RO_QUERY rejects writes.
Source: [read-only command](https://docs.falkordb.com/commands/graph.ro_query).

A plausible tool list is resolve_entity, gather_context, evaluate_options,
explain_path, record_decision and apply_simulated_action.
These are design shapes, not finalized features.

## Graph design

[Likely] Begin from the questions and decisions; then define entities and relationships.
Use stable domain IDs, explicit relationship direction and types, source provenance,
validity timestamps where context changes, and idempotent seed/write operations.

Create property indexes deliberately where queries need them.
[Certain] Cypher and graph algorithms are documented; index availability is explicit.
Sources: [Cypher](https://docs.falkordb.com/cypher),
[indexes](https://docs.falkordb.com/cypher/indexing/range-index),
[algorithms](https://docs.falkordb.com/algorithms/).

An evidence path supports a claim that the graph recorded a relationship; it does not
alone prove that a source is true or that the agent's entire conclusion is correct.
Correctness needs expected outcomes, data provenance and missing-data behavior.

## Persistence and isolation

[Certain] Official Docker examples conflict on the persistence mount path:
some use /data, while the repository README and dedicated persistence documentation
use /var/lib/falkordb/data. Pin an image, inspect its data directory, and verify a
restart before claiming persistent memory.
Sources: [Docker](https://docs.falkordb.com/operations/docker),
[persistence](https://docs.falkordb.com/operations/durability/persistence),
[repository](https://github.com/FalkorDB/FalkorDB).

[Certain] Graph names separate data graphs; authorization requires command and graph
permissions. Do not accept a user-supplied tenant graph name without access checks.
Source: [ACL](https://docs.falkordb.com/commands/acl).
[Likely] Use one synthetic demo tenant initially unless isolation is a required proof point.

## GraphRAG SDK decision

[Certain] The SDK includes document ingestion, extraction, deduplication, embeddings,
retrieval, citations and document updates. Text-to-Cypher is described as experimental.
Sources: [SDK](https://github.com/FalkorDB/GraphRAG-SDK),
[architecture](https://github.com/FalkorDB/GraphRAG-SDK/blob/main/docs/architecture.md).

[Likely] Use it only if unstructured ingestion is core. Direct graph modeling is simpler
for structured constraints and deterministic demo cases. SDK docs show schema/version
differences; pin one release and check its actual source before using example names.

## LLM provider

[Certain] Groq has a Free tier and documented tool calling. Organization/model rate
limits apply; hitting them returns HTTP 429 with retry guidance. Exact account limits
and available models must be checked when the API is connected.
Sources: [billing](https://console.groq.com/docs/billing-faqs),
[limits](https://console.groq.com/docs/rate-limits),
[tools](https://console.groq.com/docs/tool-use/overview).

[Likely] Keep provider/model configurable, context compact and tool rounds bounded.
Handle retry-after, timeouts and unavailable models. A graph-only/replay fallback
must be labeled clearly so it is never presented as a live LLM run.
No paid account change or LLM request was made.

## First validation spike after idea selection

1. Check Docker/runtime availability and choose pinned versions.
2. Seed a tiny representative graph with a non-obvious multi-hop relationship.
3. Run the decisive parameterized query against real FalkorDB; check expected paths.
4. Change one edge and verify the decision changes.
5. Connect one real LLM tool call and verify its arguments/evidence.
6. Restart storage and check persistence where claimed.

Failures in this spike trigger scope changes before building the full interface.

## Existing sponsor baseline

[Certain] Graphiti MCP already provides persistent memory; CodeGraph already handles
code relationships and impact; QueryWeaver and Text-to-Cypher already expose graph-aware
query tools.
Sources: [Graphiti](https://docs.falkordb.com/agentic-memory/graphiti-mcp-server),
[CodeGraph](https://github.com/FalkorDB/code-graph),
[QueryWeaver](https://github.com/FalkorDB/QueryWeaver),
[Text-to-Cypher](https://github.com/FalkorDB/text-to-cypher).

[Likely] Differentiation must come from a new user decision, useful action, changed-context
handling or measured correctness, not simply an existing SDK behind a new interface.

