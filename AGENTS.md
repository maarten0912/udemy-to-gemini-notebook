# Playbook: turn Udemy practice tests into Gemini Notebook podcasts

You are an AI agent (Claude Code, GitHub Copilot, ...). When the user says "run this app" (or
similar), follow this playbook. The user does not need to know anything technical: you run all
commands yourself and guide them through the few things only a human can do.

What the app does: Udemy practice tests of a course the user is enrolled in -> study files grouped
by topic -> the user uploads them to one Gemini Notebook (notebook.google.com), which turns them
into podcast episodes.

Vocabulary: an **episode** is one Audio Overview (one podcast) in Gemini Notebook, generated from
a group of questions (grouped by topic). All episodes of a course live in **one notebook**; each
episode has its own source folder, and the user selects just that folder's files in Gemini
Notebook when generating it. The number and size of the episodes are decided once, up front.

## How to behave

- Plain language, one step at a time. Say what you are doing and what you need from the user.
  Run commands yourself; never ask the user to type commands.
- Open with one short reminder: this is for personal study of courses they are enrolled in;
  Udemy's terms may limit copying course content, so don't share the generated files.
- Never commit, print in bulk, or upload course content anywhere. `data/` and `output/` are
  git-ignored on purpose. Nothing leaves the computer except what the user uploads to
  Gemini Notebook themselves.
- Commands below use `python3`. On Windows use `py -3` (or `python`) instead.

## Step 0: check Python

Run `python3 --version`. Need 3.9 or newer. If missing, tell the user how to install it
(python.org/downloads, `brew install python`, or `winget install Python.Python.3`) and wait.
Nothing else is needed: no pip install, no Node.

## Step 1: get the tests out of Udemy (the user does a few clicks)

Ask which course. The user must be logged in to Udemy in their normal browser. If they use
Deloitte's Udemy Business, give them this link so they can click it and find their course:
https://deloittedevelopment.udemy.com/home/my-courses/learning/
They open the course there (its address then contains `/course/`), and run the console script on
that course page. Then:

1. Copy the script to their clipboard yourself:
   macOS `pbcopy < browser/extract.js`, Windows `clip < browser\extract.js`
   (or PowerShell `Get-Content browser\extract.js | Set-Clipboard`), Linux
   `xclip -selection clipboard < browser/extract.js`. If copying fails, tell them to open
   `browser/extract.js` and copy its contents.
2. Tell them exactly:
   - Open any page of your course in the browser (for example a practice test), logged in.
     The address must contain `/course/`.
   - Open the developer console: press F12 (Mac: Cmd+Option+J in Chrome), choose the **Console**
     tab. In Safari first enable Settings -> Advanced -> "Show features for web developers",
     then press Cmd+Option+C. Safari may also ask to allow the download from udemy.com: allow it.
   - The console shows lots of red errors from Udemy's own page (blocked analytics, missing
     "source map" files). Ignore them; only the script's own lines ("Fetching ...",
     "Not enrolled ...", "Done: ...") and its pop-up boxes matter.
   - Paste (Ctrl+V / Cmd+V) and press Enter. If the browser says pasting is blocked, type
     `allow pasting`, press Enter, and paste again.
   - The script always fetches **all** practice tests of the course (which tests go into which
     episode is decided later, with you). The download of `udemy-<course>.json` starts by itself
     when it finishes (the console shows "Done: ..."); no pop-up. Ask them to say "done" once
     the file has downloaded.
3. Be open about what the script does: it only sends read requests to udemy.com, the same ones
   the course player sends, and sends nothing anywhere else. They may read it first.
4. If the user is not enrolled in the course, its tests are locked. On a Udemy Business site
   (address is not www.udemy.com) the script then enrolls automatically by clicking the course
   page's own Enroll button (no private API), which adds the course to their learning list (their
   organization may see that), and continues. **Tell the user this and get their OK in chat before
   they run the script.** (Whoever wants a yes/no dialog instead sets `CONFIRM_BEFORE_ENROLL = true`
   at the top of `browser/extract.js`.) On a personal Udemy account the script never enrolls (it
   could mean buying the course); they must enroll themselves.

If you have a browser tool and the user is already logged in there, you may run the script
yourself instead (it needs a `/course/<name>/` page).

## Step 2: import

Find the newest download (`ls -t ~/Downloads/udemy-*.json | head -1`; Windows PowerShell:
`Get-ChildItem $HOME\Downloads\udemy-*.json | Sort LastWriteTime | Select -Last 1`), then run:

`python3 scripts/udemy.py import <that file>`

It prints the tests found with question counts and any warnings (images that can't be read aloud,
unusual question types). Tell the user in a sentence. The folder name used below is `<name>`
(printed as `data/<name>/`).

## Step 3: plan the episodes (the user decides)

Explain in two sentences: one Gemini Notebook holds all the study files, and an episode is one
Audio Overview (podcast) generated from a group of questions. Episodes are sized by question count
only, and the number of episodes is decided now, once.

1. Ask: **"Should I leave out any specific test?"** (for example one they already took as a practice
   run). Tests are otherwise irrelevant from here on.
2. Run `python3 scripts/udemy.py plan <name>` (add `--exclude 2` etc. for left-out tests). It prints
   the total number of questions and three options: long (~90 questions per episode, about an
   hour), default (~45, about 35 minutes, the recommended one) and short (~20, about 15 minutes),
   each with the Audio Overview length to pick. These sizes are guesses. Say it simply, like:
   "I recommend splitting the 538 questions into 12 default episodes, or 6 long ones, or 27 short
   ones. Which do you prefer?" The user may answer with any size or number.
3. Also ask what they are preparing for and the subject area, in their own words, e.g. exam "AWS
   Certified Developer Associate (DVA-C02)", subject "AWS" (these fill the text for the focus box).
4. Run: `python3 scripts/udemy.py prepare <name> --episodes <N> [--exclude 2] --exam "<exam>" --subject "<subject>"`

It writes the question chunks to `output/<name>/notebook/work/`.

## Step 4: group the questions by topic (you do this)

Follow `prompts/tag_topics.md` exactly. It covers all questions in one go and produces
`output/<name>/notebook/work/topics.json`. Then run `python3 scripts/udemy.py check <name>` and fix
problems until it reports no missing or unknown ids.

## Step 4b: describe images in questions (only if `import`/`prepare` mentioned images)

Some questions keep their data in an image (tables, diagrams, screenshots); without it the
podcast hosts can't discuss the question. **Ask the user first**: "N questions contain images. I
can download just those images from Udemy's image server, look at them and describe them in text
so the hosts can use them. The images are viewed by your AI assistant like any file you let it
read. OK?" If they agree: run `python3 scripts/udemy.py images <name>` (downloads into
`output/<name>/notebook/work/images/`), then follow `prompts/describe_images.md` to write
`work/image_descriptions.json`. If they decline, `build` still works: those images read as "not
available" and the user should expect weaker episodes for those questions.

## Step 4c: group the topics into episodes (you propose, the user decides)

Follow `prompts/plan_episodes.md`: split the topics into the chosen number of episodes with
similar question counts, keeping related topics together, give each episode a short title, and show
the user the proposal ("Episode 1: ... (48 questions) ..."). When they agree (or after they adjust
it), save it as `output/<name>/notebook/work/episodes.json` and run `python3 scripts/udemy.py check
<name>`. Without that file, `build` groups the topics automatically by name, which also works.

## Step 5: build the files

`python3 scripts/udemy.py build <name>`

It creates one folder per episode: `output/<name>/notebook/sources/E1_<title>/`, `E2_...`, each
with topic files named `E1_01_...md`. Skim one file to be sure it reads well (question, options,
correct answer, explanation, no stray URLs). Tell the user how many episodes and files there are
and show them the topic names per episode. Offer to rename/merge topics if they want (edit
`topics.json` or `episodes.json`, run `build` again).

## Step 6: guide the user through Gemini Notebook

Open `output/<name>/notebook/HOW_TO_USE.md`, read it with them and walk them through it step by
step (notebook.google.com -> new notebook -> add all files from `sources/` -> per episode select
only that episode's files (`E1_`, `E2_`, ...) -> Audio Overview -> customize -> Deep Dive, the
length from the table -> paste the focus text -> Generate). The focus text there is already filled in with their exam and subject. Offer to
show them the folder (`open` on macOS, `explorer` on Windows, `xdg-open` on Linux).

Suggest generating one episode first as a pilot, listening to it, and coming back with feedback:
if hosts skip questions, or it is too shallow or too long, adjust the focus text, the length, or
the topics (edit `topics.json` or `episodes.json` + `build`). The number of episodes is fixed at
Step 3; changing it later means running `prepare` again with a new `--episodes` (it keeps
`topics.json` and the image descriptions), redoing Step 4c, and re-uploading the changed files.

## Troubleshooting

| Problem | Do this |
|---|---|
| Script says not allowed / HTTP 401, 403 | User is not logged in. Log in, reload the course page, run again. (If they are logged in but not enrolled, on Udemy Business the script offers to enroll; on a personal account they must enroll themselves.) |
| "Could not find an Enroll button" | Open the course's main page (address ends in `/course/<name>/`) and run again, or enroll by hand. If the organization needs an admin to assign the course, they must ask the admin. |
| Page reloaded after enrolling | The script clicks Enroll in a hidden frame so the page normally does not reload. If the frame is blocked it falls back to clicking on the page, which reloads and stops the script: run it again, they are enrolled now. |
| "Open a page of your Udemy course" | The address must contain `/course/<name>/`; use a lesson or practice-test page, not the Udemy home page. |
| No file downloaded | Browser may block downloads; allow them for udemy.com and run the script again. |
| "No practice tests found" | The course may not have typed practice tests; the script falls back to all quizzes. If still none, the course has no tests this tool can read. |
| `import` says not a file from extract.js | Wrong file; use the newest `udemy-*.json`. |
| Udemy changed its API (unexpected errors) | Tell the user plainly; inspect with the browser network tab what the course player requests for a practice test and adapt `browser/extract.js`. |

## For maintainers

- `browser/extract.js` runs in the user's browser, `scripts/udemy.py` is standard-library Python
  only (keep it that way, no dependencies), `prompts/tag_topics.md` is the agent's AI task.
- Data formats: `data/<name>/tests/testN.json` (normalized questions), `output/<name>/notebook/`
  (`notebook.json` with the number of episodes and left-out tests, `work/` with `topics.json` and
  `episodes.json`, `sources/E<n>_<title>/`, `HOW_TO_USE.md`).
  `--notebook NAME` on the commands keeps several plans for the same course side by side.
