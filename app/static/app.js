const state = { opportunities: [], selected: [], category: "All", plan: null, mode: "official", impact: null, trace: [] };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = value => { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; } catch { return "#"; } };
const fact = (op, name) => op.facts?.find(f => f.name === name && f.status === "known");
const dateLabel = value => { if (!value) return "Unknown"; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }); };
const deadlineLabel = value => { if (!value) return "Unknown"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString("en-IN", {day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Kolkata"}) + " IST"; };
const hours = value => Number.isFinite(Number(value)) ? Number(value).toFixed(1).replace(/\.0$/, "") : "—";
let busy = false;

function notify(message, error = false) { $("notification").textContent = message; $("notification").className = "notification" + (error ? " error" : ""); }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  let body; try { body = await response.json(); } catch { throw new Error("The server returned an unreadable response."); }
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request could not complete.");
  return body;
}
async function action(label, fn) {
  if (busy) return;
  busy = true; notify(label);
  document.querySelectorAll("button").forEach(b => { b.dataset.wasDisabled = b.disabled ? "1" : "0"; b.disabled = true; });
  try { await fn(); } catch (e) { notify(e.message || "Could not complete this action.", true); }
  finally {
    busy = false;
    document.querySelectorAll("button").forEach(b => {
      if (b.dataset.wasDisabled !== undefined) { b.disabled = b.dataset.wasDisabled === "1"; delete b.dataset.wasDisabled; }
    });
    updateSelected(); if (state.plan) $("accept-btn").disabled = state.plan.status !== "proposed";
  }
}
function showStep(name) {
  for (const s of ["discover", "plan", "evidence"]) $(s + "-section").classList.toggle("hidden", s !== name);
  document.querySelectorAll(".step").forEach(b => b.classList.toggle("active", b.dataset.step === name));
  if (name === "evidence") renderEvidence();
}
function profile() {
  const existing = state.plan?.profile || {};
  return { ...existing, id: "demo-student", synthetic: true, country: "India", degree: "BTech",
           field: "computer_science", year: 3, total_years: 4, institution_type: "non_iit",
           weekly_hours: Number($("weekly-hours").value), start_date: $("start-date").value || "2026-10-19",
           horizon_weeks: 8, exam_weeks: $("exam-week").value ? [$("exam-week").value] : [],
           completed_task_ids: existing.completed_task_ids || [], received_events: existing.received_events || [] };
}
function normalizeMonday(input) {
  if (!input.value) return;
  const date = new Date(input.value + "T12:00:00Z");
  const shift = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - shift);
  input.value = date.toISOString().slice(0,10);
}
$("start-date").addEventListener("change", () => normalizeMonday($("start-date")));
$("exam-week").addEventListener("change", () => normalizeMonday($("exam-week")));

function renderCards() {
  renderSourceControls();
  const list = state.opportunities.filter(o => state.category === "All" || o.category === state.category);
  $("result-count").textContent = list.length + " opportunit" + (list.length === 1 ? "y" : "ies");
  if (!list.length) {
    $("opportunity-cards").innerHTML = '<div class="empty-state"><span class="empty-icon">↗</span><h3>No verified results yet.</h3><p>Try a more specific search or load sourced examples.<br>Missing requirements stay unknown.</p></div>';
    return;
  }
  $("opportunity-cards").innerHTML = list.map(o => {
    const selected = state.selected.includes(o.id);
    const deadline = fact(o, "application_deadline");
    const fee = fact(o, "fee_amount");
    const funding = fact(o, "funding");
    const cost = fee ? hours(fee.value) + " " + (fact(o,"fee_currency")?.value || "") + " fee" : funding ? "Benefits listed" : "Details unknown";
    const title = o.program || o.id;
    const initial = title.includes("EPFL") ? "EPFL" : title.includes("OIST") ? "OIST" : title.includes("Google") ? "G" : title.slice(0,3).toUpperCase();
    return '<article class="card ' + (selected ? "selected" : "") + '"><div class="card-top"><div class="org-icon ' + (title.includes("EPFL") ? "epfl" : "") + '">' + esc(initial) + '</div><div class="card-title"><h3>' + esc(title) + '</h3><div class="card-sub">' + esc(o.country) + ' · ' + esc(o.category) + ' · ' + esc(o.cycle) + '</div></div><span class="badge ' + esc(o.call_status) + '">' + esc(o.call_status === "unknown" ? "OPENING UNKNOWN" : o.call_status.toUpperCase()) + '</span></div><p class="card-summary">' + esc(o.summary || "Review eligibility and funding details at the official source. Selection is a preparation target, not an eligibility decision.") + '</p><div class="card-facts"><div><b>Application deadline</b><span>' + (deadline ? esc(deadlineLabel(deadline.value)) : "Unknown / not announced") + '</span></div><div><b>Funding & costs</b><span>' + esc(cost) + '</span></div><div><b>Evidence state</b><span>' + esc(o.verification || "partial") + '</span></div></div><div class="card-foot"><div><a class="source-link" href="' + esc(safeUrl(o.source_url)) + '" target="_blank" rel="noopener noreferrer">Official source ↗</a><div class="checked">' + esc(o.mode.toUpperCase()) + ' · Checked ' + esc(dateLabel(o.checked_at)) + '</div></div><button class="select-btn ' + (selected ? "chosen" : "") + '" data-select="' + esc(o.id) + '">' + (selected ? "✓ Selected" : "+ Add target") + '</button></div></article>';
  }).join("");
  $("opportunity-cards").querySelectorAll("[data-select]").forEach(b => b.onclick = () => toggleTarget(b.dataset.select));
}
function toggleTarget(id) {
  if (state.selected.includes(id)) state.selected = state.selected.filter(x => x !== id);
  else if (state.selected.length < 3) state.selected.push(id);
  else { notify("Choose up to three targets for a focused preparation plan.", true); return; }
  renderCards(); updateSelected();
}
function updateSelected() {
  $("selection-count").textContent = state.selected.length + " / 3";
  $("selected-list").innerHTML = state.selected.length ? state.selected.map(id => {
    const op = state.opportunities.find(o => o.id === id);
    return '<div class="selected-item"><i class="selected-dot"></i><span>' + esc(op?.program || id) + '</span><button data-remove="' + esc(id) + '" aria-label="Remove target">×</button></div>';
  }).join("") : '<p class="muted">Choose up to three opportunities.<br>Selection does not mean eligibility.</p>';
  $("selected-list").querySelectorAll("[data-remove]").forEach(b => b.onclick = () => toggleTarget(b.dataset.remove));
  $("plan-btn").disabled = busy || !state.selected.length;
  $("agent-btn").disabled = busy || !state.selected.length;
}

function renderSourceControls() {
  const unique = [...new Map(state.opportunities.map(o => [o.source_url, o])).values()];
  $("source-controls").classList.toggle("hidden", !unique.length);
  $("refresh-source").innerHTML = unique.map(o => '<option value="' + esc(o.source_url) + '">' + esc(o.program) + '</option>').join("");
}

$("refresh-btn").onclick = () => action("Refreshing the selected source and checking fact-level changes…", async () => {
  const result = await api("/api/refresh", {url: $("refresh-source").value});
  const all = await api("/api/opportunities"); state.opportunities = all.opportunities || [];
  renderCards();
  if (state.plan && state.mode === "official") {
    const latest = await api("/api/plan/latest");
    if (latest.plan) setPlan(latest.plan);
  }
  const impacts = [...(result.impacts || []), ...(result.uncertainty_impacts || []), ...(result.uncertainty_impact ? [result.uncertainty_impact] : [])];
  const changed = impacts.some(i => i.semantic_change);
  notify(result.errors?.length ? "Source refresh has gaps. Retained evidence is now marked uncertain: " + result.errors.join(" ") : changed ? "Source facts changed. Review a new preparation proposal; earlier evidence is preserved." : "Source refreshed. No semantic requirement change was found.", !!result.errors?.length);
});

function setPlan(plan, mode = "official") {
  state.plan = plan; state.mode = mode;
  state.selected = plan.selected_ids || state.selected;
  $("plan-empty").classList.add("hidden"); $("plan-content").classList.remove("hidden");
  $("next-action-text").textContent = plan.next_action || "Review your target requirements and resolve the unknowns.";
  $("plan-mode-note").textContent = mode === "simulation" ? "SIMULATION · Separate graph. Changed policy is illustrative; official source facts remain unchanged." : "Synthetic student · Real source facts · Preparation and eligibility are separate checks.";
  $("metric-effort").textContent = hours(plan.total_hours_low) + "–" + hours(plan.total_hours_high) + " h";
  $("metric-capacity").textContent = hours(plan.available_hours) + " h";
  const shared = plan.tasks.filter(t => t.category === "Shared" && t.status !== "completed");
  $("metric-shared").textContent = hours(shared.reduce((sum,t) => sum + t.hours_high, 0)) + " h";
  $("metric-state").textContent = plan.status.charAt(0).toUpperCase() + plan.status.slice(1);
  $("metric-version").textContent = "Version " + plan.id.slice(0,8);
  $("accept-btn").disabled = plan.status !== "proposed";
  $("plan-warnings").innerHTML = (plan.warnings || []).map(w => '<div class="warning">' + esc(w) + '</div>').join("");
  const weeks = Object.keys(plan.weekly_used || {});
  if (!weeks.length) {
    const start = new Date(plan.profile.start_date + "T12:00:00Z");
    for (let i=0;i<plan.profile.horizon_weeks;i++) { const date = new Date(start); date.setUTCDate(date.getUTCDate()+i*7); weeks.push(date.toISOString().slice(0,10)); }
  }
  $("timeline").innerHTML = weeks.map(week => {
    const exam = (plan.profile.exam_weeks || []).includes(week);
    const used = Number(plan.weekly_used?.[week] || 0), cap = exam ? 0 : plan.profile.weekly_hours;
    return '<div class="week-row ' + (exam ? "exam" : "") + '"><div class="week-title">' + esc(dateLabel(week)) + '<small>' + (exam ? "EXAMS · PROTECTED" : "PREPARATION WEEK") + '</small></div><div class="week-bar"><span style="width:' + (cap ? Math.min(100,used/cap*100) : 0) + '%"></span></div><div class="week-hours">' + hours(used) + " / " + hours(cap) + 'h</div></div>';
  }).join("");
  $("task-list").innerHTML = plan.tasks.map(t => '<article class="task"><button class="task-check ' + (t.status === "completed" ? "done" : "") + '" data-complete="' + esc(t.task_id) + '" ' + (t.waiting_for || t.status === "waiting" || t.status === "blocked" ? "disabled" : "") + ' aria-label="Mark synthetic preparation complete">' + (t.status === "completed" ? "✓" : "") + '</button><div class="task-main"><h4>' + esc(t.title) + '</h4><div class="task-meta"><span class="badge ' + (t.status === "waiting" || t.status === "blocked" ? "closed" : "") + '">' + esc(t.status.toUpperCase()) + '</span><span>' + esc(t.category) + '</span><span>' + esc(t.target_ids.length > 1 ? "Supports " + t.target_ids.length + " targets" : "Program-specific work") + '</span></div>' + (t.reason ? '<p>' + esc(t.reason) + '</p>' : "") + (t.waiting_for ? '<p>' + (t.status === "completed" ? "Synthetic event recorded." : "External confirmation is required; estimated work time cannot satisfy it.") + '</p>' : "") + '</div><span class="task-hours">' + hours(t.hours_high) + 'h</span></article>').join("");
  $("task-list").querySelectorAll("[data-complete]").forEach(b => b.onclick = () => action("Updating the synthetic completion state…", async () => {
    const updated = profile();
    const id = b.dataset.complete;
    updated.completed_task_ids = updated.completed_task_ids.includes(id) ? updated.completed_task_ids.filter(x => x !== id) : [...updated.completed_task_ids,id];
    if (mode === "simulation") { notify("Complete preparation in the main plan. Simulation is a separate review scenario."); return; }
    setPlan(await api("/api/plan", {selected_ids: state.selected,profile: updated}));
    notify("Preparation state updated in a new proposal.");
  }));
  for (const [index, task] of plan.tasks.entries()) {
    if (!task.waiting_for) continue;
    const container = $("task-list").children[index]?.querySelector(".task-main");
    if (!container) continue;
    const observed = (plan.profile.received_events || []).includes(task.waiting_for);
    const button = document.createElement("button");
    button.className = "receipt-btn secondary";
    button.textContent = observed ? "Undo synthetic receipt" : "Record synthetic receipt";
    button.disabled = mode === "simulation";
    button.onclick = () => action("Recording an explicitly observed synthetic event…", async () => {
      const updated = profile();
      updated.received_events = observed ? updated.received_events.filter(e => e !== task.waiting_for) : [...updated.received_events, task.waiting_for];
      setPlan(await api("/api/plan", {selected_ids: state.selected, profile: updated}));
      notify("Synthetic receipt state updated. No letter, document, email or application was sent.");
    });
    container.appendChild(button);
  }
  $("target-checks").innerHTML = plan.targets.map(t => {
    const op = state.opportunities.find(o => o.id === t.target_id);
    return '<div class="check-card"><h4>' + esc(op?.program || t.target_id) + '</h4><span class="badge ' + (t.schedule_status === "infeasible" || t.eligibility === "not_eligible" ? "closed" : "unknown") + '">' + esc(t.schedule_status.replaceAll("_"," ").toUpperCase()) + '</span><p>' + esc((t.reasons || []).join(" ")) + '</p>' + (t.criteria || []).slice(0,5).map(c => '<div class="criteria-item"><strong>' + esc(c.status.replaceAll("_"," ")) + '</strong><span>' + esc(c.explanation) + '</span></div>').join("") + '</div>';
  }).join("");
  const candidates = state.opportunities.filter(o => state.selected.includes(o.id) && Number(fact(o,"reference_min")?.value) > 0);
  $("simulation-target").innerHTML = candidates.map(o => '<option value="' + esc(o.id) + '">' + esc(o.program) + '</option>').join("");
  $("simulate-btn").disabled = !candidates.length;
  if (!candidates.length) $("simulation-target").innerHTML = '<option>No supported reference rule selected</option>';
  renderEvidence(); renderCards(); updateSelected();
}
function renderEvidence() {
  if (!state.plan) return;
  const seen = new Set();
  const evidence = [...(state.plan.evidence || [])].sort((a,b) => Number(!!b.excerpt) - Number(!!a.excerpt)).filter(e => {
    const version = e.nodes.find(n => n.includes("@"));
    const key = e.target_id + "/" + (version ? version.split("@")[0] : e.task_id);
    if (seen.has(key)) return false; seen.add(key); return true;
  });
  $("evidence-list").innerHTML = evidence.length ? evidence.slice(0,18).map(e => '<article class="evidence-card"><div class="evidence-path">' + (e.nodes || []).map(n => '<span>' + esc(nodeLabel(n)) + '</span>').join(" → ") + '</div>' + (e.excerpt ? '<blockquote>' + esc(e.excerpt) + '</blockquote>' : '<p class="muted">Explicit preparation recipe; effort is estimated.</p>') + (e.source_url ? '<a class="source-link" href="' + esc(safeUrl(e.source_url)) + '" target="_blank" rel="noopener noreferrer">Read supporting source ↗</a>' : "") + '</article>').join("") : '<div class="empty-state"><p>No evidence paths were returned. Review the missing source information.</p></div>';
}

function nodeLabel(id) {
  const op = state.opportunities.find(o => o.id === id);
  if (op) return op.program + " · " + op.cycle;
  const task = state.plan?.tasks.find(t => t.task_id === id || id.endsWith("/task/" + t.task_id));
  if (task) return task.title;
  if (id.startsWith("source/")) return "Source observation";
  if (id.includes("/target/")) return "Target assessment";
  if (id.startsWith("plan-")) return "Saved plan";
  const name = id.split("/").pop().split("@")[0];
  const labels = {reference_min:"Required reference count",reference_received_before_submit:"Receipt before submission",reference_submitter:"Qualifying recommender",reference_forbidden:"Reference exception",application_deadline:"Application cutoff",portal_status:"Portal state",transcript_translation:"Transcript language rule",statement_max_words:"Statement word limit",statement_max_chars:"Statement character limit",documents:"Required documents",requirement_set:"Requirement membership",institution_approval:"Institution approval"};
  if (id.includes("/deliverable/")) return "Required " + name.replaceAll("_", " ");
  return labels[name] || name.replaceAll("_", " ");
}
document.querySelectorAll(".step").forEach(b => b.onclick = () => showStep(b.dataset.step));
document.querySelectorAll(".filter").forEach(b => b.onclick = () => { state.category = b.dataset.category; document.querySelectorAll(".filter").forEach(x => x.classList.toggle("active",x===b)); renderCards(); });
$("search-form").onsubmit = e => { e.preventDefault(); action("Searching and fetching public sources with TinyFish…", async () => {
  const result = await api("/api/discover",{query:$("search-query").value});
  const map = new Map(state.opportunities.map(o=>[o.id,o]));
  (result.opportunities || []).forEach(o=>map.set(o.id,o)); state.opportunities = [...map.values()];
  $("source-caption").textContent = "LIVE · TinyFish search/fetch · Checked " + dateLabel(new Date().toISOString());
  renderCards(); updateSelected();
  notify(result.errors?.length ? "Discovery completed with source gaps: " + result.errors.join(" ") : "Public sources checked. Review requirements before choosing targets.", !!result.errors?.length);
}); };
$("examples-btn").onclick = () => action("Loading labeled snapshots from official sources…", async () => {
  const result = await api("/api/examples"); state.opportunities = result.opportunities || [];
  $("source-caption").textContent = "CACHED OFFICIAL SOURCES · Original checked dates are shown · Refresh before relying on a deadline";
  renderCards(); updateSelected(); notify("Examples loaded from official-source snapshots. They are cached, not a live search.");
});
$("plan-btn").onclick = () => action("Traversing target requirements and shared preparation in FalkorDB…", async () => {
  state.impact = null; $("impact-details").innerHTML = ""; setPlan(await api("/api/plan",{selected_ids:state.selected,profile:profile()}));
  showStep("plan"); notify("Preparation proposal built from graph context. Review uncertain and waiting states before accepting.");
});
$("back-btn").onclick = () => showStep("discover");
$("accept-btn").onclick = () => action("Checking fact versions and saving the accepted plan…", async () => {
  setPlan(await api("/api/plan/" + encodeURIComponent(state.plan.id) + "/accept?mode=" + state.mode,{}),state.mode);
  notify("Plan accepted and saved. This accepts preparation only; no internship application was submitted.");
});
$("simulate-btn").onclick = () => action("Tracing one simulated policy change through a separate FalkorDB graph…", async () => {
  const result = await api("/api/simulate",{selected_ids:state.selected,profile:profile(),opportunity_id:$("simulation-target").value,fact_name:"reference_min",value:2});
  state.impact = result.impact; setPlan(result.after,"simulation");
  const i=result.impact;
  const impacted = result.after.tasks.filter(t => i.affected_task_ids.includes(t.task_id));
  $("impact-details").innerHTML = '<div class="impact-result"><b>SIMULATION · Field-level impact</b><p>' + esc(i.affected_target_ids.length) + ' target(s), ' + esc(i.affected_task_ids.length) + ' task(s) need review.</p>' + impacted.map(t=>'<span class="impact-path">'+esc(t.title)+'</span>').join("") + '<p>Compatible completed base work is preserved. Full supporting paths are in Evidence.</p></div>';
  notify("Simulated change reviewed. Original official facts remain unchanged.");
});
$("agent-btn").onclick = () => action("The agent is choosing tools and reviewing graph evidence…", async () => {
  const result = await api("/api/agent",{selected_ids:state.selected,profile:profile(),message:"Inspect requirements and propose my preparation plan. Explain the most important blocker and next action."});
  state.trace = result.trace || [];
  const proposal = [...(result.results || [])].reverse().find(r=>r.result?.plan);
  if (proposal?.result?.plan) setPlan(proposal.result.plan);
  $("agent-trace").classList.remove("hidden");
  $("agent-trace").innerHTML = '<h3>Actual agent tool trace · ' + esc(result.provider) + '</h3><p class="trace-note">' + esc(result.message) + '</p>' + state.trace.map(t=>'<div class="trace-row"><code>'+esc(t.tool)+'</code> · '+esc(t.outcome || "executed")+' · '+esc(JSON.stringify(t.arguments))+' · '+esc(t.duration_ms)+'ms · '+esc(t.result_summary)+'</div>').join("") + '<p class="trace-note">' + esc(result.notice) + '</p>';
  showStep("evidence"); notify("Agent review complete. Read the structured proposal and evidence before accepting.");
});
async function init() {
  try {
    const result=await api("/api/health");
    const healthy=!!(result.database?.healthy || result.database?.status==="ok" || result.database?.ok);
    $("health-text").textContent=healthy?"FalkorDB connected":"Graph needs attention"; $("db-dot").classList.toggle("off",!healthy);
    const saved=await api("/api/opportunities"); state.opportunities=saved.opportunities || [];
    if(state.opportunities.length)renderCards();
    const previous=await api("/api/plan/latest");
    if(previous.plan){ setPlan(previous.plan); $("weekly-hours").value=previous.plan.profile.weekly_hours; $("start-date").value=previous.plan.profile.start_date; $("exam-week").value=previous.plan.profile.exam_weeks?.[0] || ""; notify("Saved preparation plan recovered from FalkorDB."); }
    updateSelected();
  } catch(e){$("health-text").textContent="Server unavailable";$("db-dot").classList.add("off");notify(e.message,true);}
}
init();

