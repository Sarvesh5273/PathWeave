const state = { opportunities: [], selected: [], category: "All", plan: null, mode: "official", impact: null, trace: [], hunt: null, listings: [], listingSelected: [], useHuntSelection: false, currentStep: "discover", taskCategory: "All", examWeeks: [], holidays: [], ratings: {} };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = value => { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; } catch { return "#"; } };
const fact = (op, name) => op.facts?.find(f => f.name === name && f.status === "known");
const dateLabel = value => { if (!value) return "Unknown"; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }); };
const deadlineLabel = value => { if (!value) return "Unknown"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString("en-IN", {day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Kolkata"}) + " IST"; };
const hours = value => value === null || value === undefined || value === "" ? "—" : Number.isFinite(Number(value)) ? Number(value).toFixed(1).replace(/\.0$/, "") : "—";
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
  const previousStage = document.body.dataset.story;
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
  if (previousStage && previousStage !== stage && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const heading = $("journey-title");
    heading.getAnimations().forEach(animation => animation.cancel());
    heading.animate([{ opacity: 0, transform: "translateY(7px)" }, { opacity: 1, transform: "translateY(0)" }],
      { duration: 240, easing: "cubic-bezier(.22,1,.36,1)" });
  }
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
    institution_type: text("profile-institution"), study_track: $("study-track").value || "auto", weekly_hours: Number($("weekly-hours").value),
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
  $("study-track").value = ["auto","software","data","research","general","source_only"].includes(value.study_track) ? value.study_track : "auto";
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
  const roadmap = Array.isArray(plan.roadmap) ? plan.roadmap : [];
  const trackNames = {auto:"Suggested track",software:"Software engineering",data:"Data science",research:"Research",general:"General preparation",source_only:"Source-linked topics only"};
  $("study-track-label").textContent = (trackNames[plan.study_track || plan.profile?.study_track] || "Suggested track").toUpperCase();
  $("roadmap-note").textContent = (roadmap.length
    ? "One topic at a time, with practice and a stopping point. Source-linked topics are not a source-backed syllabus; recommended guidance is not an employer requirement or a guarantee."
    : "This plan has no topic guidance. Rebuild when you’re ready; the saved plan will not change until you choose to build a new proposal.")
    + (plan.study_track_reason ? " " + plan.study_track_reason : "");
  const legacyRoadmap = roadmap.length > 0 && (!plan.study_track || roadmap.some(entry =>
    !["source_linked","recommended"].includes(entry.basis) ||
    !Array.isArray(entry.learn) || !entry.learn.length ||
    typeof entry.practice !== "string" || !entry.practice.trim() ||
    typeof entry.done_when !== "string" || !entry.done_when.trim()
  ));
  if (!roadmap.length || legacyRoadmap) {
    $("roadmap-list").innerHTML = '<div class="empty-state roadmap-empty"><h3>No study topics in this plan yet.</h3><p>Older plans are kept as they are. Build a new proposal to get topic-first guidance; no topics are invented for this view.</p><button class="primary" type="button" data-rebuild-plan>Build a new topic roadmap <span aria-hidden="true">→</span></button></div>';
    $("roadmap-list").querySelector("[data-rebuild-plan]").onclick = () => {
      $("prep-settings").open = true;
      if ($("study-track").value === "source_only") $("study-track").value = "auto";
      $("plan-btn").click();
    };
    return;
  }
  const ratingOptions = [["","Not rated"],["comfortable","Comfortable"],["review","Needs review"],["new","New to me"],["unsure","Not sure"]];
  const tasksById = new Map((plan.tasks || []).filter(task => task.task_id).map(task => [task.task_id, task]));
  const selectedTopic = roadmap.find(entry => entry.start_here === true);
  $("roadmap-list").innerHTML = roadmap.map((entry, index) => {
    const candidateIds = [...(Array.isArray(entry.task_ids) ? entry.task_ids : []), ...(entry.key ? ["study/" + entry.key + "/v1"] : [])];
    const topicTasks = [...new Set(candidateIds.filter(id => typeof id === "string" && tasksById.has(id)))].map(id => tasksById.get(id));
    const topicTaskIds = topicTasks.map(task => task.task_id);
    const required = Object.entries(entry.required_by || {}).map(([target,names]) => (state.opportunities.find(item => item.id === target)?.program || target) + " · " + (Array.isArray(names) ? names : [names]).map(name => String(name).replaceAll("_"," ")).join(", "));
    const completed = topicTasks.length > 0 ? topicTasks.every(task => task.status === "completed") : entry.task_status === "completed";
    const status = completed ? "completed" : topicTasks.find(task => task.status && task.status !== "completed")?.status || entry.task_status || "not started";
    const allocation = topicTasks.reduce((all, task) => {
      for (const [week, value] of Object.entries(task.week_allocations || {})) all[week] = Number(all[week] || 0) + Number(value || 0);
      return all;
    }, {});
    if (!Object.keys(allocation).length) Object.assign(allocation, entry.week_allocations || {});
    const allocationText = Object.entries(allocation).filter(([, value]) => Number(value) > 0).map(([week, value]) => dateLabel(week) + " · " + hours(value) + "h").join(" / ");
    const links = (Array.isArray(entry.resources) ? entry.resources : []).map(resource => {
      const url = safeUrl(resource?.url);
      return url === "#" ? "" : '<a class="source-link" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(resource.title || "Open learning resource") + ' ↗</a>';
    }).join("");
    const learn = Array.isArray(entry.learn) ? entry.learn.filter(Boolean) : [];
    const title = entry.title || "Untitled topic";
    const completionLabel = completed ? "Undo completion: " + title + " topic practice" : "Mark complete: " + title + " topic practice";
    const checkbox = topicTaskIds.length ? '<button type="button" class="topic-done ' + (completed ? "done" : "") + '" data-topic-complete="' + esc(JSON.stringify(topicTaskIds)) + '" aria-label="' + esc(completionLabel) + '" aria-pressed="' + completed + '">' + (completed ? "Mark not done" : "Mark topic complete") + '</button>' : '<span class="topic-status">Completion task unavailable in this plan</span>';
    const selected = entry === selectedTopic;
    return '<details class="roadmap-item ' + (selected ? "start" : "") + (completed ? " done" : "") + '"' + (selected ? " open" : "") + '><summary class="roadmap-summary"><span class="roadmap-order">' + String(entry.order || index + 1).padStart(2,"0") + '</span><span class="roadmap-summary-main"><span class="roadmap-title"><span class="roadmap-topic-name">' + esc(title) + '</span><span class="badge">' + esc(entry.family || "Topic") + '</span><span class="badge basis-badge">' + (entry.basis === "source_linked" ? "SOURCE-LINKED" : "RECOMMENDED") + '</span>' + (selected ? '<span class="badge start-badge">STUDY NEXT</span>' : '') + '<span class="badge">' + esc(String(status).replaceAll("_"," ").toUpperCase()) + '</span></span><span class="topic-disclosure-hint">' + (selected ? "Selected next topic · details open" : "Open topic details") + '</span></span></summary><div class="roadmap-main">' + (entry.prerequisites?.length ? '<p class="roadmap-prereqs">Builds after: ' + entry.prerequisites.map(value => esc((roadmap.find(item => item.key === value)?.title) || String(value).replaceAll("_"," "))).join(", ") + '</p>' : '') + '<div class="topic-guidance">' + (learn.length ? '<div><strong>Learn</strong><ul>' + learn.map(item => '<li>' + esc(item) + '</li>').join("") + '</ul></div>' : '') + (entry.practice ? '<div><strong>Practice</strong><p>' + esc(entry.practice) + '</p></div>' : '') + (entry.done_when ? '<div><strong>You’re done when</strong><p>' + esc(entry.done_when) + '</p></div>' : '') + '</div><div class="topic-footer"><span class="topic-effort">' + (Number.isFinite(Number(entry.hours_low)) && Number.isFinite(Number(entry.hours_high)) ? esc(hours(entry.hours_low) + "–" + hours(entry.hours_high) + " hours") : "Effort estimate unavailable") + (allocationText ? ' · Scheduled: ' + esc(allocationText) : topicTasks.length ? ' · Not scheduled in a specific week' : "") + '</span><label class="topic-rating">Your level<select data-rating="' + esc(entry.key) + '">' + ratingOptions.map(([value,label]) => '<option value="' + esc(value) + '" ' + (entry.rating === value ? "selected" : "") + '>' + esc(label) + '</option>').join("") + '</select></label>' + checkbox + '</div>' + (links ? '<div class="roadmap-resources">' + links + '</div>' : '<p class="roadmap-required">No learning links are attached to this topic.</p>') + (entry.basis === "source_linked" ? '<p class="roadmap-required">Connected to selected source details; not a complete source-backed syllabus.</p>' : '<p class="roadmap-required">Recommended learning guidance, not an employer requirement or a guarantee.</p>') + (required.length ? '<p class="roadmap-required">Connected source facts: ' + esc(required.join("; ")) + '</p>' : '') + (entry.note ? '<p class="roadmap-item-note">' + esc(entry.note) + '</p>' : '') + '</div></details>';
  }).join("");
  $("roadmap-list").querySelectorAll("[data-topic-complete]").forEach(button => button.onclick = () => toggleCompletion(JSON.parse(button.dataset.topicComplete), state.mode));
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

async function toggleCompletion(taskId, mode = state.mode) {
  return action("Updating your study progress…", async () => {
    if (mode === "simulation") { notify("Update study progress in the main plan. Simulation is a separate review scenario."); return; }
    const updated = profile();
    const ids = Array.isArray(taskId) ? taskId : [taskId];
    const allComplete = ids.length > 0 && ids.every(id => updated.completed_task_ids.includes(id));
    updated.completed_task_ids = allComplete
      ? updated.completed_task_ids.filter(id => !ids.includes(id))
      : [...new Set([...updated.completed_task_ids, ...ids])];
    setPlan(await api("/api/plan", {selected_ids: state.selected, profile: updated}));
    const topicTask = Array.isArray(taskId) || ids.some(id => id.startsWith("study/"));
    notify(!allComplete
      ? (topicTask ? "Topic marked complete. You can undo this any time." : "Preparation work marked complete. You can undo this any time.")
      : (topicTask ? "Topic completion undone." : "Preparation completion undone."));
  });
}

function setPlan(plan, mode = "official") {
  state.plan = plan; state.mode = mode;
  const tasks = Array.isArray(plan.tasks) ? plan.tasks : [];
  const targets = Array.isArray(plan.targets) ? plan.targets : [];
  const profileData = plan.profile || {};
  state.ratings = {...(profileData.skill_ratings || {})};
  state.selected = plan.selected_ids || state.selected;
  if (["auto","software","data","research","general","source_only"].includes(profileData.study_track)) $("study-track").value = profileData.study_track;
  $("plan-empty").classList.add("hidden"); $("plan-content").classList.remove("hidden");
  $("next-action-text").textContent = plan.next_action || "Choose a topic and start with its practice exercise.";
  $("plan-mode-note").textContent = mode === "simulation" ? "SIMULATION · Separate graph. Changed policy is illustrative; official source facts remain unchanged." : "Your profile and progress are self-reported. Studying can continue while an application portal is unavailable.";
  if (state.enrichmentWarnings?.length || plan.warnings?.some(w => /source.*review is incomplete/i.test(w))) $("plan-mode-note").textContent += " Some source details need review.";
  $("metric-effort").textContent = hours(plan.total_hours_low) + "–" + hours(plan.total_hours_high) + " h";
  $("metric-capacity").textContent = hours(plan.available_hours) + " h";
  const shared = tasks.filter(task => task.category === "Shared" && task.status !== "completed");
  $("metric-shared").textContent = hours(shared.reduce((sum, task) => sum + Number(task.hours_high || 0), 0)) + " h";
  $("metric-state").textContent = String(plan.status || "proposed").charAt(0).toUpperCase() + String(plan.status || "proposed").slice(1);
  $("metric-version").textContent = plan.id ? "Version " + String(plan.id).slice(0,8) : "New proposal";
  $("accept-btn").disabled = plan.status !== "proposed";
  const warnings = [...(state.enrichmentWarnings || []), ...(plan.warnings || [])];
  $("plan-warnings").innerHTML = warnings.map(warning => '<div class="warning">' + esc(warning) + '</div>').join("");
  $("budget-summary").textContent = "Study guidance: " + hours(plan.study_hours_low) + "–" + hours(plan.study_hours_high) + " h · Application and other work: " + hours(plan.application_hours_low) + "–" + hours(plan.application_hours_high) + " h. These share one weekly budget.";

  const weeklyUsed = plan.weekly_used || {};
  const weeksSet = new Set(Object.keys(weeklyUsed));
  for (const task of tasks) for (const week of Object.keys(task.week_allocations || {})) weeksSet.add(week);
  let weeks = [...weeksSet].sort();
  if (!weeks.length && profileData.start_date && Number(profileData.horizon_weeks) > 0) {
    const start = new Date(profileData.start_date + "T12:00:00Z");
    if (!Number.isNaN(start.getTime())) for (let i=0; i<Number(profileData.horizon_weeks); i++) {
      const date = new Date(start); date.setUTCDate(date.getUTCDate() + i * 7); weeks.push(date.toISOString().slice(0,10));
    }
  }
  $("timeline").innerHTML = weeks.length ? weeks.map(week => {
    const cap = weekCapacity(profileData, week);
    const used = Number(weeklyUsed[week] || 0);
    const protectedWeek = cap === 0;
    const activities = tasks.map(task => ({task, value: Number(task.week_allocations?.[week] || 0)})).filter(item => item.value > 0);
    const activityMarkup = activities.length
      ? '<ul class="week-activities">' + activities.map(({task, value}) => '<li><span>' + esc(task.title || "Preparation activity") + '</span><b>' + hours(value) + 'h</b></li>').join("") + '</ul>'
      : used > 0 ? '<p class="week-unmapped">Hours are allocated this week, but the plan did not provide activity-level detail.</p>' : '<p class="week-unmapped">No activity scheduled for this week.</p>';
    return '<article class="week-row ' + (protectedWeek ? "exam" : "") + '"><div class="week-title">' + esc(dateLabel(week)) + '<small>' + (protectedWeek ? "PROTECTED / UNAVAILABLE" : "WEEKLY WORK") + '</small></div><div class="week-detail">' + activityMarkup + '</div><div class="week-hours">' + hours(used) + ' / ' + hours(cap) + 'h</div></article>';
  }).join("") : '<div class="week-unavailable">No weekly schedule was returned for this plan. Work is not scheduled rather than assumed.</div>';

  const appBlockers = tasks.filter(task => task.category !== "Study" && task.status !== "completed" && (task.waiting_for || task.status === "waiting" || task.status === "blocked"));
  const requiredHigh = tasks.filter(task => task.status !== "completed").reduce((sum, task) => sum + Math.max(0, Number(task.hours_high || 0)), 0);
  const availableCapacity = Number(plan.available_hours);
  const capacityGap = Number.isFinite(availableCapacity) ? Math.max(0, requiredHigh - availableCapacity) : 0;
  $("priority-blockers").innerHTML = (appBlockers.length
    ? '<div class="blocker-note application-blocker"><strong>' + appBlockers.length + ' application item' + (appBlockers.length === 1 ? "" : "s") + ' may need review.</strong><div class="blocker-actions"><button type="button" class="text-btn" data-open-detail="application-work">Open tasks and reasons</button><button type="button" class="text-btn" data-open-detail="target-check-details">Open target checks</button></div><small>These affect applications only. They do not prevent you from studying.</small></div>'
    : "") + (capacityGap > 0
    ? '<div class="capacity-notice" role="status">Upper-bound work exceeds available capacity by ' + esc(hours(capacityGap)) + ' hours. Make more time or extend the horizon; studying can still happen when it fits.</div>'
    : "");
  $("priority-blockers").querySelectorAll("[data-open-detail]").forEach(button => button.onclick = () => {
    const details = $(button.dataset.openDetail);
    if (details) {
      details.open = true;
      details.scrollIntoView({block:"nearest", behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
    }
  });

  renderRoadmap(plan);
  $("task-list").innerHTML = tasks.length ? tasks.map(task => {
    const completed = task.status === "completed";
    const blocked = !completed && (task.waiting_for || task.status === "waiting" || task.status === "blocked");
    const targetIds = Array.isArray(task.target_ids) ? task.target_ids : [];
    const allocationTotal = Object.values(task.week_allocations || {}).reduce((sum,value) => sum + Number(value || 0),0);
    const taskTitle = task.title || "Preparation work";
    return '<article class="task"><button class="task-check ' + (completed ? "done" : "") + '" data-complete="' + esc(task.task_id) + '" ' + (blocked ? "disabled" : "") + ' aria-label="' + esc(completed ? "Undo completion of " + taskTitle : "Mark " + taskTitle + " complete") + '" aria-pressed="' + completed + '">' + (completed ? "✓" : "") + '</button><div class="task-main"><h4>' + esc(taskTitle) + '</h4><div class="task-meta"><span class="badge ' + (blocked ? "closed" : "") + '">' + esc(String(task.status || "planned").toUpperCase()) + '</span><span>' + esc(task.category || "Preparation") + '</span><span>' + esc(targetIds.length > 1 ? "Supports " + targetIds.length + " targets" : "Target-specific work") + '</span></div>' + (task.reason ? '<p>' + esc(task.reason) + '</p>' : "") + (task.waiting_for ? '<p>' + (completed ? "Receipt marked by you; not independently verified." : "External confirmation is required; estimated work time cannot satisfy it.") + '</p>' : "") + (allocationTotal < Number(task.hours_low || 0) && !completed ? '<p class="task-unscheduled">Not fully scheduled in the weekly plan.</p>' : "") + '</div><span class="task-hours">' + hours(task.hours_low) + '–' + hours(task.hours_high) + 'h</span></article>';
  }).join("") : '<div class="empty-state roadmap-empty"><p>No preparation tasks were returned. Nothing has been invented for this plan.</p></div>';
  $("task-list").querySelectorAll("[data-complete]").forEach(button => button.onclick = () => toggleCompletion(button.dataset.complete, mode));
  for (const [index, task] of tasks.entries()) if ($("task-list").children[index]) $("task-list").children[index].dataset.taskCategory = task.category || "Preparation";
  const taskCategories = ["All", ...["Study","Shared","Research","Company"].filter(category => tasks.some(task => task.category === category))];
  if (!taskCategories.includes(state.taskCategory)) state.taskCategory = "All";
  $("task-filters").innerHTML = taskCategories.map(category => {
    const count = tasks.filter(task => category === "All" || task.category === category).length;
    const label = category === "All" ? "All work" : category === "Study" ? "Study topics" : category === "Shared" ? "Shared foundations" : category;
    return '<button class="filter" data-task-filter="' + esc(category) + '" aria-pressed="' + (category === state.taskCategory) + '">' + esc(label) + ' <span>' + count + '</span></button>';
  }).join("");
  $("task-filters").querySelectorAll("button").forEach(button => button.onclick = () => { state.taskCategory = button.dataset.taskFilter; applyTaskFilter(); });
  applyTaskFilter();
  for (const [index, task] of tasks.entries()) {
    if (!task.waiting_for) continue;
    const container = $("task-list").children[index]?.querySelector(".task-main");
    if (!container) continue;
    const observed = (profileData.received_events || []).includes(task.waiting_for);
    const receipt = document.createElement("button");
    receipt.className = "receipt-btn secondary";
    receipt.textContent = observed ? "Undo my receipt confirmation" : "I confirm this was received";
    receipt.disabled = mode === "simulation";
    receipt.onclick = () => action("Saving your receipt confirmation…", async () => {
      const updated = profile();
      updated.received_events = observed ? updated.received_events.filter(event => event !== task.waiting_for) : [...updated.received_events, task.waiting_for];
      setPlan(await api("/api/plan", {selected_ids: state.selected, profile: updated}));
      notify("Your receipt confirmation was saved. Delivery has not been checked independently.");
    });
    container.appendChild(receipt);
  }
  $("target-checks").innerHTML = targets.length ? targets.map(target => {
    const op = state.opportunities.find(item => item.id === target.target_id);
    const scheduleStatus = String(target.schedule_status || "unknown");
    return '<div class="check-card"><h4>' + esc(op?.program || target.target_id) + '</h4><span class="badge ' + (scheduleStatus === "infeasible" || target.eligibility === "not_eligible" ? "closed" : "unknown") + '">' + esc(scheduleStatus.replaceAll("_"," ").toUpperCase()) + '</span><p>' + esc((target.reasons || []).join(" ")) + '</p>' + (target.criteria || []).slice(0,5).map(criterion => '<div class="criteria-item"><strong>' + esc(String(criterion.status || "unknown").replaceAll("_"," ")) + '</strong><span>' + esc(criterion.explanation) + '</span></div>').join("") + '</div>';
  }).join("") : '<p class="muted">No target checks were returned for this plan.</p>';
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
  showStep("plan");
  if (state.plan?.roadmap?.length && state.plan.study_track !== "source_only") {
    $("plan-content").scrollIntoView({block:"start", behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
    notify("Your study roadmap is ready. Start with the highlighted topic; application checks are separate.");
  } else {
    notify("Source-linked preparation proposal built. Review application checks before saving.");
  }
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
  let result;
  try {
    result = await api("/api/health");
  } catch {
    $("health-text").textContent = "Server unavailable";
    $("db-dot").classList.add("off");
    $("agent-status").textContent = "Browser Agent status unavailable";
    notify("The app server could not be reached. Refresh the page or check that PathWeave is running.", true);
    return;
  }
  const healthy=!!(result.database?.healthy || result.database?.status==="ok" || result.database?.ok);
  $("health-text").textContent=healthy?"FalkorDB connected":"Graph not connected"; $("db-dot").classList.toggle("off",!healthy);
  const agentEnabled = result.discovery?.agent_enabled === true;
  $("agent-status").textContent = agentEnabled ? "TinyFish browser Agent enabled · metered fallback" : "TinyFish browser Agent off · Search/Fetch separate";
  $("agent-status").title = result.discovery?.agent_gate || "This is separate from Groq's preparation agent. Configuration does not prove a live run.";
  if (!healthy) {
    notify("FalkorDB is not connected. You can explore interests and set search preferences; saved targets and preparation plans need the graph database.", true);
    updateSelected();
    return;
  }
  try {
    const saved=await api("/api/opportunities"); state.opportunities=saved.opportunities || [];
    const previous=await api("/api/plan/latest");
    if(previous.plan && !busy && !state.plan){ fillProfile(previous.plan.profile); setPlan(previous.plan); if(!state.hunt)notify("Saved preparation plan recovered from FalkorDB."); }
    updateSelected();
  } catch {
    $("health-text").textContent = "Saved data unavailable";
    notify("The server is running, but saved preparation data could not be loaded. Check the graph connection before building or updating a plan.", true);
  }
}
init();
