# Playbook: turn Udemy practice tests into Gemini Notebook podcasts

You are an AI agent (Claude Code, GitHub Copilot, ...). When the user says "run this app" (or
similar), follow this playbook **exactly, step by step**. It is a script, not a suggestion. The user
is not technical: you run every command yourself and guide them by the hand through the few things
only a human can do. Read the whole file before you start.

What the app does: the practice tests of a Udemy course the user is enrolled in -> study files grouped
by topic -> the user uploads them to one Gemini Notebook (notebook.google.com), which turns them into
podcast episodes. An **episode** is one Audio Overview (one podcast) in Gemini Notebook, generated from
a group of questions. All episodes live in **one notebook**. All source files are uploaded together
(Gemini Notebook can't upload folders); the file-name prefix `E1_`, `E2_`, ... says which episode a
file belongs to, and the user selects one episode's files when generating it.

## Rules (they matter more than anything below)

1. **Do the steps in order. Never skip, merge or reorder them.** Start each reply to the user with the
   step header given below ("Step 1 of 6: ...").
2. **Say and ask exactly the texts in the blockquotes** marked SAY and ASK. Only fill in the
   `<placeholders>`. Don't paraphrase, shorten, add jargon or add extra remarks. Each SAY/ASK text
   already explains why the user is being asked.
3. **Ask only the questions marked ASK, one at a time, each exactly once.** Do not ask anything else.
   In particular never ask for the course name or link, the Udemy account type, or permission to run
   commands: the script finds the course and account type itself, and commands are yours to run.
4. Ask in normal chat text (no pop-up forms or multiple-choice tools), and wait for the answer
   before doing the next thing.
5. Run all commands yourself without asking. Never show the user commands, file paths or JSON; speak
   plain language ("I'm sorting your questions by topic").
6. If the user says something unexpected or asks a question, answer briefly in plain language, then
   repeat the pending ASK.
7. Never commit, upload or print in bulk any course content. `data/` and `output/` are git-ignored on
   purpose. Nothing leaves the computer except what the user uploads to Gemini Notebook themselves.
8. Commands use `python3`. On Windows use `py -3` (or `python`).

## Step 0: check Python (silent)

Run `python3 --version`. Need 3.9 or newer; nothing else must be installed (no pip, no Node). If it is
missing or too old, SAY:

> I need Python 3 (a free programming tool) on this computer, and it isn't installed yet. Please
> install it from https://www.python.org/downloads/ (Mac with Homebrew: `brew install python`;
> Windows: `winget install Python.Python.3`), then tell me when it's done.

and wait. Otherwise continue straight to Step 1 and put this opening in the same message, before the
Step 1 text:

> Hi! I'll turn the practice tests of one of your Udemy courses into podcast episodes you can
> generate in Gemini Notebook. There are 6 short steps and it takes about 10-15 minutes. I do the
> technical parts; you only click a few things. One reminder: this is for your own study of a course
> you're enrolled in. Udemy's terms may limit copying course content, so please don't share the
> generated files.

## Step 1 of 6: get the practice tests out of Udemy

DO, before writing anything (the user must not see any of this):

1. Copy `browser/extract.js` to the clipboard (macOS `pbcopy < browser/extract.js`, Windows
   `clip < browser\extract.js`, Linux `xclip -selection clipboard < browser/extract.js`). If that
   fails, tell the user to open the file and copy its contents.
2. Find out the operating system and the default web browser (macOS: `defaults read
   com.apple.LaunchServices/com.apple.launchservices.secure LSHandlers`, look for the `https` handler,
   none means Safari; Windows PowerShell: `(Get-ItemProperty
   HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice).ProgId`;
   Linux: `xdg-settings get default-web-browser`).
3. Fill the three placeholders of the message below from this table:

| Browser | `<console>` | `<paste>` |
|---|---|---|
| Chrome, Edge, Brave, Arc, Opera | Mac: `Cmd+Option+J`, otherwise `Ctrl+Shift+J` | `Cmd+V` or `Ctrl+V` per OS, plus: "If it says pasting is blocked, type `allow pasting`, press Enter and paste again." |
| Firefox | Mac: `Cmd+Option+K`, otherwise `Ctrl+Shift+K` | same as above |
| Safari | first turn on Safari > Settings > Advanced > "Show features for web developers", then press `Cmd+Option+C` (Safari may ask to allow the download later: allow it) | `Cmd+V` |
| unknown | `F12`, then the Console tab | `Ctrl+V` |

SAY and ASK (one message, exactly this short; fill in `<browser>`):

> **Step 1 of 6: get the practice tests out of Udemy**
>
> I copied a small script to your clipboard. It reads your course's practice tests from udemy.com and
> saves them as one file in your Downloads folder; it sends nothing anywhere else.
>
> 1. Open your Udemy course in <browser> (logged in; any page whose address contains `/course/`).
>    Deloitte Udemy Business: https://deloittedevelopment.udemy.com/home/my-courses/learning/
> 2. Open the console: <console>
> 3. Paste (<paste>) and press Enter. Ignore red error lines from Udemy's own page.
> 4. Wait for "Done: ..." in the console. The file appears in Downloads.
>
> Heads-up: if you use Udemy Business and aren't enrolled in this course yet, the script enrolls you
> through the course's own Enroll button (your organization may see it).
>
> **Reply "done" when the file has downloaded, or "stop" if you don't want that.**

If they reply "stop": SAY "No problem. Enroll in the course yourself in your browser, then tell me
'done' and we'll continue with step 1." and go back to the ASK above when they are ready.

## Step 2 of 6: read the file (no question)

DO: find the newest download (`ls -t ~/Downloads/udemy-*.json | head -1`; Windows PowerShell:
`Get-ChildItem $HOME\Downloads\udemy-*.json | Sort LastWriteTime | Select -Last 1`). If there is none,
SAY "I can't find the downloaded file yet. Did the console show 'Done:'? If your browser blocked the
download, allow it for udemy.com and run the script again. Tell me when it's downloaded." and wait.
Then run `python3 scripts/udemy.py import <that file>`. It prints `data/<name>/` (that `<name>` is used
in every later command), the tests with question counts and any warnings. SAY:

> **Step 2 of 6: got it.** I found <number of tests> practice tests with <total questions> questions
> in "<course title>": <list like "test 1 (65 questions), test 2 (65 questions)">.

If there were image warnings add: "<K> of the questions contain images; I'll take care of those in step 4."

## Step 3 of 6: choose your episodes (three questions, one at a time)

SAY and ASK (question A):

> **Step 3 of 6: choose your episodes**
>
> A podcast episode is one Audio Overview in Gemini Notebook. I'll split all questions into episodes of
> similar size; which test a question came from doesn't matter, except for one thing: if you already
> took a test as a practice run, we can leave it out.
>
> **Do you want to leave out any specific test? Reply "none" or the test numbers (like "2").**

DO: `python3 scripts/udemy.py plan <name>` (add `--exclude 2 ...` for left-out tests). Its output has
one line per option: the number of episodes, the size name (long, default or short; two names on one
line mean the options coincide), questions per episode and minutes per episode. Then SAY and ASK
(question B), one bullet per line of the output. The number of episodes and the length of an episode
always go together: the user picks one option and gets both. Mark the line marked `<-- recommended`:

> You have <total> questions. Here are the ways to split them into podcast episodes:
>
> - **<N> long episodes**: about <per> questions each, roughly <minutes> minutes per episode
> - **<N> default episodes**: about <per> questions each, roughly <minutes> minutes per episode (my recommendation)
> - **<N> short episodes**: about <per> questions each, roughly <minutes> minutes per episode
>
> The lengths are my estimates; we can calibrate after the first episode.
>
> **Which do you prefer? Reply "long", "default" or "short", or a number of episodes if you want
> something else.**

Map the answer to the number of episodes `<N>` and **remember the size name they picked** (long,
default or short). The size name also decides the Audio Overview length used in Step 6 (long = Longer,
default = Default, short = Shorter), so it must reach `prepare`. If they give their own number
instead, tell them in one short sentence the resulting size ("that's about <per> questions, roughly
<minutes> minutes per episode") and continue; `prepare` then picks the nearest size name itself.

Then SAY and ASK (question C). For `<exam>` use the course title unless it is obviously long or
unclear, then a short natural name; `<subject>` is the technology or field (e.g. "AWS", "Databricks"):

> The podcast hosts need to know what you're preparing for, so they pitch it right. I'll use "<exam>"
> as the exam and "<subject>" as the subject area.
>
> **Reply "ok", or tell me the exam name and the subject area you'd like.**

DO: `python3 scripts/udemy.py prepare <name> --episodes <N> [--size <long|default|short>] [--exclude ...] --exam "<exam>" --subject "<subject>"`
(pass `--size` whenever the user picked a size name). Remember the "Audio Overview length" it prints,
and whether it reported images in questions.

## Step 4 of 6: sort the questions by topic

SAY (no question):

> **Step 4 of 6: sorting the questions by topic.** I'm grouping your <total> questions into topics now,
> so each podcast episode teaches coherent subjects. This takes a few minutes; nothing is needed from you.

DO (you do this yourself): follow `prompts/tag_topics.md` exactly. It produces
`output/<name>/notebook/work/topics.json`. Run `python3 scripts/udemy.py check <name>` and fix problems
until it reports no missing or unknown ids.

If `prepare` reported images in questions, ASK (this is the only reason to ask here: it downloads files
from Udemy's image server and shows them to you, the AI):

> <K> of the questions contain images, such as tables or diagrams, that the podcast hosts can't see. I
> can download just those <M> images from Udemy and describe them in text so the hosts can use them. I
> will look at the images myself (as your AI assistant).
>
> **Reply "yes" to do that, or "no" to skip it.**

On "yes": run `python3 scripts/udemy.py images <name>` (it downloads into `work/images/`), then follow
`prompts/describe_images.md` to write `work/image_descriptions.json`. On "no": continue; those images
will read as "not available" in the files.

## Step 5 of 6: group the topics into episodes and build the files

DO: follow `prompts/plan_episodes.md` to draft the split of the topics into the chosen number of
episodes. Then SAY and ASK (one episode per line; fill in title, number of questions and a few topic
names in plain language):

> **Step 5 of 6: your episodes.** Here is how I'd divide the topics:
>
> - **Episode 1: <title>** (<n> questions): <3-5 topics in plain language>
> - **Episode 2: <title>** (<n> questions): <...>
> - ...
>
> **Reply "ok" to use this split, or tell me what to change** (for example "move X to episode 2").

Apply their changes, save `output/<name>/notebook/work/episodes.json`, run
`python3 scripts/udemy.py check <name>` (fix every PROBLEM) and then `python3 scripts/udemy.py build <name>`.
Skim one generated file to be sure it reads well (question, options, correct answer, explanation,
no stray URLs). Then continue straight to Step 6.

## Step 6 of 6: make the podcasts in Gemini Notebook (guided, one episode at a time)

DO: open the folder `output/<name>/notebook/sources/` for the user (macOS `open`, Windows `explorer`,
Linux `xdg-open`) and copy the **long** focus text from `output/<name>/notebook/HOW_TO_USE.md` (section
"Text for the focus box") to the clipboard.

SAY and ASK:

> **Step 6 of 6: make your podcasts in Gemini Notebook.** Your files are ready; I opened the folder
> that holds them. One Gemini Notebook holds all episodes: you upload all files once, then we generate
> the episodes one by one.
>
> 1. Go to https://notebook.google.com and sign in with a Google account.
> 2. Create a new notebook.
> 3. Add sources: upload all <total files> files from the folder I opened. Every file name starts with
>    `E1_`, `E2_`, ... so we can pick each episode's files later.
>
> **Reply "uploaded" when all files are in the notebook.**

Then, for each episode in turn, SAY and ASK (the focus text is already on the clipboard; if the user
copied something else meanwhile, copy it again first). `<length>` is the "Audio Overview length" that
`prepare` printed (also in the table of `HOW_TO_USE.md`): Longer, Default or Shorter. It is the same for
every episode and follows the size the user picked in Step 3. Never choose it yourself:

> **Episode <n> of <N>: <title>** (<number of questions> questions)
>
> 1. In the notebook's source list, select **only** the files whose names start with `E<n>_` and
>    untick all the others.
> 2. Click **Audio Overview**.
> 3. Set the format to **Deep Dive** and the length to **<length>**.
> 4. Paste the text I copied to your clipboard into the box "What should the AI hosts focus on in this
>    episode?" (If the box says it's too long, tell me and I'll give you a shorter version.)
> 5. Click Generate. It takes a few minutes, and Google may limit how many you can generate per day.
>
> **Reply "next" when episode <n> is generating.**

When all episodes are done, SAY:

> **All done!** Listen to episode 1 first, then tell me how it went. If the hosts skip questions or it's
> too long, I can regroup everything into more, smaller episodes. Your files stay in this project's
> `output` folder.

## Troubleshooting

| Problem | Do this |
|---|---|
| Script says not allowed / HTTP 401, 403 | User is not logged in. Log in, reload the course page, run again. (If they are logged in but not enrolled, on Udemy Business the script enrolls by itself; on a personal account they must enroll themselves.) |
| "Could not find an Enroll button" | Open the course's main page (address ends in `/course/<name>/`) and run again, or enroll by hand. If the organization needs an admin to assign the course, they must ask the admin. |
| Page reloaded after enrolling | The script clicks Enroll in a hidden frame so the page normally does not reload. If the frame is blocked it falls back to clicking on the page, which reloads and stops the script: run it again, they are enrolled now. |
| "Open a page of your Udemy course" | The address must contain `/course/<name>/`; use a lesson or practice-test page, not the Udemy home page. |
| No file downloaded | Browser may block downloads; allow them for udemy.com and run the script again. |
| "No practice tests found" | The course may not have typed practice tests; the script falls back to all quizzes. If still none, the course has no tests this tool can read. |
| `import` says not a file from extract.js | Wrong file; use the newest `udemy-*.json`. |
| Udemy changed its API (unexpected errors) | Tell the user plainly; inspect with the browser network tab what the course player requests for a practice test and adapt `browser/extract.js`. |
| User wants a different number of episodes later | Run `prepare` again with the new `--episodes` (it keeps `topics.json` and image descriptions), redo Step 5, and have them re-upload the changed files. |

## For maintainers

- `browser/extract.js` runs in the user's browser, `scripts/udemy.py` is standard-library Python only
  (keep it that way, no dependencies), `prompts/` holds the agent's AI tasks (`tag_topics.md`,
  `describe_images.md`, `plan_episodes.md`).
- Data formats: `data/<name>/tests/testN.json` (normalized questions), `output/<name>/notebook/`
  (`notebook.json` with the number of episodes, size and left-out tests, `work/` with `topics.json` and
  `episodes.json`, `sources/E<n>_<nn>_<topic>.md` all in ONE flat folder because Gemini Notebook can't
  upload folders, `HOW_TO_USE.md`). `--notebook NAME` on the commands keeps several plans for the same
  course side by side.
- Tuning knobs: episode sizes, minutes per question, the recommended size and the size name -> Audio
  Overview length mapping live at the top of `scripts/udemy.py` (`SIZES`, `RECOMMENDED`,
  `MIN_PER_QUESTION`, `SETTING`).
- This playbook is deliberately a strict script because weaker agents improvise. When you change a
  step, keep the SAY/ASK texts self-explanatory and keep the "ask only what is listed" rule.
