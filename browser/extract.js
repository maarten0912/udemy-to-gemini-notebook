// Udemy practice-test extractor. Paste into the DevTools Console of a page of YOUR Udemy
// course while logged in (any page whose URL contains /course/<name>/).
//
// What it does: asks Udemy's own API (the same one the course player uses) for ALL practice
// tests of this course and downloads ONE json file to your computer. It only sends GET requests to udemy.com and sends nothing anywhere else.
// It never submits or changes a practice test attempt.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function get(url, tries = 4) {
    for (let i = 0; i < tries; i++) {
      const r = await fetch(url, { credentials: "include", headers: { accept: "application/json" } });
      if (r.ok) return r.json();
      if (r.status === 401 || r.status === 403) {
        const err = new Error(`Udemy says "not allowed" (HTTP ${r.status}). Are you logged in and enrolled in this course?`);
        err.notAllowed = true;
        throw err;
      }
      if (r.status !== 429 && r.status < 500) throw new Error(`HTTP ${r.status} for ${url}`);
      await sleep(500 * 2 ** i);
    }
    throw new Error("Udemy kept failing, giving up: " + url);
  }

  async function paginate(url) {
    const out = [];
    while (url) {
      const j = await get(url);
      out.push(...(j.results || []));
      url = j.next;
    }
    return out;
  }

  // Tests are locked until you are enrolled. On a Udemy Business site (not www.udemy.com) the script
  // enrolls you by clicking the page's own "Enroll now" button. It never calls a private enroll API,
  // and never does this on a personal account (there it can mean buying the course).
  // Set to true to get a yes/no dialog before enrolling.
  const CONFIRM_BEFORE_ENROLL = false;

  async function enrollThen(curriculumUrl, course, slug) {
    if (location.hostname === "www.udemy.com")
      throw new Error(
        "You are not enrolled in this course, so its tests are locked. On a personal Udemy account " +
          "enrolling can mean buying the course, so this script won't do it. Enroll yourself, then run it again."
      );
    if (CONFIRM_BEFORE_ENROLL) {
      const ok = confirm(
        `You are not enrolled in "${course.title}", so its tests are locked.\n\n` +
          `Enroll now? This adds the course to your learning list (your organization may see that). ` +
          `On a Udemy Business plan this is normally free.`
      );
      if (!ok) return null;
    }
    console.log(`Not enrolled in "${course.title}": enrolling via the page's Enroll button ...`);
    const findBtn = (doc) =>
      [...doc.querySelectorAll("button, a")].find(
        (el) => /^\s*(enroll now|enroll)\s*$/i.test(el.textContent || "") && el.offsetParent !== null
      );

    // Clicking Enroll makes Udemy reload the page into the course player, which would stop this
    // script. So click it inside a hidden frame of the course's landing page: this page (and the
    // script) stays alive while the frame reloads.
    const frame = document.createElement("iframe");
    frame.style.cssText = "position:fixed;left:-9999px;top:0;width:1280px;height:900px;border:0;opacity:0";
    frame.src = `${location.origin}/course/${slug}/`;
    document.body.appendChild(frame);
    let clicked = false;
    for (let i = 0; i < 12 && !clicked; i++) {
      await sleep(1500);
      try {
        const doc = frame.contentDocument; // null/throws if the site refuses to be framed
        if (doc && doc.body && doc.location.href !== "about:blank") {
          const b = findBtn(doc);
          if (b) {
            b.click();
            clicked = true;
          }
        }
      } catch (e) {
        /* keep trying until the loop ends, then fall back */
      }
    }

    if (!clicked) {
      // Fallback: click on this page. Udemy may reload it; if so the script stops and you run it again.
      frame.remove();
      const btn = findBtn(document);
      if (!btn)
        throw new Error(
          "I could not find an Enroll button. Open the course's main page " +
            "(the address ending in /course/<name>/) and run the script again, or enroll yourself first. " +
            "If your organization needs an admin to assign the course, ask them."
        );
      console.log("Clicking Enroll on this page. If the page reloads, paste and run the script once more.");
      btn.click();
    } else console.log("Clicked Enroll (in a hidden frame), waiting for Udemy to finish ...");

    for (let i = 0; i < 40; i++) {
      await sleep(1500);
      try {
        const items = await paginate(curriculumUrl);
        frame.remove();
        return items;
      } catch (e) {
        if (!e.notAllowed) throw e;
      }
    }
    frame.remove();
    throw new Error(
      "Enrolling did not finish within a minute. You may be enrolled now: run this script again. " +
        "Otherwise enroll yourself first."
    );
  }

  try {
    const m = location.pathname.match(/\/course\/([^/]+)/);
    if (!m) {
      alert("Open a page of your Udemy course first (the address should contain /course/<name>/), then run this again.");
      return;
    }
    const slug = m[1];

    const course = await get(`/api-2.0/courses/${slug}/?fields[course]=id,title`);
    const curriculumUrl =
      `/api-2.0/courses/${course.id}/subscriber-curriculum-items/?page_size=200` +
      `&fields[quiz]=title,type,id,version&fields[lecture]=id&fields[chapter]=id`;
    let items;
    try {
      items = await paginate(curriculumUrl);
    } catch (e) {
      if (!e.notAllowed) throw e;
      items = await enrollThen(curriculumUrl, course, slug); // null = you said no
      if (!items) return;
    }
    const quizzes = items.filter((i) => i._class === "quiz");
    let tests = quizzes.filter((q) => q.type === "practice-test");
    if (!tests.length && quizzes.length) tests = quizzes; // course without "practice-test" typed items
    if (!tests.length) {
      alert("No practice tests found in this course.");
      return;
    }
    tests.forEach((t, i) => (t.number = i + 1));
    const chosen = tests; // always all tests; which ones go into which episode is decided later
    console.log(`Found ${tests.length} test(s) in "${course.title}".`);

    const fields = "id,assessment_type,prompt,correct_response,section,question_plain,related_lecture_id,delivery_type";
    const bundle = {
      format: "udemy-practice-tests/1",
      extracted_at: new Date().toISOString(),
      origin: location.origin,
      course: { id: course.id, slug, title: course.title },
      quizzes: [],
    };
    for (const t of chosen) {
      console.log(`Fetching ${t.title} ...`);
      const v = t.version ? `&version=${t.version}` : "";
      const assessments = await paginate(
        `/api-2.0/quizzes/${t.id}/assessments/?page_size=100${v}&fields[assessment]=${fields}`
      );
      bundle.quizzes.push({ number: t.number, id: t.id, title: t.title, type: t.type, version: t.version, assessments });
      await sleep(150);
    }

    const total = bundle.quizzes.reduce((n, q) => n + q.assessments.length, 0);
    const blob = new Blob([JSON.stringify(bundle)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `udemy-${slug}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    const msg = `Done: downloaded udemy-${slug}.json (${chosen.length} test(s), ${total} questions). Go back to your AI assistant.`;
    console.log(msg);
  } catch (e) {
    console.error(e);
    alert("Something went wrong: " + e.message);
  }
})();
