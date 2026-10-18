# Parallel implementation contract — October 16

User explicitly requested implementation with parallel agents and root integration.
New discovery contracts are in app/discovery/contracts.py; root owns them and the
engine/state/API/UI. Agents must not edit other agents' modules or shared contracts.
Reference Scout is a temporary read-only clone at the pinned pre-event commit.
New event code is authored here with behavioral provenance recorded in scout-parity.md.

- Source agent: app/discovery/urls.py and feeds.py; tests/test_discovery_sources.py.
  `canonical_url(str) -> str | None`, `classify_url(str) -> SourceLead | None`,
  `detect_ats(str) -> ATSRef | None` (ATSRef local dataclass includes board_url,
  feed_url, posting_url, readable, organization); `posting_links(WebPage) -> list[SourceLead]`,
  `parse_feed(ATSRef, WebPage) -> list[SourceLead] | None`.
- AI agent: app/discovery/ai.py, extract.py, ranking.py and own tests.
  `ListingExtractor(settings, transport=None).extract(WebPage, DiscoveryPreferences,
  context: SourceLead | None = None) -> ExtractionResult`; `rank_listings(preferences,
  listings, settings=None, transport=None) -> list[DiscoveryListing]`.
  Extract exact evidence into Fact requirements; unknown/unsupported data stays unknown.
  Groq structured JSON with validation, bounded retries/no invented fields; keep AI fit
  verdict plus deterministic Scout scoring and fallback. No live provider calls by agent.
- Bridge agent: app/discovery/bridge.py, app/recipes.py, tests/test_discovery_bridge.py.
  `listing_to_opportunities(DiscoveryListing, WebPage | None) -> list[Opportunity]`:
  supported adapters retained, generic typed requirements carried with source evidence;
  metadata stored in Opportunity.discovery. Skills share only exact reviewed recipe
  identities; no claimed competence from completion. No changes to graph.py/planner.py.
- Transport agent: app/discovery/provider.py, browser.py and own tests.
  `DiscoveryWebClient(settings, transport=None).search(SearchTask) -> list[SourceLead]`;
  `.fetch(list[str], format="markdown", ttl=0) -> tuple[list[WebPage], dict[str,str]]`.
  `BrowserFallback(settings, transport=None).find(SourceLead, preferences) -> list[SourceLead]`.
  Public-URL safety, bounded HTTP, cache-ready keys/goals, Agent run status recovery,
  no blind retry/cancel, error carries run ID where applicable. Root authorizes execution
  based on settings and budgets; no metered call by agent. Use current official API docs.

Root: engine.py (multi-wave pipeline), state.py (durable hunts/jobs/cache/usage),
main.py integration and UI, config settings, contract negotiation and final tests.
No successful old test repeated without concrete regression risk. No original Scout
repo edits, new account, purchase, publication or deployment. Per-run/daily ceilings
are enforced before provider calls; uncertain spending must remain a visible blocker.

## Discovery-failure repair ownership amendment

After the real Japan hunt failure, bounded source/collection and AI-throughput jobs
were authorized under the user's existing parallel-work request. Source job delivered
its engine/feed fixes and is completed. Root now owns engine integration and extract.py
for compact line-ID evidence/title normalization. The follow-up AI owner edits only
ai.py and test_discovery_ai_limits.py for separate output-token quotas/nonreasoning
mode; do not edit root's live extraction changes concurrently. Fresh browser-started
proof is required; partial cached Amazon proof is not this acceptance gate.
