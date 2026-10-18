# PathWeave — laptop demo recording guide

Prepared October 18, 2026 (IST). Suggested runtime: about three minutes, not a
verified event requirement. This guide replaces the obsolete cached-example,
receipt and policy-simulation walkthrough.

## Recording status and evidence boundary

This is a script and shot list, not a finished recording or proof of a new run.
No video footage was supplied in this workspace when the guide was prepared.
The user will supply silent raw footage; the agent is to cut it and add
voiceover. The task remains in progress until that footage is processed.
Record the real laptop app with its existing FalkorDB Docker server. The
imported Replit workspace is not evidence that the laptop's saved plans work.
Do not use browser-test fixtures as live application footage.

Source: current `docs/project-handoff.md` and the UI controls in
`app/static/index.html`, `app/static/scout.js` and `app/static/app.js`.
The laptop can differ from the imported code: verify the visible controls first.

## Before recording

1. Open `http://127.0.0.1:18080/` on the laptop with its existing database running.
   Do not delete/recreate the Docker volume, rename its graph or reset saved data.
2. Keep the cream/orange theme. Close personal tabs and enable Do Not Disturb.
3. Use the same browser workspace that contains the saved search; plans are
   browser-scoped. Do not clear browser storage or switch to private browsing.
4. On macOS, press Command-Shift-5 and choose Record Selected Portion. Frame the
   app, avoiding unrelated desktop content. Start at 100% browser zoom; reduce
   slightly only if needed. Ensure text remains readable.
5. Record silently. One continuous recording is sufficient; six separate clips
   are optional. Pause for three to five seconds on important screens. There is
   no need to speak, pre-edit or remove loading waits: the agent will cut the
   raw recording and add narration matching the actual footage.
6. Rehearse once without recording. Confirm that "What are you preparing for?"
   and "Study by topic" exist on the laptop. An old saved plan may need the
   explicit "Build a new topic roadmap" path. If the new controls are absent,
   stop and resolve the local version mismatch rather than substituting fixtures.
7. Use an existing saved, relevant software internship posting. HENNGE is only
   an example if that posting is actually present and relevant; no new hunt is
   needed for this guide. Do not silently pair an unrelated research target with
   software preparation. If only research targets are available, choose Research
   and change the narration to match what the actual plan shows.
8. Check that at least one topic has a completion task and practice/resources
   before recording. If it does not, record the actual limitation or stop for a
   focused fix; do not fake completion or resource content.

## Exact fictional-student inputs

Say the student profile is fictional. Do not enter personal documents or imply
that these values establish the participant's actual qualifications.

| Field | Input |
| --- | --- |
| Hours available per week | 6 |
| Preparation starts | October 19, 2026 |
| Mon / Tue / Wed / Thu / Fri / Sat / Sun | 1 / 0 / 1 / 0 / 1 / 2 / 1 hours |
| Exam week starting Monday | November 2, 2026; click Add exam week |
| Single day off | October 24, 2026; click Add day off |
| Applicant country under Your background | India |
| Degree | BTech |
| Field of study | Computer science |
| Current study year / Total degree years | 2 / 4 |
| Institution type | Other institution |
| What are you preparing for? | Software engineering |
| Planning horizon (weeks) | 8 |

The daily pattern totals six hours. Explicit zeroes make unavailable days clear.
Keep the restored search's actual settings: placeholder examples such as
"Amazon, OIST, EPFL" are not values that must all be entered. Do not edit search
settings and then imply the old results were retrieved using the changed settings.
The optional background fields can be left unknown in ordinary use; the values
above are just a consistent fictional recording example.

## Six recording sections and planned agent voiceover

The "Say" text below is for the agent's later voiceover, not instructions for
the user to speak during recording. Final wording and timing must follow the
supplied footage; do not generate speech before checking what the video shows.

### 01 — Introduction (0:00–0:15)

**Shoot:** PathWeave opening screen and "I know what I'm looking for."
Skip the 12-question explorer for this concise version.

**Say:** "PathWeave helps students move from internship discovery to a practical
preparation roadmap. I'll demonstrate it locally using a fictional student profile."

### 02 — Select an actual target (0:15–0:45)

**Shoot:** Saved searches -> Open a saved search -> select the hunt -> Open hunt.
Open "Filter evidence & source details" on a relevant existing posting. Pause on
its read date and an actual excerpt. Click "+ Prepare for this", then
"Next: your available time". One target is sufficient.

**Say:** "These results came from an earlier search. I can inspect the posting
evidence and choose a target. Missing details stay unknown, and the preference
score is not a selection probability."

If the only relevant card is under "Unconfirmed coverage / location", show that
label and describe it as an unconfirmed lead, not a confirmed match. A stored
LIVE label describes its earlier retrieval mode, not a fresh verification.

### 03 — Time and track (0:45–1:20)

**Shoot:** Enter the table's availability, add the exam week/day-off chips, expand
"Your background", choose Software engineering under "What are you preparing
for?", and click "Build my roadmap".

**Say:** "This example student has six hours a week, with specific available days,
an exam week and a day off. I choose software engineering preparation explicitly.
Suggested study guidance is separate from confirmed employer requirements."

Remove uneventful processing waits with a clean cut or a "Processing wait
shortened" caption. Do not hide an error or splice another plan in as its result.
Source/application work has capacity priority, so not every study topic is
guaranteed to be scheduled in the first week.

### 04 — Topic-wise roadmap (1:20–2:05)

**Shoot:** "Study by topic", its ordered topics and the next-topic marker.
Open one topic to show Learn, Practice, You're done when, an actual resource
link, and its RECOMMENDED or SOURCE-LINKED badge. Pause so the text is readable.
Read one real practice instruction from the screen; no fixed topic title is
promised by this script. A resource can be shown as a link; if opening it,
precheck that page and return to the app after a brief shot.

**Say:** "The roadmap gives me a topic sequence, concrete practice, learning
resources and a completion criterion. Recommended topics are study guidance—not
a claim that this employer tests them."

Do not describe authored resources as automatically discovered or
employer-endorsed. SOURCE-LINKED does not establish an employer-backed syllabus.

### 05 — Weekly allocation and reversible progress (2:05–2:35)

**Shoot:** The weekly plan and protected dates where visible. Only describe the
allocation actually displayed. On a topic with a completion task, click
"Mark topic complete", pause for the changed state, then click "Mark not done".
This is a demonstration of the control, not a claim that the exercise was done.

**Say:** "The weekly plan uses my available capacity. Progress is self-reported:
I can mark practice complete and undo it. That does not certify mastery or
eligibility."

If any update fails, keep it out of success narration and get the failure
resolved or state the limitation. Do not claim automatic adaptive replanning
beyond what the observed interaction demonstrates.

### 06 — Separate evidence and close (2:35–3:00)

**Shoot:** "Why this plan?" and an actual graph path/source excerpt. Separate
the learning view from "Warnings and source gaps", "Application tasks and other
preparation" and "Target checks". Return using "Back to my roadmap" and end on
"Study by topic".

**Say:** "FalkorDB connects source facts, topics, prerequisites and resources.
Deterministic code schedules the work. Source gaps remain visible, so a study
recommendation does not become an employer requirement."

Only show evidence returned by this actual plan. If a particular path or source
is missing, do not insert a fabricated response or an old test capture.

## Optional save shot — only after an observed successful run

The new roadmap's live FalkorDB save/resume check is separate outstanding work.
Do not include a persistence claim by default. If independently observed on the
laptop: click "Save this plan", reload in the same browser, open "My roadmap",
and verify the same selected target and state before describing recovery.
This changes the saved plan; do it only if replacing the current accepted plan
is intended. Never restart/delete storage merely to create a recording effect.

## Do not record as current functionality

- Historical Load sourced examples, policy simulation or synthetic-receipt UI.
- Browser-test fixtures represented as live backend/graph functionality.
- Fresh-search claims over saved results, hidden source gaps or invented funding.
- Timetable-file ingestion, tested competence, automatic application submission,
  guaranteed eligibility or interview success.
- "Run again", "Refresh source" or "Review with Groq" solely for activity footage.
  They are unnecessary external work, not a recording prerequisite.
- API keys, environment files, browser storage tokens, personal documents or
  unrelated terminal output.

## Footage handoff and editing

Send the original silent MOV/MP4 recording without pre-editing it. One file is
fine. If recording separately, optional names are `01-intro`, `02-target`,
`03-time-track`, `04-topics`, `05-progress`, `06-evidence`. Preserve the original
resolution and uncut files. The agent will produce and synchronize the voiceover;
no spoken contribution or separate narration file is required from the user.
Do not send credentials or private documents.

No footage has been edited yet. When supplied, edits can trim pauses, join the
actual sequence and add readable captions. Missing behavior must be identified
for a reshoot, never manufactured. Any titles/captions should retain cream and
orange; preserve uncertainty labels. Review the finished video for readable
text, accidental private content, audio clarity and claims matching the shots.

Recording/export is not authorization to upload publicly, publish the app or
submit the event form. Obtain the applicable authorization separately.
