# Task for the AI agent: describe the images inside questions

Some questions carry their key data in an image (a table before/after an update, a job diagram, a
statistics screenshot, a code screenshot). The podcast hosts only get text, so each image must
become a text description that makes the question answerable without seeing the picture.

**Input:** the files that `python3 scripts/udemy.py images <name>` downloaded to
`output/<name>/notebook/work/images/`, named `<question id>_<image number>.<ext>` (for example
`1-14_2.png`). In the source text the image appears as `[image 2]` in the question or an option.

**Output:** `output/<name>/notebook/work/image_descriptions.json`, one entry per image:

```json
{"1-14": {"1": "Table 'Before' with columns id, name, city. Row 1: ...", "2": "Table 'After' ..."}}
```

The first key is the question id, the second the image number. Keep existing entries when you add
new ones.

## How to describe

1. Open (view) each image yourself. Read the question and its options first (they are in
   `data/<name>/tests/testN.json`) so you know what the image is for.
2. Be factual and complete. Transcribe every piece of text, number, label, status, code line and
   table row that matters for the question. Describe tables row by row ("Row 1: id 1, name Alice,
   city Paris"), diagrams as boxes and connections in words ("Task 1 runs first, then Task 2 and
   Task 3 run in parallel, Task 4 depends on both"), screenshots by their relevant visible values.
3. Written to be read aloud: plain sentences or short lines, no markdown tables, no pipes.
   Usually 2-8 lines.
4. Do not solve the question: don't state or hint at the answer, don't interpret beyond what is
   visible. If part of the image is unreadable, say so instead of guessing.
5. Sanity check against the correct answer and explanation in the test data: your description
   must be consistent with them. If it is not, look at the image again.

When done, run `python3 scripts/udemy.py check <name>` (it reports images still missing a
description), then `build`, and read two or three of the affected questions in the generated files.
