// Scout-style discovery is separate from saved preparation targets and evidence.
const splitPrefs = id => $(id).value.split(",").map(v => v.trim()).filter(Boolean);

function discoveryPreferences() {
  const types = [];
  if ($("search-company").checked) types.push("company_roles");
  if ($("search-research").checked) types.push("research_programs");
  if (!types.length) throw new Error("Choose company roles, research programs, or both.");
  const roles = splitPrefs("search-query");
  if (!roles.length || roles.length > 5 || roles.some(role => role.length > 120)) {
    throw new Error("Enter 1–5 roles or interests, up to 120 characters each, separated by commas.");
  }
  return { roles, locations: splitPrefs("search-locations"),
    companies: splitPrefs("search-companies"), keywords: splitPrefs("search-keywords"),
    exclude_keywords: splitPrefs("search-exclude"), funding: $("search-funding").value,
    seniority: [$("search-level").value], opportunity_types: types,
    remote_ok: $("search-remote").checked, needs_visa_sponsorship: $("search-visa").checked,
    citizenship: $("search-citizenship").value.trim() || null };
}

async function refreshHunts() {
  const result = await api("/api/hunts");
  $("hunt-select").innerHTML = '<option value="">New search</option>' + result.hunts.map(h => '<option value="' + esc(h.id) + '">' + esc(h.name) + '</option>').join("");
  if (state.hunt) $("hunt-select").value = state.hunt.id;
  return result.hunts;
}

function loadHunt(hunt) {
  $("shortlist-section").dataset.empty = "false";
  state.hunt = hunt; state.listings = hunt.result?.listings || [];
  let savedSelection=[];
  try { savedSelection=JSON.parse(localStorage.getItem("scout-selection:"+hunt.id)||"[]"); } catch {}
  state.listingSelected = (Array.isArray(savedSelection) ? savedSelection : []).filter(id => state.listings.some(v => v.id === id)).slice(0,3);
  state.useHuntSelection = true;
  $("hunt-select").value = hunt.id;
  localStorage.setItem("scout-last-hunt", hunt.id);
  $("hunt-refresh").disabled = false;
  $("source-caption").textContent = "Matches require source evidence for your selected location and funding. Unconfirmed candidates have a separate view; source read dates are shown.";
  showStep("discover", "results");
  $("search-form").classList.remove("hidden");
  const p = hunt.preferences;
  if (Array.isArray(p?.roles)) {
    for (const [id, key] of [["search-query", "roles"], ["search-locations", "locations"], ["search-companies", "companies"], ["search-keywords", "keywords"], ["search-exclude", "exclude_keywords"]]) {
      $(id).value = (p[key] || []).join(", ");
    }
    $("search-funding").value = p.funding || "any";
    $("search-level").value = p.seniority?.[0] || "internship";
    $("search-citizenship").value = p.citizenship || "";
    $("search-company").checked = (p.opportunity_types || []).includes("company_roles");
    $("search-research").checked = (p.opportunity_types || []).includes("research_programs");
    $("search-remote").checked = !!p.remote_ok;
    $("search-visa").checked = !!p.needs_visa_sponsorship;
  }
  renderScoutCards(); updateSelected();
}

let listingRenderSequence = 0;
async function renderScoutCards() {
  const view = $("listing-view").value;
  const query = $("listing-text").value.trim().toLowerCase();
  const visa = $("listing-visa").value;
  const funding = $("listing-funding").value;
  let listings;
  const request = ++listingRenderSequence;
  if (!state.hunt) { listings = []; }
  else {
    const params = new URLSearchParams({view, sort: $("listing-sort").value, q: query, min_score: $("listing-score").value});
    if (state.category !== "All") params.set("kind", state.category === "Research" ? "program" : "job");
    if (visa) params.set("visa", visa);
    if (funding) params.set("funding", funding);
    try {
      const result = await api("/api/hunts/" + state.hunt.id + "/listings?" + params);
      if (request !== listingRenderSequence) return;
      listings = result.listings;
    } catch (error) {
      if (request === listingRenderSequence) notify(error.message, true);
      return;
    }
  }
  // Preserve the API's verified ordering and date-precision handling.
  $("result-count").textContent = listings.length + (view === "review" ? " unconfirmed" : " result" + (listings.length === 1 ? "" : "s"));
  if (!listings.length) {
    const message = view === "saved" ? "Save a listing to keep it here." : view === "hidden" ? "Listings you hide will appear here." : view === "review" ? "No unconfirmed candidates in this view." : "No retrieved source currently confirms all selected filters. View unconfirmed coverage or inspect source gaps; requirements were not relaxed.";
    $("opportunity-cards").innerHTML = '<div class="empty-state"><span class="empty-icon" aria-hidden="true">↗</span><h3>' + (view === 'review' ? 'Unconfirmed coverage' : 'No matches in this view yet.') + '</h3><p>' + esc(message) + '<br>Your selected targets and other hunts stay separate.</p></div>';
    return;
  }
  $("opportunity-cards").innerHTML = listings.map(v => {
    const selected = state.listingSelected.includes(v.id);
    const evidence = (v.requirements || []).filter(f => f.status === "known" && f.excerpt);
    const constraintEvidence = Object.entries(v.filter_evidence || {}).flatMap(([name, quotes]) => quotes.map(excerpt => ({name,excerpt})));
    const filterStatus = {match:"Selected filters supported",needs_review:"Selected filters unconfirmed",excluded:"Outside selected filters"}[v.constraint_status] || "Selected filters unconfirmed";
    const opening = {open: "Applications open", closed: "Closed", future: "Future opening", unknown: "Opening unconfirmed"}[v.call_status] || "Opening unconfirmed";
    const visa = {sponsors: "Visa support stated", not_sponsored: "No visa sponsorship", citizens_only: "Citizenship restrictions", unknown: "Visa support unknown"}[v.visa_status];
    const funding = {fully_funded: "Stipend + accommodation + round-trip travel", paid: "Paid / stipend", unpaid: "Unpaid", unknown: "Funding unknown"}[v.funding_level];
    const review = {pending:"Detail review pending",complete:"Visible requirements reviewed",cached:"Reused requirement review",partial:"Requirements partly reviewed",failed:"Detail review unavailable"}[v.enrichment_status] || "Detail review pending";
    const fitMode = {rules:"Rule estimate",groq:"AI role review",cached:"Reused role review"}[v.score_mode] || "Rule estimate";
    const required = evidence.filter(f=>f.kind === "requirement");
    const preferred = evidence.filter(f=>f.kind === "preference");
    const requirementLabels = facts => facts.map(f=>Array.isArray(f.value) ? f.value.join(", ") : typeof f.value === "string" ? f.value : f.name.replaceAll("_"," ")).join("; ");
    const requirementSummary = '<div class="card-facts"><div><b>' + esc(review) + '</b><span>Required: ' + esc(requirementLabels(required) || "Not yet confirmed") + '</span><span>Preferred: ' + esc(requirementLabels(preferred) || "Not yet confirmed") + '</span></div></div>';
    const fitParts = Object.entries(v.score_breakdown || {}).map(([name,value])=>name + ": " + value).join(" · ");
    return '<article class="card ' + (selected ? "selected" : "") + '"><div class="card-top"><div class="org-icon" aria-hidden="true">' + esc(v.organization.slice(0,3).toUpperCase()) + '</div><div class="card-title"><h3>' + esc(v.title) + '</h3><div class="card-sub">' + esc(v.organization) + ' · ' + esc(v.locations.join(", ") || "Location unknown") + '<br>' + esc(v.kind === "program" ? "Research" : "Company") + ' · ' + esc(v.cycle) + '</div></div><span class="badge" title="' + esc(fitMode + '; ' + fitParts + '; advisory ranking, not selection probability') + '">Preference fit<br>' + esc(v.score) + '/100</span></div>' +
      '<div class="filter-status '+esc(v.constraint_status)+'">' + esc(filterStatus) + '</div><p class="card-summary">' + esc(v.summary || "Inspect source evidence before relying on these labels.") + '</p><div class="listing-labels"><span>' + esc(opening) + '</span><span>' + esc(visa) + '</span><span>' + esc(funding) + '</span>' + (v.is_new ? '<span>New this hunt</span>' : '') + (v.verification === "uncertain" ? '<span>Unverified observation</span>' : '') + '</div><div class="card-facts"><div><b>Deadline · original wording</b><span>' + esc(v.deadline_text || "Not stated / unknown") + ' <small>(' + esc(v.deadline_precision) + ')</small></span></div><div><b>Funding · check covered costs</b><span>' + esc(v.funding_note || "Coverage and fees need source review.") + '</span></div></div>' +
      requirementSummary + '<details class="listing-evidence"><summary>Filter evidence & source details · ' + (evidence.length + constraintEvidence.length) + ' excerpts</summary><p>' + esc(fitMode + (fitParts ? " · " + fitParts : "")) + '</p><ul>' + [...(v.constraint_reasons || []), ...(v.reasons || [])].map(r=>'<li>'+esc(r)+'</li>').join("") + '</ul>' + constraintEvidence.map(f=>'<div><b>'+esc(f.name.replaceAll('_',' '))+'</b><blockquote>'+esc(f.excerpt)+'</blockquote></div>').join('') + evidence.map(f=>'<div><b>'+esc(f.name.replaceAll("_"," "))+' · '+esc(f.kind)+'</b><blockquote>'+esc(f.excerpt)+'</blockquote></div>').join("") + '</details><div class="card-foot"><div><a class="source-link" href="' + esc(safeUrl(v.apply_url)) + '" target="_blank" rel="noopener noreferrer">View posting / application ↗</a><div class="checked">' + esc(v.found_via.toUpperCase()) + ' · Read ' + esc(dateLabel(v.checked_at)) + '</div></div><button class="select-btn ' + (selected ? 'chosen' : '') + '" data-listing="' + esc(v.id) + '" aria-pressed="' + selected + '">' + (selected ? '✓ Selected' : '+ Prepare for this') + '</button></div><div class="listing-actions"><div><button class="text-btn" data-save="' + esc(v.id) + '" aria-pressed="' + !!v.saved + '">' + (v.saved ? 'Unsave' : 'Save') + '</button><button class="text-btn" data-hide="' + esc(v.id) + '">' + (v.hidden ? 'Unhide' : 'Hide') + '</button></div><span class="fit-disclaimer">Funding and location checked separately</span></div></article>';
  }).join("");
  $("opportunity-cards").querySelectorAll("[data-listing]").forEach(b=>b.onclick=()=>toggleListing(b.dataset.listing));
  for (const [attribute,field] of [["save","saved"],["hide","hidden"]]) {
    $("opportunity-cards").querySelectorAll("[data-"+attribute+"]").forEach(b=>b.onclick=()=>action("Saving this hunt preference…",async()=>{
      const listing=state.listings.find(v=>v.id===b.dataset[attribute]);
      const flags={saved:listing.saved,hidden:listing.hidden}; flags[field]=!flags[field];
      await api("/api/hunts/"+state.hunt.id+"/listings/"+listing.id+"/flags",flags);
      Object.assign(listing,flags); renderScoutCards();
    }));
  }
}

function toggleListing(id) {
  if (state.listingSelected.includes(id)) state.listingSelected=state.listingSelected.filter(v=>v!==id);
  else if (state.listingSelected.length<3) state.listingSelected.push(id);
  else { notify("Select at most three targets for one preparation plan.",true); return; }
  localStorage.setItem("scout-selection:"+state.hunt.id,JSON.stringify(state.listingSelected));
  renderScoutCards(); updateSelected();
}

async function prepareSelectedListings() {
  const key = state.hunt.id + ":" + [...state.listingSelected].sort().join(",");
  if (state.plan && [...state.plan.selected_ids].sort().join(",") === [...state.listingSelected].sort().join(",") &&
      state.plan.selected_ids.every(id => state.opportunities.some(o => o.id === id && o.discovery?.apply_url))) {
    state.selected = state.plan.selected_ids;
    state.preparedSelection = key;
  }
  if (state.preparedSelection === key && state.selected.length && state.selected.every(id => state.opportunities.some(o => o.id === id))) return;
  const result=await api("/api/hunts/"+state.hunt.id+"/select",{listing_ids:state.listingSelected});
  const map=new Map(state.opportunities.map(v=>[v.id,v]));
  result.opportunities.forEach(v=>map.set(v.id,v)); state.opportunities=[...map.values()];
  state.selected=result.selected_ids;
  state.preparedSelection=key;
  state.enrichmentWarnings=result.enrichment_warnings || [];
  // Planning references only explicit graph targets, never unselected search results.
}

async function watchRun(run) {
  $("discovery-trace").classList.remove("hidden");
  $("discovery-trace").open=false;
  const started=Date.now();
  let lastUpdate="";
  while (true) {
    paintRun(run);
    const update=String(run.updated || "") + ":" + run.listing_count;
    if (["queued", "running"].includes(run.status) && run.listing_count > 0 && update !== lastUpdate) {
      loadHunt(await api("/api/hunts/"+run.hunt));
      lastUpdate=update;
    }
    if (!["queued","running"].includes(run.status)) break;
    if(Date.now()-started>6*60*1000){
      notify("This run is taking longer than expected. It may still be active; reopen this hunt to check status. No duplicate run was started.",true);
      return;
    }
    await new Promise(resolve=>setTimeout(resolve,1800));
    run=await api("/api/discovery-runs/"+run.id);
  }
  if (run.error) {
    $("discovery-trace").open=true;
    // A failed rerun can retain earlier records as uncertain. Read that current
    // state before displaying the failure, rather than leaving stale labels up.
    loadHunt(await api("/api/hunts/"+run.hunt));
    await refreshHunts();
    throw new Error(run.error);
  }
  loadHunt(await api("/api/hunts/"+run.hunt));
  await refreshHunts();
  const incomplete = ["partial", "failed", "interrupted"].includes(run.status);
  if (incomplete) $("discovery-trace").open=true;
  notify(incomplete ? "Some sources or processing steps need review. Your available results are below; unknowns stay visible." : "Source reading is complete. Review matches and optional unconfirmed candidates, select targets, then set your preparation time.",incomplete);
  $("shortlist-section").scrollIntoView({ block: "start" });
}

function paintRun(run) {
  setStoryStage("results");
  $("run-progress").classList.remove("hidden");
  $("discovery-trace").classList.remove("hidden");
  const events = run.events || [];
  const sequence = ["search", "fetch", "extract", "match"];
  const stageFor = stage => stage === "feed" || stage === "recheck" || stage === "agent" ? "fetch" : stage;
  const logged = new Set(events.map(event => stageFor(event.stage)));
  const latest = [...events].reverse().find(event => sequence.includes(stageFor(event.stage)));
  const active = ["queued", "running"].includes(run.status);
  document.querySelectorAll("#run-stages [data-stage]").forEach(item => {
    const observed = logged.has(item.dataset.stage);
    const current = active && latest && stageFor(latest.stage) === item.dataset.stage;
    item.classList.toggle("logged", observed);
    item.classList.toggle("current", !!current);
    item.querySelector("small").textContent = current ? "Active stage" : observed ? "Activity logged" : active ? "Waiting" : "No activity logged";
  });
  const titles = {queued: "Your search is in the queue.", running: "Finding and reading possibilities.", completed: "Your shortlist is ready.", partial: "Results are ready, with gaps.", failed: "This run could not finish.", interrupted: "This run was interrupted."};
  $("run-progress-title").textContent = titles[run.status] || "Check this run’s status.";
  if (!active && run.listing_count === 0 && ["completed", "partial"].includes(run.status)) {
    $("run-progress-title").textContent = run.status === "partial" ? "No usable listings verified in this run." : "No matching listings found in this run.";
  }
  $("run-status-label").textContent = run.status.replaceAll("_", " ");
  const notes = events.filter(event => event.stage === "warning").length;
  $("run-coverage").textContent = active ? "Candidates appear first, then sourced requirements and preference fit update. Location and funding require separate source evidence." : run.status === "completed" ? "Review extracted requirements and filter evidence, then select targets. Preference fit is an advisory ranking." : (notes ? notes + " source or processing note" + (notes === 1 ? "" : "s") + " reported. " : "") + "Retrieved leads remain available; incomplete requirements stay visible.";
  $("run-state").textContent="Run "+run.id.slice(0,8)+" · "+run.status;
  $("run-events").innerHTML=events.map(e=>'<div><b>'+esc(e.stage.toUpperCase())+'</b> '+esc(e.message)+(e.url?' <a href="'+esc(safeUrl(e.url))+'" target="_blank" rel="noopener noreferrer">source ↗</a>':'')+'</div>').join("");
}

$("search-form").onsubmit=e=>{e.preventDefault();action("Starting your preference-driven discovery hunt…",async()=>{
  showStep("discover");
  const result=await api("/api/hunts",{preferences:discoveryPreferences()});
  state.listingSelected=[]; loadHunt(result.hunt); await refreshHunts(); await watchRun(result.run);
});};
$("hunt-refresh").onclick=()=>action("Re-running the same hunt with live sources…",async()=>watchRun(await api("/api/hunts/"+state.hunt.id+"/runs",{})));
$("hunt-open").onclick=()=>action("Opening your saved discovery hunt…",async()=>{
  const id=$("hunt-select").value;if(!id)throw new Error("Choose a saved hunt first.");
  state.listingSelected=[];loadHunt(await api("/api/hunts/"+id));
});
$("listing-view").onchange=()=>{if(state.useHuntSelection)renderScoutCards();};
for (const id of ["listing-sort", "listing-visa", "listing-funding", "listing-score"]) $(id).onchange = () => { if (state.useHuntSelection) renderScoutCards(); };
$("listing-text").oninput = () => { if (state.useHuntSelection) renderScoutCards(); };

function closeExplorer() {
  $("interest-explorer").classList.add("hidden");
  $("explore-btn").setAttribute("aria-expanded", "false");
}
function showSearch(focus = true) {
  closeExplorer();
  showStep("discover", "search");
  $("search-form").classList.remove("hidden");
  if (focus) {
    $("search-form").scrollIntoView({ block: "center" });
    $("search-query").focus({ preventScroll: true });
  }
}
$("known-interests-btn").onclick=()=>showSearch();
if ($("empty-search-btn")) $("empty-search-btn").onclick=()=>showSearch();
$("search-back-btn").onclick=()=>goStory("start");
$("edit-search-btn").onclick=()=>showSearch();
$("resume-hunt-btn").onclick=()=>{showStep("discover","results");$("saved-searches").open=true;};
$("resume-plan-btn").onclick=()=>goStory("roadmap");
$("view-evidence-btn").onclick=()=>goStory("evidence");
$("edit-time-btn").onclick=()=>goStory("time");
$("evidence-back-btn").onclick=()=>goStory("roadmap");
document.querySelectorAll("[data-story-nav]").forEach(button=>button.onclick=()=>goStory(button.dataset.storyNav));
async function restoreScout() {
  const hunts=await refreshHunts();
  if(state.hunt || busy)return;
  const id=localStorage.getItem("scout-last-hunt");
  const found=hunts.find(h=>h.id===id);
  if(!found)return;
  const hunt=await api("/api/hunts/"+id);
  if(state.hunt || busy)return;
  loadHunt(hunt);
  if(found.latest_run){
    const run=await api("/api/discovery-runs/"+found.latest_run);
    if(["queued","running"].includes(run.status))await action("Recovering this discovery run…",()=>watchRun(run));
    else paintRun(run);
  }
}
restoreScout().catch(error=>notify("Saved hunt could not be restored: "+error.message,true));
