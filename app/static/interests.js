// Authored activity preferences. No diagnosis, aptitude score or model inference.
let explorationData = null;
let explorationIndex = 0;
let explorationAnswers = {};
const explorationRatings = [
  [3, "I'd enjoy trying this"], [2, "I'm curious about it"], [0, "This doesn't appeal to me"],
  [null, "Haven't tried / not sure"]
];
const explorationKey = "interest-exploration:" + browserToken();
function storeExploration() {
  localStorage.setItem(explorationKey, JSON.stringify({version: explorationData.version, answers: explorationAnswers}));
}
async function startExploration() {
  showStep("discover", "explore");
  if (!explorationData) {
    const response = await fetch('/api/interest-scenarios');
    if (!response.ok) throw new Error('Interest scenarios could not load. You can enter your interests directly.');
    explorationData = await response.json();
    try {
      const saved = JSON.parse(localStorage.getItem(explorationKey) || '{}');
      if (saved.version === explorationData.version && saved.answers && typeof saved.answers === 'object') explorationAnswers = saved.answers;
    } catch { explorationAnswers = {}; }
  }
  $('interest-explorer').classList.remove('hidden');
  $('explore-btn').setAttribute('aria-expanded', 'true');
  $('explore-note').textContent = explorationData.notice;
  if (explorationData.scenarios.every(s=>Object.hasOwn(explorationAnswers,s.id))) showDirections();
  else renderScenario();
  $('explore-heading').scrollIntoView({block:'start'});
}
function renderScenario() {
  const scenario = explorationData.scenarios[explorationIndex];
  const answer = explorationAnswers[scenario.id];
  $('explore-heading').textContent = 'Try the work in your imagination.';
  $('explore-note').textContent = explorationData.notice;
  $('interest-cards').innerHTML = '<article class="scenario-card"><div class="scenario-progress">' + (explorationIndex + 1) + ' / ' + explorationData.scenarios.length + ' · ' + esc(scenario.context) + '</div><h3>' + esc(scenario.title) + '</h3><p>' + esc(scenario.problem) + '</p><div class="scenario-work"><strong>What you would do</strong><p>' + esc(scenario.activity) + '</p></div><fieldset><legend>' + esc(scenario.question) + '</legend>' + explorationRatings.map(([rating, label], index) => '<label class="scenario-answer"><input type="radio" name="scenario-rating" value="' + index + '" ' + (answer === rating && Object.hasOwn(explorationAnswers,scenario.id) ? 'checked' : '') + '><span>' + esc(label) + '</span></label>').join('') + '</fieldset></article>';
  $('interest-cards').querySelectorAll('input').forEach(input => input.onchange = () => {
    explorationAnswers[scenario.id] = explorationRatings[Number(input.value)][0]; storeExploration();
  });
  $('explore-back').disabled = explorationIndex === 0;
  $('explore-back').classList.remove('hidden');
  $('explore-next').classList.remove('hidden');
  $('explore-next').textContent = explorationIndex === explorationData.scenarios.length - 1 ? 'See possible directions →' : 'Next project →';
  $('explore-apply').classList.add('hidden');
  $('explore-retest').classList.add('hidden');
  $('explore-skip-question').classList.remove('hidden');
}
function directionScores(data, answers) {
  return Object.entries(data.directions).map(([id, direction]) => {
    const answered = data.scenarios.filter(s => s.direction === id && [0,2,3].includes(answers[s.id]));
    const interested = answered.filter(s => answers[s.id] >= 2);
    return {id, ...direction, score: answered.reduce((sum,s)=>sum+answers[s.id],0), answered: answered.length, interested};
  }).filter(d=>d.interested.length).sort((a,b)=>b.score-a.score || b.interested.length-a.interested.length);
}
function showDirections() {
  const directions = directionScores(explorationData, explorationAnswers);
  const recommended = directions.slice(0,3);
  const pending = explorationData.scenarios.filter(s => ![0,2,3].includes(explorationAnswers[s.id])).length;
  const broad = directions.length > 3 && directions[2].score === directions[3].score;
  $('explore-heading').textContent = 'Directions you might like to explore.';
  $('interest-cards').innerHTML = (recommended.length ? '<div class="direction-summary">Your answers suggest these starting points. ' + (pending ? pending + ' projects were skipped or uncertain, so this picture is partial.' : 'These describe interest, not demonstrated ability.') + '</div>' + recommended.map(d=>'<label class="direction-card"><input type="checkbox" data-direction="'+esc(d.id)+'" checked><span class="eyebrow">POSSIBLE DIRECTION</span><h3>'+esc(d.label)+'</h3><p>You were curious about ' + d.interested.length + ' of its 2 projects: ' + esc(d.interested.map(s=>s.title).join('; ')) + '.</p><strong>A small thing to try</strong><p>'+esc(d.try_it)+'</p></label>').join('') : '<div class="empty-state"><h3>We don’t have enough interest signals yet.</h3><p>Try another project, retake the questions, or enter interests yourself. We won’t invent a direction from uncertain answers.</p></div>') + '<label class="interest-edit">Add or change roles / interests<input id="explore-edited-roles" placeholder="Software engineering intern, robotics intern…" maxlength="600"><small>Up to 5. These stay editable in search.</small></label>';
  $('explore-back').classList.add('hidden');
  $('explore-next').classList.add('hidden');
  $('explore-skip-question').classList.add('hidden');
  $('explore-retest').classList.remove('hidden');
  $('explore-apply').classList.remove('hidden');
  $('explore-note').textContent = broad ? 'Several directions have equal signals. These are starting options, not a clear ranking. You can add another direction or retake the questions.' : 'Recommendations come from the activities you chose. Company work and research can overlap. Edit freely; there is no right career answer.';
}
$('explore-back').onclick=()=>{if(explorationIndex>0){explorationIndex--;renderScenario();}};
$('explore-next').onclick=()=>{
  const scenario=explorationData.scenarios[explorationIndex];
  if(!Object.hasOwn(explorationAnswers,scenario.id)) { $('explore-note').textContent='Choose how you feel, select “not sure”, or skip this project.'; return; }
  if(explorationIndex < explorationData.scenarios.length-1){explorationIndex++;renderScenario();}else showDirections();
};
$('explore-skip-question').onclick=()=>{explorationAnswers[explorationData.scenarios[explorationIndex].id]=null;storeExploration();if(explorationIndex<explorationData.scenarios.length-1){explorationIndex++;renderScenario();}else showDirections();};
$('explore-retest').onclick=()=>{explorationAnswers={};explorationIndex=0;storeExploration();renderScenario();};
$('explore-apply').onclick=()=>{
  const chosen=[...$('interest-cards').querySelectorAll('[data-direction]:checked')].map(input=>explorationData.directions[input.dataset.direction]);
  const edits=$('explore-edited-roles').value.split(',').map(v=>v.trim()).filter(Boolean);
  const roles=[...new Set([...chosen.map(d=>d.role),...edits])];
  if(!roles.length || roles.length>5 || roles.some(v=>v.length>120)){ $('explore-note').textContent='Choose or enter 1–5 roles, up to 120 characters each.'; return; }
  $('search-query').value=roles.join(', ');
  const keywords=[...new Set(chosen.flatMap(d=>d.keywords))];
  $('search-keywords').value=keywords.join(', ');
  showSearch(); notify('Your suggested roles and keywords are ready to edit. Search starts only when you choose Find opportunities.');
};
$('explore-btn').onclick=()=>{startExploration().catch(error=>notify(error.message,true));};
$('explore-skip').onclick=()=>showSearch();
