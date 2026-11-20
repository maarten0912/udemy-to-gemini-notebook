# Task for the AI agent: group the topics into episodes

You do this step yourself, then show the result to the user and let them adjust it.

**Input:** `output/<name>/notebook/work/topics.json` (question id -> topic name) and the number of
episodes from `notebook.json` (`episodes`). `python3 scripts/udemy.py check <name>` lists every topic
with its question count.

**Output:** `output/<name>/notebook/work/episodes.json`:

```json
{"1": {"title": "Ingestion, Streaming and Spark", "topics": ["Auto Loader – Ingestion", "Structured Streaming – Windows"]},
 "2": {"title": "Delta Lake and Security", "topics": ["Delta Lake – Tables", "Data Security – Masking"]}}
```

## Rules

1. Exactly as many episodes as `notebook.json` says (keys `"1"` .. `"N"`). Every topic name from
   `topics.json` appears in exactly one episode, spelled exactly the same.
2. Balance the question counts: each episode should be within about 25% of the average (total
   questions divided by the number of episodes). Topics are not split across episodes, so move
   whole topics to balance.
3. Keep related topics together so each episode feels like a coherent lesson (for example all
   streaming topics together, all security topics together), and order the episodes so that the
   learning builds up where that makes sense.
4. Give each episode a short, descriptive title (3-8 words). It becomes the folder name and the
   name shown to the user.

## Procedure

1. Read the topics and their sizes, draft the grouping.
2. Show the user a short proposal: per episode its title, question count and topics. Ask if
   they want to change anything (move a topic, rename an episode).
3. Save `episodes.json`, run `python3 scripts/udemy.py check <name>` and fix every PROBLEM it
   prints (missing topic, topic in two episodes, wrong number of episodes).
