/**
 * Dependency-free Chromium smoke check for the actual frontend.
 * Uses explicitly synthetic API responses, never live providers or graph writes.
 * Run: node --experimental-websocket scripts/check_responsive_ui.mjs
 * Optional: UI_TEST_URL=https://... CHROMIUM_PATH=/path/to/chromium
 */
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:net";

const base = process.env.UI_TEST_URL || `https://${process.env.REPLIT_DEV_DOMAIN}`;
assert(!base.includes("undefined"), "Set UI_TEST_URL or REPLIT_DEV_DOMAIN");
const directory = "generated-artifacts/responsive-ui";
await mkdir(directory, { recursive: true });
const profileDirectory = await mkdtemp(join(tmpdir(), "pathweave-ui-"));
const reservation = createServer();
await new Promise(resolve => reservation.listen(0, "127.0.0.1", resolve));
const port = reservation.address().port;
await new Promise(resolve => reservation.close(resolve));
const chrome = spawn(process.env.CHROMIUM_PATH || "/repl/tools/bin/chromium", [
  "--headless", "--no-sandbox", "--disable-dev-shm-usage",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profileDirectory}`,
  "--no-first-run", "--no-default-browser-check", "about:blank",
], { stdio: ["ignore", "ignore", "ignore"] });
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
let client;

class CDP {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.sequence = 0;
    this.pending = new Map();
    this.handlers = new Map();
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", event => {
      const data = JSON.parse(event.data);
      if (data.id) {
        const request = this.pending.get(data.id);
        if (!request) return;
        clearTimeout(request.timer);
        this.pending.delete(data.id);
        data.error ? request.reject(new Error(JSON.stringify(data.error))) : request.resolve(data.result);
      } else {
        for (const handler of this.handlers.get(data.method) || []) handler(data.params);
      }
    });
  }
  on(method, handler) {
    this.handlers.set(method, [...(this.handlers.get(method) || []), handler]);
  }
  async send(method, params = {}) {
    await this.ready;
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, 20000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression, awaitPromise: true, returnByValue: true,
    });
    assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
}

const listing = {
  id: "ui-fixture-target", title: "Software Engineering and Scientific Computing Internship",
  organization: "Synthetic University Research Laboratory",
  locations: ["Germany"], cycle: "2027", kind: "job", score: 85,
  summary: "Synthetic UI fixture only. Python and algorithms with source-linked requirements.",
  call_status: "unknown", visa_status: "unknown", funding_level: "paid", is_new: true,
  deadline_text: null, deadline_precision: "unknown", funding_note: "Funding details remain unknown.",
  requirements: [{ name: "skills", kind: "requirement", status: "known", excerpt: "Python and algorithms required." }],
  reasons: ["Advisory role fit, not eligibility certification."],
  apply_url: "https://example.org/internships/fixture", found_via: "search",
  checked_at: "2026-10-18T10:00:00Z", saved: false, hidden: false,
};
const hunt = { id: "ui-fixture-hunt", name: "Synthetic UI check", preferences: {}, result: { listings: [listing] } };
const run = {
  id: "ui-fixture-run", hunt: hunt.id, status: "partial", error: null,
  events: ["search", "fetch", "extract", "match"].map(stage => ({ stage, message: `Synthetic ${stage} stage.` })),
};
const fixtureProfile = {
  start_date: "2026-10-19", horizon_weeks: 4, weekly_hours: 6,
  exam_weeks: ["2026-11-02"], holidays: ["2026-10-25"],
  weekly_pattern: {}, skill_ratings: {}, received_events: [],
};
function buildFixturePlan(request = {}) {
  const result = spawnSync("python", ["-m", "scripts.study_ui_fixture"], {
    input: JSON.stringify({target_id: listing.id, ...request}),
    encoding: "utf8", timeout: 10000,
  });
  assert.equal(result.status, 0, result.stderr || "Offline planner fixture failed");
  return JSON.parse(result.stdout);
}
const plan = buildFixturePlan();

try {
  let target;
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
      break;
    } catch { await wait(100); }
  }
  assert(target?.webSocketDebuggerUrl, "Chromium did not start");
  client = new CDP(target.webSocketDebuggerUrl);
  const errors = [];
  const unexpectedRequests = [];
  let graphUnavailable = false;
  let fixtureWithSource = false;
  const planRequests = [];
  let graphReadsWhileDisconnected = 0;
  client.on("Runtime.exceptionThrown", event => errors.push(event.exceptionDetails.text));
  client.on("Fetch.requestPaused", event => {
    const path = new URL(event.request.url).pathname;
    let data;
    if (path === "/api/health") data = { database: { status: graphUnavailable ? "unavailable" : "ok", healthy: !graphUnavailable }, provider_configured: { groq: true, tinyfish: true }, app_version: "UI fixture" };
    else if (path === "/api/hunts") data = event.request.method === "POST" ? { hunt, run } : { hunts: [] };
    else if (path === `/api/hunts/${hunt.id}`) data = hunt;
    else if (path === `/api/hunts/${hunt.id}/listings`) data = { listings: [listing] };
    else if (path === `/api/discovery-runs/${run.id}`) data = run;
    else if (path === "/api/opportunities") data = { opportunities: [] };
    else if (path === "/api/plan/latest") data = { plan: null };
    else if (path === "/api/plan") {
      const request = JSON.parse(event.request.postData || "{}");
      planRequests.push(request);
      data = buildFixturePlan({...request, with_source: fixtureWithSource});
    }
    else if (path.endsWith("/flags")) data = JSON.parse(event.request.postData || "{}");
    else if (path === "/api/interest-scenarios") {
      client.send("Fetch.continueRequest", { requestId: event.requestId }).catch(error => errors.push(error.message));
      return;
    } else {
      unexpectedRequests.push(path);
      data = { detail: "Unexpected endpoint in UI fixture" };
    }
    if (graphUnavailable && ["/api/opportunities", "/api/plan/latest"].includes(path)) graphReadsWhileDisconnected++;
    client.send("Fetch.fulfillRequest", {
      requestId: event.requestId, responseCode: unexpectedRequests.includes(path) ? 400 : 200,
      responseHeaders: [{ name: "Content-Type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(data)).toString("base64"),
    }).catch(error => errors.push(error.message));
  });
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Fetch.enable", { patterns: [{ urlPattern: "*/api/*" }] });
  await client.send("Page.navigate", { url: base });
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await client.evaluate("typeof showStep === 'function' && typeof startExploration === 'function' && document.readyState === 'complete'")) break;
    await wait(100);
  }
  await client.evaluate("localStorage.removeItem('scout-active-hunt'); localStorage.removeItem('scout-selected')");
  await wait(500);
  await client.evaluate(`window.__fixtureHunt = ${JSON.stringify(hunt)}; window.__fixturePlan = ${JSON.stringify(plan)};`);
  const stages = ["start", "explore", "search", "results", "time", "roadmap", "evidence"];
  const report = [];
  for (const width of [320, 375, 430, 768, 1024, 1440]) {
    await client.send("Emulation.setDeviceMetricsOverride", {
      width, height: 900, deviceScaleFactor: 1, mobile: width < 600,
    });
    for (const stage of stages) {
      if (stage === "start") await client.evaluate("showStep('discover','start')");
      if (stage === "explore") await client.evaluate("startExploration()");
      if (stage === "search") await client.evaluate("showStep('discover','search'); showSearch(); document.querySelector('#advanced-preferences').open=true");
      if (stage === "results") await client.evaluate("(async()=>{state.hunt=window.__fixtureHunt; state.listings=window.__fixtureHunt.result.listings; state.useHuntSelection=true; state.listingSelected=[]; state.selected=[]; showStep('discover','results'); await renderScoutCards(); updateSelected()})()");
      if (stage === "time") await client.evaluate("document.querySelector('[data-listing]').click(); document.querySelector('#setup-plan-btn').click(); document.querySelector('#prep-settings').open=true; document.querySelectorAll('#prep-settings details').forEach(el=>el.open=true)");
      if (stage === "roadmap") await client.evaluate("setPlan(window.__fixturePlan); showStep('plan','roadmap'); document.querySelector('#prep-settings').open=false; document.querySelector('#plan-content').scrollIntoView({block:'start'})");
      if (stage === "evidence") await client.evaluate("showStep('evidence','evidence')");
      await wait(350);
      await client.evaluate("window.scrollTo(0,0)");
      const layout = await client.evaluate(`(() => {
        const width = window.innerWidth;
        const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
        const overflowing = [...document.querySelectorAll('body *')].filter(el => {
          if (!visible(el)) return false;
          const r = el.getBoundingClientRect();
          return r.right > width + 1 || r.left < -1;
        }).slice(0,12).map(el=>({tag:el.tagName,id:el.id,class:typeof el.className==='string'?el.className:'',right:Math.round(el.getBoundingClientRect().right)}));
        const activeNav = document.querySelector('.journey-step[aria-current="step"]');
        const navRect = activeNav?.getBoundingClientRect();
        const clipping = [...document.querySelectorAll('button,input,select,textarea')].filter(el => visible(el) && !el.disabled && el.getBoundingClientRect().width < 24).map(el=>el.id||el.className);
        const chrome = ['.topbar','footer'].map(selector => {
          const el=document.querySelector(selector), r=el.getBoundingClientRect();
          return {selector,left:r.left,width:r.width,padding:parseFloat(getComputedStyle(el).paddingLeft)};
        });
        return {scrollWidth:document.documentElement.scrollWidth,width,availableWidth:document.documentElement.clientWidth,overflowing,clipping,chrome,
          activeNavVisible:!navRect || (navRect.left>=-1 && navRect.right<=width+1),
          stage:document.body.dataset.story};
      })()`);
      report.push({ width, stage, ...layout });
      assert(layout.scrollWidth <= width + 1, `${width}/${stage}: horizontal page overflow ${JSON.stringify(layout)}`);
      assert(layout.overflowing.length === 0, `${width}/${stage}: offscreen elements ${JSON.stringify(layout.overflowing)}`);
      assert(layout.activeNavVisible, `${width}/${stage}: current step is offscreen`);
      for (const frame of layout.chrome) {
        assert(Math.abs(frame.left) <= 1 && Math.abs(frame.width - layout.availableWidth) <= 1,
          `${width}/${stage}: ${frame.selector} does not span the viewport`);
        assert(frame.padding >= 20 && frame.padding <= 48, `${width}/${stage}: excessive app chrome padding`);
      }
      if ([375, 1440].includes(width)) {
        const shot = await client.send("Page.captureScreenshot", { format: "jpeg", quality: 75, captureBeyondViewport: false });
        await writeFile(`${directory}/${stage}-${width}.jpg`, Buffer.from(shot.data, "base64"));
        const section = { explore: "#interest-explorer", search: "#search-form", results: "#opportunity-cards", time: "#prep-settings", roadmap: "#roadmap-list", evidence: "#evidence-list" }[stage];
        if (section) {
          await client.evaluate(`document.querySelector(${JSON.stringify(section)}).scrollIntoView({block:'start'})`);
          const contentShot = await client.send("Page.captureScreenshot", { format: "jpeg", quality: 75, captureBeyondViewport: false });
          await writeFile(`${directory}/${stage}-content-${width}.jpg`, Buffer.from(contentShot.data, "base64"));
        }
      }
    }
  }
  // Exercise the actual new controls against real, offline planner responses.
  // No public fixture endpoint or sign-in bypass is added to the application.
  await client.evaluate("setPlan(window.__fixturePlan); showStep('plan','roadmap'); state.useHuntSelection=false");
  assert.equal(await client.evaluate("document.querySelectorAll('#roadmap-list details[open]').length"), 1,
    "Only the selected topic should initially expose all learning detail");
  assert.equal(await client.evaluate("document.querySelector('#plan-warnings').closest('details').open"), false);
  assert.equal(await client.evaluate("document.querySelector('#target-checks').closest('details').open"), false);
  assert.equal(await client.evaluate("document.querySelectorAll('.week-activities li').length > 0"), true);
  const firstTask = plan.roadmap.find(entry => entry.start_here).task_ids[0];
  async function until(expression, message) {
    for (let attempt=0; attempt<60; attempt++) {
      if (await client.evaluate(expression)) return;
      await wait(50);
    }
    assert.fail(message);
  }
  await client.evaluate("document.querySelector('#roadmap-list details[open] [data-topic-complete]').click()");
  await until(`state.plan.tasks.find(task=>task.task_id===${JSON.stringify(firstTask)})?.status==='completed'`,
    "Recommended topic completion did not round-trip through /api/plan");
  await client.evaluate(`document.querySelector('#roadmap-list [data-topic-complete*="${firstTask}"]').click()`);
  await until(`state.plan.tasks.find(task=>task.task_id===${JSON.stringify(firstTask)})?.status!=='completed'`,
    "Recommended topic completion could not be undone");
  assert.equal(planRequests.at(-1).profile.study_track, "software");

  fixtureWithSource = true;
  const sourcePlan = buildFixturePlan({with_source: true, profile: {study_track: "source_only"}});
  await client.evaluate(`setPlan(${JSON.stringify(sourcePlan)})`);
  await client.evaluate("document.querySelector('#roadmap-list [data-topic-complete]').click()");
  await until("state.plan.tasks.find(task=>task.task_id==='shared/skill-python-foundation/v1')?.status==='completed'",
    "Source-linked topic completion control did not use its real task ID");
  fixtureWithSource = false;

  const zeroPlan = buildFixturePlan({profile: {weekly_hours: 0}});
  await client.evaluate(`setPlan(${JSON.stringify(zeroPlan)})`);
  assert.match(await client.evaluate("document.querySelector('#next-action-text').textContent"), /Make time/);
  assert.equal(await client.evaluate("document.querySelectorAll('#roadmap-list .start-badge').length"), 0);
  assert.equal(await client.evaluate("document.querySelectorAll('#roadmap-list details[open]').length"), 0);

  const legacyPlan = structuredClone(plan);
  legacyPlan.study_track = "source_only";
  legacyPlan.profile.study_track = "source_only";
  legacyPlan.roadmap = [];
  await client.evaluate(`setPlan(${JSON.stringify(legacyPlan)}); document.querySelector('#plan-btn').disabled=false; document.querySelector('[data-rebuild-plan]').click()`);
  await until("state.plan.study_track!=='source_only' && state.plan.roadmap.length>0",
    "Rebuilding an old plan did not switch to an actual study track");
  assert.equal(planRequests.at(-1).profile.study_track, "auto");

  const unsafePlan = structuredClone(plan);
  unsafePlan.roadmap[0].title = '<img src=x onerror="window.__xssFired=1">';
  unsafePlan.roadmap[0].resources = [{title: "Unsafe URL", url: "javascript:window.__xssFired=1"}];
  await client.evaluate(`setPlan(${JSON.stringify(unsafePlan)})`);
  assert.equal(await client.evaluate("!!window.__xssFired || !!document.querySelector('#roadmap-list img')"), false);
  assert.equal(await client.evaluate("!!document.querySelector('#roadmap-list a[href^=\"javascript:\"]')"), false);
  await client.evaluate("setPlan(window.__fixturePlan)");

  await client.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  await client.evaluate("showStep('discover','start')");
  assert.equal(await client.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"), true);
  const motionCount = await client.evaluate("document.getAnimations().filter(a=>a.playState==='running' && a.effect?.getTiming().duration>1).length");
  assert.equal(motionCount, 0, "Reduced motion leaves long animations running");
  await client.evaluate("document.querySelector('.journey-step').focus()");
  await client.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
  await client.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
  const keyboard = await client.evaluate(`(() => {
    const el=document.activeElement, css=getComputedStyle(el);
    return {tag:el.tagName,outline:css.outlineStyle,outlineWidth:css.outlineWidth,visible:el.matches(':focus-visible')};
  })()`);
  assert.equal(keyboard.tag, "BUTTON");
  assert.equal(keyboard.visible, true, "Keyboard focus is not visible");
  assert.notEqual(keyboard.outline, "none", "No visible keyboard focus");
  const preservedIds = await client.evaluate(`(() => {const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);return {count:ids.length,unique:new Set(ids).size}})()`);
  assert.equal(preservedIds.count, preservedIds.unique, "Duplicate HTML IDs");
  assert.deepEqual(errors, [], "Browser JavaScript errors");
  assert.deepEqual(unexpectedRequests, [], "Unexpected API calls");
  graphUnavailable = true;
  await client.evaluate("init()");
  assert.equal(await client.evaluate("document.querySelector('#health-text').textContent"), "Graph not connected");
  assert.match(await client.evaluate("document.querySelector('#notification').textContent"), /FalkorDB is not connected/);
  assert.equal(graphReadsWhileDisconnected, 0, "Disconnected startup still queries graph-backed endpoints");
  await writeFile(`${directory}/report.json`, JSON.stringify({ mode: "synthetic frontend fixtures, no live graph/provider verification", report, keyboard, motionCount, graphReadsWhileDisconnected, errors }, null, 2));
  console.log(`PASS: ${report.length} screen/viewport checks; topic disclosure, real offline-planner completion/undo, source task completion, legacy rebuild, zero capacity, output escaping, focus, reduced motion and disconnected state. No live graph/provider writes.`);
} finally {
  client?.socket.close();
  chrome.kill("SIGTERM");
  await wait(250);
  await rm(profileDirectory, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
