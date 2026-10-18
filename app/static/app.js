const state = { opportunities: [], selected: [], category: "All", plan: null, mode: "official", impact: null, trace: [], hunt: null, listings: [], listingSelected: [], useHuntSelection: false, currentStep: "discover", taskCategory: "All", examWeeks: [], holidays: [], ratings: {} };
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
  let token = localStorage.getItem("scout-client");
  if (!token) { token = crypto.randomUUID().replaceAll("-", ""); localStorage.setItem("scout-client", token); }
  const headers = { "X-Scout-Client": token };
  const response = await fetch(path, data === undefined ? {headers} : { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(data) });
  let body; try { body = await response.json(); } catch { throw new Error("The server returned an unreadable response."); }
  if (!response.ok) {
    const message = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map(item => item.msg).join("; ") : "Request could not complete.";
    throw new Error(message);
  }
  return body;
}
async function action(label, fn) {
  if (busy) return;
  busy = true; document.body.classList.add("is-working"); notify(label);
  document.querySelectorAll("button").forEach(b => { b.dataset.wasDisabled = b.disabled ? "1" : "0"; b.disabled = true; });
  try { await fn(); } catch (e) { notify(e.message || "Could not complete this action.", true); }
  finally {
    busy = false; document.body.classList.remove("is-working");
    document.querySelectorAll("button").forEach(b => {
      if (b.dataset.wasDisabled !== undefined) { b.disabled = b.dataset.wasDisabled === "1"; delete b.dataset.wasDisabled; }
    });
    updateSelected(); if (state.plan) $("accept-btn").disabled = state.plan.status !== "proposed";
    $("hunt-refresh").disabled = !state.hunt;
  }
}
function showStep(name, story) {
  const changed = state.currentStep !== name;
  state.currentStep = name;
  document.body.dataset.page = name;
  setStoryStage(story || (name === "plan" ? (state.plan ? "roadmap" : "time") : name === "evidence" ? "evidence" : state.hunt ? "results" : "start"));
  for (const s of ["discover", "plan", "evidence"]) $(s + "-section").classList.toggle("hidden", s !== name);
  document.querySelectorAll(".step").forEach(b => {
    b.classList.toggle("active", b.dataset.step === name);
    if (b.dataset.step === name) b.setAttribute("aria-current", "step");
    else b.removeAttribute("aria-current");
  });
  if (name === "evidence") renderEvidence();
  const section = $(name + "-section");
  if (changed && section && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    section.getAnimations().forEach(animation => animation.cancel());
    section.animate([{opacity:0,transform:"translateY(10px)"},{opacity:1,transform:"translateY(0)"}],
      {duration:240,easing:"cubic-bezier(.22,1,.36,1)"});
  }
}
function setStoryStage(stage) {
  document.body.dataset.story = stage;
  const copy = {
    start:["YOUR NEXT CHAPTER","Find a direction worth exploring.","Start with what you know—or discover the work you might enjoy."],
    explore:["STEP 1 · EXPLORE THE WORK","What would you enjoy doing?","Imagine the project. Choose the activities you’re curious to try."],
    search:["STEP 2 · YOUR PREFERENCES","What opportunities should we look for?","Edit your roles, places and funding. Your interests are a starting point."],
    results:["STEP 3 · CHOOSE YOUR TARGETS","Which opportunities do you want to pursue?","Review the source details. Choose up to three targets for one connected preparation path."],
    time:["STEP 4 · MAKE ROOM","When can you prepare?","Set a realistic routine. Protect your exams and days off before building the plan."],
    roadmap:["STEP 5 · YOUR LEARNING PATH","Your next step, with a reason.","Shared topics come first. Adjust your starting level and follow the resources at your pace."],
    evidence:["THE REASONING BEHIND YOUR PLAN","See what your plan is based on.","Follow source excerpts and graph relationships. Unknown requirements stay visible."]
  }[stage];
  if (copy) { $("journey-kicker").textContent=copy[0]; $("journey-title").textContent=copy[1]; $("journey-description").textContent=copy[2]; }
  const active=stage==="explore"?"start":stage==="evidence"?"roadmap":stage;
  document.querySelectorAll("[data-story-nav]").forEach(button=>{
    button.classList.toggle("active",button.dataset.storyNav===active);
    if(button.dataset.storyNav===active)button.setAttribute("aria-current","step");else button.removeAttribute("aria-current");
  });
}
function goStory(stage) {
  if (["results","time"].includes(stage) && !state.hunt && !state.selected.length) return notify("Start a search or open a saved search first.");
  if (stage==="time" && !(state.useHuntSelection ? state.listingSelected.length : state.selected.length)) return notify("Choose at least one target before setting your preparation time.");
  if (stage==="roadmap" && !state.plan) return notify("Choose your targets and time, then build a roadmap.");
  if(stage==="search"){showStep("discover","search");showSearch();}
  else showStep(["time","roadmap"].includes(stage)?"plan":stage==="evidence"?"evidence":"discover",stage);
  if(stage==="time")$("prep-settings").open=true;
  $("journey-title").scrollIntoView({block:"start"});
}
function browserToken() {
  let token = localStorage.getItem("scout-client");
  if (!token) { token = crypto.randomUUID().replaceAll("-", ""); localStorage.setItem("scout-client", token); }
  return token;
}
function profile() {
  const existing = state.plan?.profile || {};
  const text = id => $(id).value.trim() || null;
  const number = id => $(id).value === "" ? null : Number($(id).value);
  const pattern = {};
  for (let index=0; index<7; index++) if ($("hours-" + index).value !== "") pattern[String(index)] = Number($("hours-" + index).value);
  const value = {id: "unassigned", synthetic: false, country: text("profile-country"), degree: text("profile-degree"),
    field: text("profile-field"), year: number("profile-year"), total_years: number("profile-total-years"),
    institution_type: text("profile-institution"), weekly_hours: Number($("weekly-hours").value),
    start_date: $("start-date").value, horizon_weeks: Number($("horizon-weeks").value),
    exam_weeks: [...state.examWeeks], holidays: [...state.holidays], weekly_pattern: pattern,
    skill_ratings: {...state.ratings},
    completed_task_ids: existing.completed_task_ids || [], received_events: existing.received_events || [],
    skills: existing.skills || {}};
  localStorage.setItem("preparation-profile:" + browserToken(), JSON.stringify(value));
  return value;
}
function fillProfile(value = {}) {
  for (const [id, field] of [["profile-country","country"],["profile-degree","degree"],["profile-field","field"],
    ["profile-year","year"],["profile-total-years","total_years"],["profile-institution","institution_type"],
    ["weekly-hours","weekly_hours"],["start-date","start_date"],["horizon-weeks","horizon_weeks"]]) {
    if (value[field] !== undefined && value[field] !== null) $(id).value = value[field];
  }
  state.examWeeks = [...new Set(value.exam_weeks || [])].sort();
  state.holidays = [...new Set(value.holidays || [])].sort();
  state.ratings = {...(value.skill_ratings || {})};
  for (let index=0; index<7; index++) $("hours-" + index).value = value.weekly_pattern?.[String(index)] ?? "";
  renderCalendarChips();
  if (!$("start-date").value) $("start-date").value = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
}
let storedProfile;
try { storedProfile = JSON.parse(localStorage.getItem("preparation-profile:" + browserToken()) || "{}"); } catch { storedProfile = {}; }
fillProfile(storedProfile);
function normalizeMonday(input) {
  if (!input.value) return;
  const date = new Date(input.value + "T12:00:00Z");
  const shift = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - shift);
  input.value = date.toISOString().slice(0,10);
}
function renderCalendarChips() {
  const render = (id, values, kind) => {
    $(id).innerHTML = values.length ? values.map(value => '<span class="date-chip">' + esc(dateLabel(value)) + '<button type="button" data-remove-date="' + esc(value) + '" aria-label="Remove ' + esc(dateLabel(value)) + '">×</button></span>').join("") : '<small>None added</small>';
    $(id).querySelectorAll("[data-remove-date]").forEach(button => button.onclick = () => {
      if (kind === "exam") state.examWeeks = state.examWeeks.filter(value => value !== button.dataset.removeDate);
      else state.holidays = state.holidays.filter(value => value !== button.dataset.removeDate);
      renderCalendarChips(); profile();
    });
  };
  render("exam-weeks-list", state.examWeeks, "exam");
  render("holidays-list", state.holidays, "holiday");
}
$("exam-week-add").onclick = () => {
  if (!$("exam-week").value) return notify("Choose an exam-week date first.", true);
  normalizeMonday($("exam-week"));
  state.examWeeks = [...new Set([...state.examWeeks, $("exam-week").value])].sort();
  $("exam-week").value = ""; renderCalendarChips(); profile();
};
$("holiday-add").onclick = () => {
  if (!$("holiday-date").value) return notify("Choose a day off first.", true);
  state.holidays = [...new Set([...state.holidays, $("holiday-date").value])].sort();
  $("holiday-date").value = ""; renderCalendarChips(); profile();
};

function renderCards() {
  renderSourceControls();
  if (state.useHuntSelection && typeof renderScoutCards === "function") { renderScoutCards(); return; }
  const list = state.opportunities.filter(o => state.selected.includes(o.id) && (state.category === "All" || o.category === state.category));
  $("result-count").textContent = list.length + " opportunit" + (list.length === 1 ? "y" : "ies");
  if (!list.length) {
    $("opportunity-cards").innerHTML = '<div class="empty-state"><span class="empty-icon">↗</span><h3>Start your search.</h3><p>Find live opportunities using your interests and location preferences.<br>Missing requirements stay unknown.</p></div>';
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
  const ids = state.useHuntSelection ? state.listingSelected : state.selected;
  $("selection-count").textContent = ids.length + " / 3";
  $("selected-list").innerHTML = ids.length ? ids.map(id => {
    const op = state.opportunities.find(o => o.id === id);
    const listing = state.listings.find(v => v.id === id);
    return '<div class="selected-item"><i class="selected-dot"></i><span>' + esc(listing?.title || op?.program || id) + '</span><button data-remove="' + esc(id) + '" aria-label="Remove target">×</button></div>';
  }).join("") : '<p class="muted">Add up to three opportunities you want to work toward.</p>';
  $("selected-list").querySelectorAll("[data-remove]").forEach(b => b.onclick = () => state.useHuntSelection ? toggleListing(b.dataset.remove) : toggleTarget(b.dataset.remove));
  $("plan-btn").disabled = busy || !ids.length;
  $("setup-plan-btn").disabled = busy || !ids.length;
  $("agent-btn").disabled = busy || !ids.length || !state.plan;
  $("prep-selection-note").textContent = ids.length ? ids.length + " selected target" + (ids.length === 1 ? "" : "s") + " · one weekly budget" : "Select targets before building a plan";
  $("prep-settings").classList.toggle("hidden", !ids.length && !state.plan);
  if (!state.plan) {
    $("plan-empty").querySelector("h3").textContent = ids.length ? "Your targets are set. Now make a little room." : "Select your targets first.";
    $("plan-empty").querySelector("p").textContent = ids.length ? "Choose your weekly time above, then build a preparation proposal." : "Your preparation plan will appear here.";
  }
}

function renderSourceControls() {
  const unique = [...new Map(state.opportunities.filter(o => state.selected.includes(o.id)).map(o => [o.source_url, o])).values()];
  $("source-controls").classList.toggle("hidden", !unique.length);
  $("refresh-source").innerHTML = unique.map(o => '<option value="' + esc(o.source_url) + '">' + esc(o.program) + '</option>').join("");
}

function weekCapacity(profileValue, week) {
  const pattern = profileValue.weekly_pattern || {};
  if (!Object.keys(pattern).length) {
    const start = new Date(week + "T12:00:00Z");
    let availableDays = 0;
    for (let offset=0; offset<7; offset++) {
      const day = new Date(start); day.setUTCDate(day.getUTCDate() + offset);
      const iso = day.toISOString().slice(0,10);
      const monday = new Date(day); monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay()+6)%7));
      if (!(profileValue.exam_weeks || []).includes(monday.toISOString().slice(0,10)) && !(profileValue.holidays || []).includes(iso)) availableDays++;
    }
    return Number(profileValue.weekly_hours || 0) * availableDays / 7;
  }
  const start = new Date(week + "T12:00:00Z");
  let total = 0;
  for (let offset=0; offset<7; offset++) {
    const day = new Date(start); day.setUTCDate(day.getUTCDate() + offset);
    const iso = day.toISOString().slice(0,10);
    const monday = new Date(day); monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay()+6)%7));
    if (!(profileValue.exam_weeks || []).includes(monday.toISOString().slice(0,10)) && !(profileValue.holidays || []).includes(iso)) total += Number(pattern[String((day.getUTCDay()+6)%7)] || 0);
  }
  return total;
}

function renderRoadmap(plan) {
  const roadmap = plan.roadmap || [];
  $("roadmap-note").textContent = roadmap.length ? "Prerequisites come first. Your levels are self-reported and only change the suggested start point—not the sourced requirements." : "No reviewed learning topics were found in the selected sources yet. Unextracted or unsupported topics stay unknown.";
  if (!roadmap.length) { $("roadmap-list").innerHTML = '<div class="empty-state roadmap-empty"><p>The preparation tasks remain available. A topic roadmap appears when reviewed skills are extracted from a selected source.</p></div>'; return; }
  const ratingOptions = [["","Not rated"],["comfortable","Comfortable"],["review","Needs review"],["new","New to me"],["unsure","Not sure"]];
  $("roadmap-list").innerHTML = roadmap.map(entry => {
    const required = Object.entries(entry.required_by || {}).map(([target,names]) => (state.opportunities.find(item => item.id === target)?.program || target) + " · " + names.map(name => name.replaceAll("_"," ")).join(", "));
    return '<article class="roadmap-item ' + (entry.start_here ? "start" : "") + (entry.task_status === "completed" ? " done" : "") + '"><div class="roadmap-order">' + String(entry.order).padStart(2,"0") + '</div><div class="roadmap-main"><div class="roadmap-title"><h4>' + esc(entry.title) + '</h4><span class="badge">' + esc(entry.family || "Foundation") + '</span>' + (entry.start_here ? '<span class="badge start-badge">START HERE</span>' : '') + (entry.task_status ? '<span class="badge">' + esc(entry.task_status.toUpperCase()) + '</span>' : '') + '</div>' + (entry.prerequisites?.length ? '<p class="roadmap-prereqs">Builds after: ' + entry.prerequisites.map(value => esc((roadmap.find(item => item.key === value)?.title) || value.replaceAll("_"," "))).join(", ") + '</p>' : '') + '<div class="roadmap-actions"><label>Your level<select data-rating="' + esc(entry.key) + '">' + ratingOptions.map(([value,label]) => '<option value="' + value + '" ' + (entry.rating === value ? "selected" : "") + '>' + label + '</option>').join("") + '</select></label><div class="roadmap-resources">' + (entry.resources || []).map(resource => '<a class="source-link" href="' + esc(safeUrl(resource.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(resource.title) + ' ↗</a>').join("") + '</div></div>' + (required.length ? '<p class="roadmap-required">Connected source facts: ' + esc(required.join("; ")) + '</p>' : '<p class="roadmap-required">Prerequisite guidance for a connected required topic.</p>') + (entry.note ? '<p class="roadmap-item-note">' + esc(entry.note) + '</p>' : '') + '</div></article>';
  }).join("");
  $("roadmap-list").querySelectorAll("[data-rating]").forEach(select => select.onchange = () => action("Saving your self-reported topic level…", async () => {
    if (select.value) state.ratings[select.dataset.rating] = select.value; else delete state.ratings[select.dataset.rating];
    setPlan(await api("/api/plan", {selected_ids: state.selected, profile: profile()}));
    notify("Topic level saved as self-reported. It changes the suggested start point, not the source requirements.");
  }));
}

$("refresh-btn").onclick = () => action("Refreshing the selected source and checking fact-level changes…", async () => {
  const result = await api("/api/refresh", {url: $("refresh-source").value});
  const all = await api("/api/opportunities"); state.opportunities = all.opportunities || [];
  state.useHuntSelection = false; renderCards();
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
  state.ratings = {...(plan.profile?.skill_ratings || {})};
  state.selected = plan.selected_ids || state.selected;
  $("plan-empty").classList.add("hidden"); $("plan-content").classList.remove("hidden");
  $("next-action-text").textContent = plan.next_action || "Review your target requirements and resolve the unknowns.";
  $("plan-mode-note").textContent = mode === "simulation" ? "SIMULATION · Separate graph. Changed policy is illustrative; official source facts remain unchanged." : "Your profile and progress are self-reported · Requirements link to source evidence.";
  if (state.enrichmentWarnings?.length || plan.warnings?.some(w => /source.*review is incomplete/i.test(w))) $("plan-mode-note").textContent += " · Some source details need review.";
  $("metric-effort").textContent = hours(plan.total_hours_low) + "–" + hours(plan.total_hours_high) + " h";
  $("metric-capacity").textContent = hours(plan.available_hours) + " h";
  const shared = plan.tasks.filter(t => t.category === "Shared" && t.status !== "completed");
  $("metric-shared").textContent = hours(shared.reduce((sum,t) => sum + t.hours_high, 0)) + " h";
  $("metric-state").textContent = plan.status.charAt(0).toUpperCase() + plan.status.slice(1);
  $("metric-version").textContent = "Version " + plan.id.slice(0,8);
  $("accept-btn").disabled = plan.status !== "proposed";
  $("plan-warnings").innerHTML = [...(state.enrichmentWarnings || []),...(plan.warnings || [])].map(w => '<div class="warning">' + esc(w) + '</div>').join("");
  const weeks = Object.keys(plan.weekly_used || {});
  if (!weeks.length) {
    const start = new Date(plan.profile.start_date + "T12:00:00Z");
    for (let i=0;i<plan.profile.horizon_weeks;i++) { const date = new Date(start); date.setUTCDate(date.getUTCDate()+i*7); weeks.push(date.toISOString().slice(0,10)); }
  }
  $("timeline").innerHTML = weeks.map(week => {
    const cap = weekCapacity(plan.profile, week), used = Number(plan.weekly_used?.[week] || 0), protectedWeek = cap === 0;
    return '<div class="week-row ' + (protectedWeek ? "exam" : "") + '"><div class="week-title">' + esc(dateLabel(week)) + '<small>' + (protectedWeek ? "PROTECTED / UNAVAILABLE" : "PREPARATION WEEK") + '</small></div><div class="week-bar"><span style="width:' + (cap ? Math.min(100,used/cap*100) : 0) + '%"></span></div><div class="week-hours">' + hours(used) + " / " + hours(cap) + 'h</div></div>';
  }).join("");
  renderRoadmap(plan);
  $("task-list").innerHTML = plan.tasks.map(t => '<article class="task"><button class="task-check ' + (t.status === "completed" ? "done" : "") + '" data-complete="' + esc(t.task_id) + '" ' + (t.waiting_for || t.status === "waiting" || t.status === "blocked" ? "disabled" : "") + ' aria-label="Toggle my preparation completion">' + (t.status === "completed" ? "✓" : "") + '</button><div class="task-main"><h4>' + esc(t.title) + '</h4><div class="task-meta"><span class="badge ' + (t.status === "waiting" || t.status === "blocked" ? "closed" : "") + '">' + esc(t.status.toUpperCase()) + '</span><span>' + esc(t.category) + '</span><span>' + esc(t.target_ids.length > 1 ? "Supports " + t.target_ids.length + " targets" : "Program-specific work") + '</span></div>' + (t.reason ? '<p>' + esc(t.reason) + '</p>' : "") + (t.waiting_for ? '<p>' + (t.status === "completed" ? "Receipt marked by you; not independently verified." : "External confirmation is required; estimated work time cannot satisfy it.") + '</p>' : "") + '</div><span class="task-hours">' + hours(t.hours_high) + 'h</span></article>').join("");
  $("task-list").querySelectorAll("[data-complete]").forEach(b => b.onclick = () => action("Updating your completion state…", async () => {
    const updated = profile();
    const id = b.dataset.complete;
    updated.completed_task_ids = updated.completed_task_ids.includes(id) ? updated.completed_task_ids.filter(x => x !== id) : [...updated.completed_task_ids,id];
    if (mode === "simulation") { notify("Complete preparation in the main plan. Simulation is a separate review scenario."); return; }
    setPlan(await api("/api/plan", {selected_ids: state.selected,profile: updated}));
    notify("Preparation state updated in a new proposal.");
  }));
  for (const [index, task] of plan.tasks.entries()) $("task-list").children[index].dataset.taskCategory = task.category;
  const taskCategories = ["All", ...["Shared", "Research", "Company"].filter(category => plan.tasks.some(task => task.category === category))];
  if (!taskCategories.includes(state.taskCategory)) state.taskCategory = "All";
  $("task-filters").innerHTML = taskCategories.map(category => {
    const count = plan.tasks.filter(task => category === "All" || task.category === category).length;
    const label = category === "All" ? "All work" : category === "Shared" ? "Shared foundations" : category;
    return '<button class="filter" data-task-filter="' + category + '" aria-pressed="' + (category === state.taskCategory) + '">' + esc(label) + ' <span>' + count + '</span></button>';
  }).join("");
  $("task-filters").querySelectorAll("button").forEach(button => button.onclick = () => {
    state.taskCategory = button.dataset.taskFilter;
    applyTaskFilter();
  });
  applyTaskFilter();
  for (const [index, task] of plan.tasks.entries()) {
    if (!task.waiting_for) continue;
    const container = $("task-list").children[index]?.querySelector(".task-main");
    if (!container) continue;
    const observed = (plan.profile.received_events || []).includes(task.waiting_for);
    const button = document.createElement("button");
    button.className = "receipt-btn secondary";
    button.textContent = observed ? "Undo my receipt confirmation" : "I confirm this was received";
    button.disabled = mode === "simulation";
    button.onclick = () => action("Saving your receipt confirmation…", async () => {
      const updated = profile();
      updated.received_events = observed ? updated.received_events.filter(e => e !== task.waiting_for) : [...updated.received_events, task.waiting_for];
      setPlan(await api("/api/plan", {selected_ids: state.selected, profile: updated}));
      notify("Your receipt confirmation was saved. Delivery has not been checked independently.");
    });
    container.appendChild(button);
  }
  $("target-checks").innerHTML = plan.targets.map(t => {
    const op = state.opportunities.find(o => o.id === t.target_id);
    return '<div class="check-card"><h4>' + esc(op?.program || t.target_id) + '</h4><span class="badge ' + (t.schedule_status === "infeasible" || t.eligibility === "not_eligible" ? "closed" : "unknown") + '">' + esc(t.schedule_status.replaceAll("_"," ").toUpperCase()) + '</span><p>' + esc((t.reasons || []).join(" ")) + '</p>' + (t.criteria || []).slice(0,5).map(c => '<div class="criteria-item"><strong>' + esc(c.status.replaceAll("_"," ")) + '</strong><span>' + esc(c.explanation) + '</span></div>').join("") + '</div>';
  }).join("");
  renderEvidence(); renderCards(); updateSelected();
}
function applyTaskFilter() {
  document.querySelectorAll("#task-list .task").forEach(task => task.classList.toggle("hidden", state.taskCategory !== "All" && task.dataset.taskCategory !== state.taskCategory));
  document.querySelectorAll("#task-filters button").forEach(button => {
    const active = button.dataset.taskFilter === state.taskCategory;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}
function renderEvidence() {
  if (!state.plan) return;
  const seen = new Set();
  const evidence = [...(state.plan.evidence || [])].sort((a,b) => Number(!!b.excerpt) - Number(!!a.excerpt)).filter(e => {
    const version = e.nodes.find(n => n.includes("@"));
    const key = e.target_id + "/" + (version ? version.split("@")[0] : e.task_id);
    if (seen.has(key)) return false; seen.add(key); return true;
  });
  $("evidence-list").innerHTML = evidence.length ? evidence.slice(0,18).map(e => '<article class="evidence-card"><div class="evidence-path">' + (e.nodes || []).map(n => '<span title="' + esc(n) + '">' + esc(nodeLabel(n)) + '</span>').join(" → ") + '</div>' + (e.excerpt ? '<blockquote>' + esc(e.excerpt) + '</blockquote>' : '<p class="muted">Explicit preparation recipe; effort is estimated.</p>') + (e.source_url ? '<a class="source-link" href="' + esc(safeUrl(e.source_url)) + '" target="_blank" rel="noopener noreferrer">Read supporting source ↗</a>' : "") + '</article>').join("") : '<div class="empty-state"><p>No evidence paths were returned. Review the missing source information.</p></div>';
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
  if (id.includes("/deliverable/")) {
    const groups = {cs_topics: "CS preparation requirement", programming_languages: "Programming preparation requirement", preferred_skills: "Suggested skill preparation", skills: "Skill preparation requirement"};
    const group = Object.keys(groups).find(key => name.startsWith(key + "_"));
    return group ? groups[group] : "Required " + name.replaceAll("_", " ");
  }
  return labels[name] || name.replaceAll("_", " ");
}
document.querySelectorAll(".step").forEach(b => b.onclick = () => showStep(b.dataset.step));
document.querySelectorAll(".filter").forEach(b => b.onclick = () => { state.category = b.dataset.category; document.querySelectorAll(".filter").forEach(x => x.classList.toggle("active",x===b)); renderCards(); });
$("plan-btn").onclick = () => action("Traversing target requirements and shared preparation in FalkorDB…", async () => {
  for (const id of ["weekly-hours", "start-date", "exam-week", "holiday-date", "hours-0", "hours-1", "hours-2", "hours-3", "hours-4", "hours-5", "hours-6", "profile-country", "profile-field", "profile-year", "profile-total-years", "horizon-weeks"]) {
    if (!$(id).reportValidity()) throw new Error("Check your preparation time and dates before continuing.");
  }
  if (state.useHuntSelection) await prepareSelectedListings();
  state.impact = null; setPlan(await api("/api/plan",{selected_ids:state.selected,profile:profile()}));
  $("prep-settings").open = false;
  showStep("plan"); notify("Preparation proposal built from graph context. Review uncertain and waiting states before accepting.");
});
$("setup-plan-btn").onclick = () => {
  if (busy) return;
  $("prep-settings").open = true;
  showStep("plan", "time");
  notify("Set one weekly time budget for your selected targets. Exam weeks stay protected.");
  $("plan-section").scrollIntoView({ block: "start" });
  $("weekly-hours").focus({ preventScroll: true });
};
$("back-btn").onclick = () => showStep("discover");
$("accept-btn").onclick = () => action("Checking fact versions and saving the accepted plan…", async () => {
  setPlan(await api("/api/plan/" + encodeURIComponent(state.plan.id) + "/accept?mode=" + state.mode,{}),state.mode);
  notify("Plan accepted and saved. This accepts preparation only; no internship application was submitted.");
});
$("agent-btn").onclick = () => action("The agent is choosing tools and reviewing graph evidence…", async () => {
  if (state.useHuntSelection) await prepareSelectedListings();
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
    const agentEnabled = result.discovery?.agent_enabled === true;
    $("agent-status").textContent = agentEnabled ? "TinyFish browser Agent enabled · metered fallback" : "TinyFish browser Agent off · Search/Fetch separate";
    $("agent-status").title = result.discovery?.agent_gate || "This is separate from Groq's preparation agent. Configuration does not prove a live run.";
    const saved=await api("/api/opportunities"); state.opportunities=saved.opportunities || [];
    const previous=await api("/api/plan/latest");
    if(previous.plan && !busy && !state.plan){ fillProfile(previous.plan.profile); setPlan(previous.plan); if(!state.hunt)notify("Saved preparation plan recovered from FalkorDB."); }
    updateSelected();
  } catch(e){$("health-text").textContent="Server unavailable";$("db-dot").classList.add("off");$("agent-status").textContent="Browser Agent status unavailable";notify(e.message,true);}
}
init();
