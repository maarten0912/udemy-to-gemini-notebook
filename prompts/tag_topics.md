# Task for the AI agent: group the questions into study topics

You do this step yourself (no external AI or API key). It is the only step that needs judgment;
everything else is done by `scripts/udemy.py`.

**Input:** `output/<name>/notebook/work/questions_1.txt`, `questions_2.txt`, ... (chunks of up to 100
questions). The first line of each chunk names the exam and subject. Every other line is one
question: `id [domain] Q: <end of the question> A: <correct answer(s)>`.

**Output:** one JSON object saved as `output/<name>/notebook/work/topics.json`, mapping every
question id to a topic name, e.g. `{"4-1": "Messaging – Queues and Delivery", "4-2": "Deployment – Rollouts and Rollbacks"}`.

## Why

Each topic becomes one source file belonging to an episode (an episode is one podcast made
from a group of whole topics), and must teach one coherent concept. Gemini Notebook covers small,
focused documents completely, but only skims big mixed ones. That is why questions are grouped
by concept instead of by test. You tag all questions in one go; the next step
(`prompts/plan_episodes.md`) then groups whole topics into the episodes, so make topic names start
with their area ("Area – Concept"): related topics then sort and group together.

If `topics.json` already exists (for example after re-running `prepare` with other settings), only
add the ids that `check` reports as missing, reusing the existing topic names.

## Rules

1. A topic is one concept, service, tool or area of the subject. Decide by what the question
   actually tests (look at the correct answer), not by the story around it. Questions from
   different tests that test the same concept belong together.
2. Aim for about one topic per 6-14 questions (about 15-25 topics for ~200 questions).
   Merge topics that would have fewer than 4 questions into the closest related topic, unless
   they truly don't fit anywhere. Don't create topics with more than 16 questions (the build
   step splits those into parts anyway, but a good split by concept is better).
3. Name topics in Title Case, short, as "Area – Concept" with an en dash, in the language of
   the questions. Use the exact same string every time you reuse a topic.
4. Every id must appear exactly once. Never invent, drop or change ids.

## Procedure

1. Read the chunk files in order. Process one chunk at a time.
2. Before each chunk after the first, look at the topic names already in `topics.json` and reuse
   them exactly when a question fits. Add new topics only where nothing fits.
3. After each chunk, write (or extend) `topics.json`. Keep the ids from earlier chunks.
4. When all chunks are done, run `python3 scripts/udemy.py check <name>`. If it reports
   missing or unknown ids, or topics that are far too small, fix `topics.json` and run it again.
