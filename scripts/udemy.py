#!/usr/bin/env python3
"""Udemy practice tests -> Gemini Notebook source files. Normally run by an AI agent, see AGENTS.md.

  python3 scripts/udemy.py import  <udemy-xxx.json> [--name NAME]   # file downloaded by browser/extract.js
  python3 scripts/udemy.py plan    <name> [--exclude 2 3]          # total questions + episode size options
  python3 scripts/udemy.py prepare <name> --episodes N [--exclude 2 3] [--exam T] [--subject T]
  python3 scripts/udemy.py images  <name>                           # downloads question images to describe
  python3 scripts/udemy.py check   <name>                           # validates topics.json + episode grouping
  python3 scripts/udemy.py build   <name>                           # writes sources/ + HOW_TO_USE.md

One Gemini Notebook = one "notebook" folder with N podcast EPISODES. The number of episodes is
decided up front from the total number of questions (tests only matter for leaving some out). The
questions are grouped into topics (AI step), the topics are grouped into the N episodes (work/episodes.json,
or automatically), and each episode's source files live in their own folder: in Gemini Notebook you
select exactly those files to generate that episode's Audio Overview. All commands after `prepare`
take an optional `--notebook NAME` (default: notebook) if you keep several plans for one course.

Folders (both git-ignored, they hold copyrighted course content):
  data/<name>/                    imported tests (tests/testN.json) and the original download
  output/<name>/<notebook>/       notebook.json, work/, sources/E1_<title>/*.md, ..., HOW_TO_USE.md
"""
import argparse
import json
import math
import re
import shutil
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"
CHUNK = 100  # questions per tagging chunk
MAX_TOPIC = 16  # topics larger than this are split into parts in build
# Guesses (calibrate with the first episode): questions per episode and what that is worth in minutes.
SIZES = {"long": 90, "default": 45, "short": 20}
RECOMMENDED = "default"
MIN_PER_QUESTION = 0.75


# ---------------------------------------------------------------- html -> text
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}

    def __init__(self, images):
        super().__init__(convert_charrefs=True)
        self.parts, self.images, self.pre = [], images, 0

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.pre += 1
            self.parts.append("\n```\n")
        elif tag in self.BLOCK:
            if not (self.parts and self.parts[-1] == "\n- "):  # <li><p>..: keep the bullet with its text
                self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag == "code" and not self.pre:
            self.parts.append("`")
        elif tag == "img" and self.images is not None:
            src = dict(attrs).get("src")
            if src:  # numbered placeholder; the link is kept so an agent can describe the image
                self.images.append(src)
                self.parts.append(f" [image {len(self.images)}] ")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.pre = max(0, self.pre - 1)
            self.parts.append("\n```\n")
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag == "code" and not self.pre:
            self.parts.append("`")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data if self.pre else re.sub(r"[ \t\r\f\v]+", " ", data))


def html_to_text(h, images=None):
    """HTML -> text. Pass a list as `images` to collect image links (placeholders [image N]);
    without it images are dropped silently (used for explanation diagrams)."""
    p = _Text(images)
    p.feed(h or "")
    s = "".join(p.parts).replace("\xa0", " ")
    s = re.sub(r"\*\*[ \t]*\*\*", "", s)  # empty bold; must not swallow newlines
    s = re.sub(r"[ \t]+\n", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def plain(s):
    return s.replace("**", "").replace("`", "").strip()


# ---------------------------------------------------------------- import
def normalize_quiz(quiz):
    letters = "abcdefghijklmnopqrstuvwxyz"
    questions, issues = [], []
    for i, a in enumerate(quiz["assessments"], 1):
        pr = a.get("prompt") or {}
        raw_answers = pr.get("answers")
        answers = raw_answers if isinstance(raw_answers, list) else []
        raw_corr = a.get("correct_response")
        corr = [c for c in raw_corr if isinstance(c, str)] if isinstance(raw_corr, list) else []
        imgs = []  # images in the question and its options, numbered in reading order
        question = html_to_text(pr.get("question"), imgs)
        opts = [html_to_text(x, imgs) for x in answers]
        q = {
            "number": i,
            "id": a.get("id"),
            "type": a.get("assessment_type"),
            "domain": a.get("section"),
            "question": question,
            "images": imgs,
            "options": [{"letter": letters[k], "text": t, "correct": letters[k] in corr} for k, t in enumerate(opts)],
            "correct_letters": corr,
            "explanation": html_to_text(pr.get("explanation")),
        }
        questions.append(q)
        if q["type"] not in ("multiple-choice", "multi-select"):
            issues.append(f"question {i}: unsupported type '{q['type']}' (may read badly)")
        if not corr or any(c not in letters[: len(opts)] for c in corr):
            issues.append(f"question {i}: no usable correct answer")
        if imgs:
            issues.append(f"question {i}: has {len(imgs)} image(s); describe them before building (see AGENTS.md)")
    return questions, issues


def cmd_import(args):
    bundle = json.load(open(args.file))
    if not str(bundle.get("format", "")).startswith("udemy-practice-tests/"):
        sys.exit("This is not a file made by browser/extract.js.")
    name = args.name or bundle["course"]["slug"]
    tests_dir = DATA / name / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    if Path(args.file).resolve() != (DATA / name / "bundle.json").resolve():
        shutil.copyfile(args.file, DATA / name / "bundle.json")
    print(f"Course: {bundle['course']['title']}  -> data/{name}/")
    summary, all_issues = [], []
    for quiz in bundle["quizzes"]:
        qs, issues = normalize_quiz(quiz)
        n = quiz["number"]
        json.dump({"test": n, "title": quiz["title"], "quiz_id": quiz["id"], "count": len(qs), "questions": qs},
                  open(tests_dir / f"test{n}.json", "w"), indent=1, ensure_ascii=False)
        multi = sum(1 for q in qs if q["type"] == "multi-select")
        print(f"  test {n}: {quiz['title']} - {len(qs)} questions ({multi} select-several)")
        summary.append({"number": n, "title": quiz["title"], "quiz_id": quiz["id"], "count": len(qs)})
        all_issues += [f"test {n} {x}" for x in issues]
    json.dump({"name": name, "slug": bundle["course"]["slug"], "title": bundle["course"]["title"],
               "origin": bundle.get("origin"), "extracted_at": bundle.get("extracted_at"), "tests": summary},
              open(DATA / name / "course.json", "w"), indent=1, ensure_ascii=False)
    if all_issues:
        print("\nWarnings:")
        print("\n".join("  " + x for x in all_issues[:30]))
        if len(all_issues) > 30:
            print(f"  ... and {len(all_issues) - 30} more")
    print(f"\nNext: python3 scripts/udemy.py plan {name}")


# ---------------------------------------------------------------- plan: tests -> episodes
def available_tests(name):
    """{test number: (title, question count)} from the imported data."""
    tests = {}
    for p in sorted((DATA / name / "tests").glob("test*.json")):
        d = json.load(open(p))
        tests[d["test"]] = (d.get("title") or f"Test {d['test']}", len(d["questions"]))
    if not tests:
        sys.exit(f"No imported tests in data/{name}/tests. Run 'import' first.")
    return tests


def length_setting(n_questions):
    """Which Audio Overview length setting to pick in Gemini Notebook for an episode of this size."""
    return "Shorter" if n_questions < 15 else "Default" if n_questions < 35 else "Longer"


def approx_minutes(n_questions):
    return max(5, round(n_questions * MIN_PER_QUESTION / 5) * 5)


def cmd_plan(args):
    tests = available_tests(args.name)
    excluded = sorted(set(args.exclude or []))
    for t in excluded:
        if t not in tests:
            sys.exit(f"test {t} does not exist (available: {sorted(tests)})")
    print("Tests found:")
    for n, (title, c) in tests.items():
        print(f"  test {n}: {title} - {c} questions" + ("   <-- left out" if n in excluded else ""))
    total = sum(c for n, (_, c) in tests.items() if n not in excluded)
    print(f"\n{total} questions to turn into episodes. Episodes are sized by question count only; tests only "
          "matter for leaving one out (e.g. one the user already took as a practice run: --exclude N).")
    print("Options (sizes are guesses, calibrate after the first episode):")
    for key in ("long", "default", "short"):
        n = max(1, round(total / SIZES[key]))
        per = round(total / n)
        print(f"  {n} {key} episode(s) of about {per} questions, roughly {approx_minutes(per)} min each, "
              f"Audio Overview length {length_setting(per)}" + ("   <-- recommended" if key == RECOMMENDED else ""))
    print("Ask the user: which tests (if any) to leave out, and how many episodes they want. Then run:")
    ex = " --exclude " + " ".join(map(str, excluded)) if excluded else ""
    print(f"  python3 scripts/udemy.py prepare {args.name} --episodes <N>{ex} --exam \"<exam>\" --subject \"<subject>\"")


# ---------------------------------------------------------------- notebook config
def notebook_dir(name, notebook):
    d = OUT / name / notebook
    if not (d / "notebook.json").exists():
        sys.exit(f"{d / 'notebook.json'} not found. Run 'prepare' first.")
    return d


def load_notebook(name, notebook):
    cfg = json.load(open(notebook_dir(name, notebook) / "notebook.json"))
    cfg["dir"], cfg["name"] = notebook_dir(name, notebook), name
    cfg.setdefault("subject", cfg["exam"])
    return cfg


def load_questions(cfg):
    qs = []
    for t in cfg["tests"]:
        path = DATA / cfg["name"] / "tests" / f"test{t}.json"
        if not path.exists():
            sys.exit(f"missing {path}; run 'import' first (and check the test numbers)")
        for q in json.load(open(path))["questions"]:
            q["qid"] = f"{t}-{q['number']}"
            qs.append(q)
    return qs


def correct_opts(q):
    return [o for o in q["options"] if o["correct"]]


def load_descriptions(cfg):
    path = cfg["dir"] / "work" / "image_descriptions.json"
    return json.load(open(path)) if path.exists() else {}


def undescribed(cfg, qs):
    """(question id, image number) for every question image without a description yet."""
    desc = load_descriptions(cfg)
    return [(q["qid"], str(n)) for q in qs for n in range(1, len(q.get("images") or []) + 1)
            if not (desc.get(q["qid"]) or {}).get(str(n))]


# ---------------------------------------------------------------- prepare
def cmd_prepare(args):
    tests = available_tests(args.name)
    excluded = sorted(set(args.exclude or []))
    for t in excluded:
        if t not in tests:
            sys.exit(f"test {t} does not exist (available: {sorted(tests)})")
    included = [t for t in sorted(tests) if t not in excluded]
    if not included:
        sys.exit("All tests are excluded; nothing to do.")
    if args.episodes < 1:
        sys.exit("--episodes must be at least 1 (run 'plan' for options)")
    course_file = DATA / args.name / "course.json"
    title = json.load(open(course_file))["title"] if course_file.exists() else args.name
    cfg = {"exam": args.exam or title, "subject": args.subject or args.exam or title,
           "tests": included, "excluded": excluded, "episodes": args.episodes}
    d = OUT / args.name / args.notebook
    (d / "work").mkdir(parents=True, exist_ok=True)
    json.dump(cfg, open(d / "notebook.json", "w"), indent=1, ensure_ascii=False)
    cfg["dir"], cfg["name"] = d, args.name
    qs = load_questions(cfg)
    for old in (d / "work").glob("questions_*.txt"):
        old.unlink()
    chunks = [qs[i:i + CHUNK] for i in range(0, len(qs), CHUNK)]
    for n, chunk in enumerate(chunks, 1):
        lines = [f"# Exam: {cfg['exam']} | Subject: {cfg['subject']} | chunk {n} of {len(chunks)}"]
        for q in chunk:
            text = re.sub(r"\s+", " ", plain(q["question"]))
            if len(text) > 300:  # the actual ask is at the end of the scenario
                text = "…" + text[-300:]
            ans = "; ".join(re.sub(r"\s+", " ", plain(o["text"]))[:120] for o in correct_opts(q))
            lines.append(f"{q['qid']} [{q.get('domain') or '-'}] Q: {text} A: {ans}")
        (d / "work" / f"questions_{n}.txt").write_text("\n".join(lines) + "\n")
    per = round(len(qs) / args.episodes)
    print(f"Notebook plan '{args.notebook}': {len(qs)} questions"
          + (f" (tests {', '.join(map(str, excluded))} left out)" if excluded else "")
          + f" -> {args.episodes} episode(s) of about {per} questions, roughly {approx_minutes(per)} min each, "
          f"Audio Overview length {length_setting(per)}. Question chunks ({len(chunks)}) -> {d / 'work'}")
    n_img = sum(1 for q in qs if q.get("images"))
    if n_img:
        print(f"{n_img} question(s) contain images: after tagging, run 'images {args.name}' "
              "and describe them (see AGENTS.md).")
    nb = "" if args.notebook == "notebook" else f" --notebook {args.notebook}"
    print(f"Next: tag the questions as described in prompts/tag_topics.md and save {d / 'work' / 'topics.json'}, "
          f"then run: check {args.name}{nb}")


# ---------------------------------------------------------------- images
def cmd_images(args):
    cfg = load_notebook(args.name, args.notebook)
    qs = [q for q in load_questions(cfg) if q.get("images")]
    if not qs:
        print("No question in this notebook contains an image. Nothing to do.")
        return
    desc = load_descriptions(cfg)
    folder = cfg["dir"] / "work" / "images"
    folder.mkdir(exist_ok=True)
    todo = failed = 0
    for q in qs:
        for n, url in enumerate(q["images"], 1):
            ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".png"
            path = folder / f"{q['qid']}_{n}{ext}"
            if not path.exists():
                try:
                    if not url.startswith("https://"):
                        raise ValueError("not an https link")
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    data = urllib.request.urlopen(req, timeout=30).read(10_000_001)
                    if len(data) > 10_000_000:
                        raise ValueError("image larger than 10 MB")
                    path.write_bytes(data)
                except Exception as e:
                    print(f"{q['qid']} image {n}: FAILED to download ({e})")
                    failed += 1
                    continue
            done = bool((desc.get(q["qid"]) or {}).get(str(n)))
            todo += not done
            print(f"{q['qid']} image {n}: {path.relative_to(ROOT)}  " + ("(described)" if done else "NEEDS DESCRIPTION"))
    print(f"\n{sum(len(q['images']) for q in qs)} images in {len(qs)} questions, {todo} still need a description"
          + (f", {failed} failed to download" if failed else "") + ".")
    print(f"Describe them as in prompts/describe_images.md and save {cfg['dir'] / 'work' / 'image_descriptions.json'}")


# ---------------------------------------------------------------- check
def read_topics(cfg, qs):
    path = cfg["dir"] / "work" / "topics.json"
    if not path.exists():
        sys.exit(f"{path} not found; tag the questions first (see prompts/tag_topics.md)")
    topics = json.load(open(path))
    ids = {q["qid"] for q in qs}
    return topics, sorted(ids - set(topics)), sorted(set(topics) - ids)


def episode_plan(cfg, topics):
    """Assign the topics to the notebook's N episodes: work/episodes.json if present (written by the
    agent together with the user), else automatically. Returns (plan, problems, where it came from);
    plan = {episode number: {"title": str, "topics": [topic names]}}."""
    n_ep = cfg["episodes"]
    sizes = defaultdict(int)
    for t in topics.values():
        sizes[t] += 1
    path = cfg["dir"] / "work" / "episodes.json"
    if path.exists():
        plan, problems, seen = {}, [], defaultdict(int)
        for k, v in json.load(open(path)).items():
            ts = v.get("topics", []) if isinstance(v, dict) else v
            title = (v.get("title") if isinstance(v, dict) else None) or f"Part {k}"
            plan[int(k)] = {"title": title, "topics": ts}
            for t in ts:
                seen[t] += 1
        if sorted(plan) != list(range(1, n_ep + 1)):
            problems.append(f"episodes.json must define exactly the episodes 1..{n_ep}, found {sorted(plan)}")
        problems += [f"topic not in any episode: {t}" for t in sizes if t not in seen]
        problems += [f"topic in episodes.json but not in topics.json: {t}" for t in seen if t not in sizes]
        problems += [f"topic in several episodes: {t}" for t, c in seen.items() if c > 1]
        return plan, problems, "work/episodes.json"
    per, cum = sum(sizes.values()) / n_ep, 0
    plan = {i: {"title": f"Part {i}", "topics": []} for i in range(1, n_ep + 1)}
    for t in sorted(sizes):  # topic names start with their area, so sorting keeps related topics together
        plan[min(n_ep - 1, int((cum + sizes[t] / 2) / per)) + 1]["topics"].append(t)
        cum += sizes[t]
    return plan, [], "automatic, alphabetical by topic name"


def cmd_check(args):
    cfg = load_notebook(args.name, args.notebook)
    qs = load_questions(cfg)
    topics, missing, extra = read_topics(cfg, qs)
    groups = defaultdict(list)
    for qid, t in topics.items():
        groups[t].append(qid)
    for t in sorted(groups):
        n = len(groups[t])
        print(f"{n:3d}  {t}" + ("  <-- small" if n < 4 else "  <-- large (will be split)" if n > MAX_TOPIC else ""))
    print(f"\n{len(groups)} topics, {len(topics)} tagged, {len(qs)} questions")
    if missing:
        print("MISSING (not tagged):", missing)
    if extra:
        print("UNKNOWN ids (not in this notebook):", extra)
    pending = undescribed(cfg, qs)
    if pending:
        print(f"NOTE: {len(pending)} question image(s) have no description yet "
              f"(run 'images {args.name}'); build will leave a placeholder.")
    plan, problems, source = episode_plan(cfg, {q: t for q, t in topics.items() if q not in extra})
    print(f"\nEpisode grouping ({source}), {cfg['episodes']} episode(s):")
    sizes = {i: sum(len(groups[t]) for t in p["topics"] if t in groups) for i, p in plan.items()}
    for i in sorted(plan):
        print(f"  episode {i}: {plan[i]['title']} - {sizes[i]} questions, {len(plan[i]['topics'])} topics, "
              f"Audio Overview length {length_setting(sizes[i])}")
    avg = sum(sizes.values()) / max(1, len(sizes))
    if any(s < 0.7 * avg or s > 1.3 * avg for s in sizes.values()):
        print("NOTE: episode sizes differ by more than 30%; consider moving a topic to balance them.")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if missing or extra or problems else 0


# ---------------------------------------------------------------- build
def clean_explanation(t):
    # a caption line ("How X works:") directly followed by a removed diagram's "via - url"
    t = re.sub(r"(?m)^[^\n]*:[ \t]*\n\s*\n[ \t]*via\s*-\s*https?://\S+[ \t]*$", "", t)
    t = re.sub(r"(?im)^[ \t]*via\s*-\s*https?://\S+[ \t]*$", "", t)
    t = re.sub(r"(?im)^[ \t]*For more information visit.*$", "", t)
    t = re.split(r"(?im)^[ \t]*\**references?:?\**[ \t]*$", t)[0]  # drop reference list
    t = re.sub(r"(?im)^[ \t]*\**references?\**[ \t]*:.*$", "", t)  # "Reference: <link>" on one line
    t = re.sub(r"https?://\S+", "", t)  # URLs are useless when spoken
    return re.sub(r"\n{3,}", "\n\n", plain(t)).strip()


def fill_images(text, q, desc, missing):
    """Replace [image N] placeholders by the agent-written description (or a note if there is none)."""
    def rep(m):
        d = ((desc.get(q["qid"]) or {}).get(m.group(1)) or "").strip()
        if d:
            return "[Image description: " + d + "]"
        missing.append((q["qid"], m.group(1)))
        return "[an image that is not available in this text]"
    return re.sub(r"\[image (\d+)\]", rep, text)


def source_text(cfg, ep, title, items, desc, missing):
    out = [f"# {title}", "",
           f"Study material for the {cfg['exam']} exam (episode {ep['number']}: {ep['title']}). Topic: {title}. This document "
           f"contains {len(items)} practice questions on this topic. For each question you get the question, "
           "the answer options, the correct answer, and an explanation of why the correct answer is right and "
           "why the other options are wrong.", ""]
    for i, q in enumerate(items, 1):
        multi = len(correct_opts(q)) > 1
        head = f"## Question {i}" + (f" (select all that apply, {len(correct_opts(q))} correct answers)" if multi else "")

        def txt(s, q=q):
            return fill_images(plain(s), q, desc, missing)
        out += [head, "", txt(q["question"]), "", "Options:"]
        out += [f"{o['letter'].upper()}. {txt(o['text'])}" for o in q["options"]]
        label = "Correct answers" if multi else "Correct answer"
        out += ["", f"{label}: " + "; ".join(f"{o['letter'].upper()}. {txt(o['text'])}" for o in correct_opts(q)), ""]
        out += ["Explanation:", clean_explanation(q["explanation"]), ""]
    return "\n".join(out).rstrip() + "\n"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


FOCUS = (
    "This is a deep dive podcast into the technical details and internals of {subject}, so the listener becomes "
    "thoroughly familiar with the content of the {exam} exam. Assume a good {subject} background; skip beginner "
    "explanations. The selected sources are practice questions grouped by topic. Cover every question in all "
    "selected sources, working through the sources one after another in file-name order. For each question: briefly "
    "set up the scenario and ask the listener to pick an answer before revealing it, give the correct answer and "
    "explain at a technical level why it is right (how it works, limits, defaults), explain why each wrong option is "
    "wrong and what trap makes it tempting, and end with a one-line rule of thumb. Refer to options by their content, "
    "not by letter. Use only facts from the sources. Finish with a recap of the key points."
)
FOCUS_SHORT = (
    "Deep dive for a listener with a good {subject} background preparing for {exam}. Cover EVERY question in all "
    "selected sources, source by source in file-name order: set up the scenario, give the correct answer and the "
    "technical reason, explain why each wrong option is wrong, end with a one-line rule of thumb. Refer to options by "
    "content, not letter. Only use facts from the sources. End with a recap of the key points."
)


def how_to_use(cfg, episodes):
    fill = {"subject": cfg["subject"], "exam": cfg["exam"]}
    n_files = sum(len(e["files"]) for e in episodes)
    lines = [
        "# Make your podcast episodes in Gemini Notebook", "",
        f"You get **one Gemini Notebook** that holds all sources. Each episode is one Audio Overview made from "
        f"one group of sources: the folder `sources/E<n>_...` of that episode. Their file names start with `E<n>_`, "
        "so you can tell them apart in the notebook.", "",
        "1. Go to https://notebook.google.com and sign in with a Google account.",
        "2. Create a new notebook.",
        f"3. Add sources: upload all {n_files} files from the `sources/` folder (all episode folders).",
        "4. Make episode 1: in the notebook's source list select **only** the files whose names start with `E1_` "
        "(untick the others). Open **Audio Overview**, click the customize (pencil) button, set Format to "
        "**Deep Dive** and Length as in the table below, paste the focus text below into \"What should the AI hosts "
        "focus on in this episode?\", then Generate.",
        "5. Repeat for each other episode with its own files (`E2_`, `E3_`, ...). Each episode takes a few minutes; "
        "Google may limit how many you can generate per day.", "",
        "## Episodes", "",
        "| Episode | Title | Source folder | Questions | Files | Audio Overview length |",
        "|---|---|---|---|---|---|"]
    for e in episodes:
        lines.append(f"| {e['number']} | {e['title']} | `sources/{e['folder']}/` | {e['questions']} | "
                     f"{len(e['files'])} | {length_setting(e['questions'])} |")
    lines += ["", "Rough guide (a guess, calibrate with your first episode): about 20 questions make roughly 15 "
              "minutes, 45 questions about 35 minutes, 90 questions about 70 minutes. If the hosts skip questions "
              "or an episode gets too long, use fewer questions per episode next time.", "",
              "## Text for the focus box (same for every episode)", "", FOCUS.format(**fill), "",
              "Shorter version (if the box rejects the long one):", "", FOCUS_SHORT.format(**fill), "",
              "## Topics per episode", ""]
    for e in episodes:
        lines.append(f"**Episode {e['number']}: {e['title']}**")
        lines += [f"- {title} ({n} questions)" for _, title, n in e["files"]]
        lines.append("")
    return "\n".join(lines)


def cmd_build(args):
    cfg = load_notebook(args.name, args.notebook)
    qs = load_questions(cfg)
    topics, missing, extra = read_topics(cfg, qs)
    if missing or extra:
        sys.exit(f"topics.json does not match the questions (missing={missing}, unknown={extra}); run 'check'")
    plan, problems, _ = episode_plan(cfg, topics)
    if problems:
        sys.exit("Episode grouping has problems; run 'check':\n  " + "\n  ".join(problems))
    sources = cfg["dir"] / "sources"
    if sources.exists():
        shutil.rmtree(sources)  # only our own generated folder
    sources.mkdir()
    desc, missing_imgs = load_descriptions(cfg), []
    episodes, index = [], ["# Source index (question ids per file; not for upload)\n"]
    for number in sorted(plan):
        ep = {"number": number, "title": plan[number]["title"]}
        in_episode = set(plan[number]["topics"])
        eq = [q for q in qs if topics[q["qid"]] in in_episode]
        groups = defaultdict(list)
        for q in eq:  # keeps test, then question order within a topic
            groups[topics[q["qid"]]].append(q)
        final = {}
        for title, items in groups.items():
            parts = math.ceil(len(items) / MAX_TOPIC)
            if parts == 1:
                final[title] = items
                continue
            size = math.ceil(len(items) / parts)
            for p in range(parts):
                final[f"{title} (Part {p + 1} of {parts})"] = items[p * size:(p + 1) * size]
        words, short = slug(ep["title"]).split("-"), ""
        for w in words:  # cut at a word boundary, folder names stay readable
            if len(short) + len(w) + 1 > 40:
                break
            short = f"{short}-{w}" if short else w
        folder = f"E{number}_{short}" if short else f"E{number}"
        (sources / folder).mkdir()
        files = []
        index.append(f"\n## Episode {number}: {ep['title']}")
        for n, title in enumerate(sorted(final), 1):
            items = final[title]
            path = sources / folder / f"E{ep['number']}_{n:02d}_{slug(title)}.md"
            path.write_text(source_text(cfg, ep, title, items, desc, missing_imgs))
            files.append((path.name, title, len(items)))
            index.append(f"- {path.name}: {len(items)} questions, {len(path.read_text().split())} words — "
                         + ", ".join(q["qid"] for q in items))
        episodes.append({"number": number, "title": ep["title"], "folder": folder,
                         "questions": len(eq), "files": files})
    (cfg["dir"] / "work" / "source_index.md").write_text("\n".join(index) + "\n")
    (cfg["dir"] / "HOW_TO_USE.md").write_text(how_to_use(cfg, episodes))
    print(f"{len(episodes)} episode(s), {sum(len(e['files']) for e in episodes)} source files -> {sources}")
    for e in episodes:
        print(f"  episode {e['number']} ({e['title']}): {e['questions']} questions, {len(e['files'])} files, "
              f"length {length_setting(e['questions'])}")
    print(f"Instructions for the user -> {cfg['dir'] / 'HOW_TO_USE.md'}")
    if missing_imgs:
        print(f"WARNING: {len(missing_imgs)} image(s) have no description and read as 'not available' "
              f"(e.g. question {missing_imgs[0][0]}). Run 'images {args.name}' and describe them.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("import")
    i.add_argument("file")
    i.add_argument("--name", help="folder name under data/ (default: the course's url name)")
    pl = sub.add_parser("plan")
    pl.add_argument("name")
    pl.add_argument("--exclude", type=int, nargs="+", metavar="TEST", help="tests to leave out entirely")
    pr = sub.add_parser("prepare")
    pr.add_argument("name")
    pr.add_argument("--episodes", type=int, required=True, help="number of podcast episodes (see 'plan')")
    pr.add_argument("--exclude", type=int, nargs="+", metavar="TEST", help="tests to leave out entirely")
    pr.add_argument("--notebook", default="notebook")
    pr.add_argument("--exam", help="what the listener is preparing for (default: course title)")
    pr.add_argument("--subject", help="subject area for the podcast, e.g. AWS (default: --exam)")
    for cmd in ("images", "check", "build"):
        c = sub.add_parser(cmd)
        c.add_argument("name")
        c.add_argument("--notebook", default="notebook")
    args = p.parse_args()
    run = {"import": cmd_import, "plan": cmd_plan, "prepare": cmd_prepare, "images": cmd_images,
           "check": cmd_check, "build": cmd_build}
    sys.exit(run[args.command](args) or 0)


if __name__ == "__main__":
    main()
