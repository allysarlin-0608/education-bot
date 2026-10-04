# GNOSIS — product plan

From a daily lesson-and-quiz app to a learning companion people trust, return to
every day, and pay for. This is the plan to approve before anything is built.

---

## 1. Where GNOSIS is now

### What it already does well
- **Daily lessons with a real structure**: seven subjects, each with a written
  syllabus (~260 lessons so far, units in order), a placement check that sets
  the starting level, and a rotation of one subject a day at a chosen pace
  (1, 3 or 5 lessons).
- **A lesson that is checked**: each lesson has a 10-question quiz (multiple
  choice, matching, short answers marked by the AI) with an 80% pass mark, and
  every generated quiz goes through a verification and repair step.
- **Spaced review**: missed questions, vocabulary and key ideas become cards
  that come back at growing intervals (1 → 60 days), 20 a day.
- **A record**: streaks, a calendar, day details, a course map per subject,
  search across everything, a reading plan for books with daily check-ins.
- **A coach in the lesson**: follow-up questions about the lesson in a chat.
- **Solid foundations**: accounts with invites, each person's data isolated
  by row-level security, a daily AI allowance per person, backups, a test suite
  that runs before every push, a calm design on phone, iPad and desktop.

### The biggest gaps, compared with the best learning products

| Gap | Who does it well | Why it matters |
|---|---|---|
| You can only learn the 7 subjects we chose | Khan Academy (breadth), Brilliant (paths), ChatGPT-style tools (anything) | "Learn what *I* want" is the strongest reason to try and to pay |
| The first session doesn't show what makes GNOSIS different | Duolingo, Headway (personal plan right after a short questionnaire) | People decide in minutes whether a product is for them |
| Progress is counts (lessons, days), not mastery | Brilliant (skill map), Duolingo (skill levels), Khan (mastery) | People pay for proof they are getting better |
| Nothing brings you back if you don't open the app | Duolingo (reminders, streak freeze), Headway (daily goal) | Quitting is the main way learning products fail |
| Practice is reading + one quiz | Brilliant (interactive), Duolingo (varied exercises), Anki (recall) | Varied, active practice is how ideas stick |
| No "explain it back", no projects | (rare — an opening for GNOSIS) | The AI can do what other apps can't: check your understanding in your words |
| No weekly report, no completion moment | Duolingo, Headway, Coursera (certificates) | A visible milestone is a reason to stay and to share |
| No notes/highlights library, no listening | Readwise, Blinkist (audio) | Learning on the go; keeping what you learned |
| No public front door, no plans or payments, no terms/privacy | all of them | Strangers can't find, trust, or pay for it |

### What makes GNOSIS different (and should stay at the centre)
Other apps have fixed content (Duolingo, Brilliant, Blinkist) or no structure
(a chatbot). GNOSIS can do both: **a structured, checked course on anything you
want, that adapts to you, and a tutor who knows what you have learned.** Every
phase below strengthens that.

---

## 2. Recommended phases

Ordered by impact on learning, coming back, and willingness to pay. Each phase
is complete on its own and usable before the next starts.

### Phase 1 — Learn what you want, and feel it in the first ten minutes
*For the user: "I told it what I want to learn and it made me a real plan, and
the first lesson was excellent."*
- **Goal-based onboarding**: what do you want to learn, why, how much time a
  day (5 / 15 / 30 minutes), where you are now. The seven subjects appear as
  recommended starting points ("templates"), not the only choice.
- **AI-designed learning path** for any goal: an outcome ("by the end you will
  be able to…"), units, and lesson titles, shown for the learner to review,
  reorder, shorten or regenerate before starting. The path is generated once
  (one AI call plus a check that it is coherent and safe), then saved; lessons
  are written as they are reached, as today.
- **Several goals side by side** (the plan decides how many per tier), each
  with its own course map; the daily rotation becomes "today's goal" with an
  easy switch.
- **The first lesson as the "aha" moment**: the personal plan screen right
  after onboarding, a short first lesson, and a small win at the end (first
  card in review, first step on the map).
- **A daily goal in minutes** that adapts to the time chosen, instead of a fixed
  number of lessons.

### Phase 2 — Coming back, and seeing progress
*For the user: "It reminds me when I want, it forgives a bad day, and every
week it tells me what I learned."*
- **Reminders by email** at the time the learner chooses, off by default, one
  click to stop.
- **Streak protection**: one "rest day" earned per week of practice, used
  automatically, so one missed day doesn't erase a month.
- **Welcome back** after a break: no guilt, a two-minute warm-up review, then
  exactly where they left off.
- **Weekly report** (in the app, and by email if wanted): what you learned, what
  got stronger, what to review, time spent, next week's step.
- **"Where I started vs where I am now"**: the placement result and the first
  quiz scores beside today's.

### Phase 3 — Mastery you can see, and practice that sticks
*For the user: "I can see which ideas I really know and which are still shaky,
and the app makes me practise the shaky ones."*
- **Skill map**: every lesson's 2–4 key ideas (already extracted for review
  cards) become skills; each has a strength from quiz answers and reviews
  (new → learning → solid → mastered). The map replaces counts as the main view
  of progress.
- **Adaptive practice**: a daily "strengthen" set drawn from weak skills; faster
  through what is already mastered (skip ahead with a check).
- **More kinds of practice**: fill in the blank, put in order, matching,
  flashcards, a short scenario ("what would you do"), "apply it to your own
  life" — all generated with the lesson and verified like quizzes.
- **Explain it back** (Feynman): the learner explains an idea in their own
  words; the coach points out what is missing or wrong, kindly and precisely.
- **A tutor grounded in the lesson**: answers cite the lesson section they come
  from, say "I'm not sure" rather than invent, and stay on the learner's path.

### Phase 4 — Plans, payments (test mode), and a public front door
*For the user: "I can see what's free and what's paid, try it, pay easily, and
cancel easily."*
- Plans, trial, upgrade, account page with the current plan, cancellation —
  with **Stripe in test mode** and a feature flag that switches all of it off.
- Limits enforced on the server (the database), never only on the page.
- Upgrade prompts only at natural moments (a second goal, more lessons today,
  a paid feature), never in the middle of a lesson or quiz.
- **Public landing page**: what GNOSIS is, who it is for, real example lessons,
  sign up. **Privacy policy and terms** as drafts for you to review.

### Phase 5 — Depth that makes the paid plan worth it
*For the user: "I finish units with something real to show for it."*
- **Unit completion**: a summary of what was mastered, and a certificate (PDF)
  at the end of a path.
- **Unit projects**: a small real output (a one-page business plan, a personal
  style analysis, a watchlist with reasons) with AI feedback.
- **Notes and highlights** on any lesson, one searchable library, export
  (Markdown / PDF).
- **Listening mode**: lessons read aloud with the device's own voice (free, no
  AI cost), with speed control.
- Keyboard shortcuts on desktop; a final accessibility and polish pass.

Why monetization is Phase 4 and not first: the paid plan needs things worth
paying for (paths, progress, practice), and the habit features in Phase 2 are
what make a trial convert. The plan limits (server-side) will be designed in
Phase 1 so nothing has to be rebuilt later.

---

## 3. Free and paid

### The split

| | Free | Paid ("GNOSIS Plus") | Why |
|---|---|---|---|
| Learning goals (paths) | 1 active | Up to 5 active | One goal builds the habit and shows the value; more goals is the clearest reason to upgrade |
| New lessons a day | Up to 2 (~15 min) | Up to 6 (fair use) | Enough to learn properly for free; more speed is paid |
| Spaced review | Full | Full | Review is what makes learning stick — never paywall retention |
| Streaks, rest days, reminders, welcome back | Yes | Yes | Habit features keep free users around; they convert later |
| Coach questions in a lesson | 5 a day | Fair use (~60 a day) | The tutor is the most AI-expensive part |
| Skill map | Yes | Yes | Seeing progress is part of the core value |
| Weekly report | Short version | Full (what improved, what to review, trends) | |
| Adaptive "strengthen" practice, varied practice | 1 set a day | Unlimited | Faster progress is what people pay for |
| Explain it back | 1 a week (to try it) | Unlimited | A distinctive feature: let people feel it |
| Unit projects, certificates | — | Yes | Real outputs, natural paid value |
| Notes & highlights | Yes (no export) | Yes, with export | |
| Listening mode | — | Yes | No AI cost, but a convenience people pay for |
| Reading plan (books) | 1 book at a time | Unlimited | |

### Pricing (proposal)
- **Monthly US$8.99**, **yearly US$59.99** (about US$5 a month, 44% off).
- **7-day free trial** of Plus for new accounts, **no card needed** to start
  (fewer people drop off; a reminder two days before it ends).
- **Student discount**: 40% off the yearly plan (a coupon; verification kept
  simple at first).
- For reference: Duolingo Super ~US$13/month or ~US$84/year, Brilliant ~US$25/month
  or ~US$150/year, Headway ~US$13/month, Blinkist ~US$16/month. GNOSIS sits
  below them while being more personal.

### AI cost per active user (estimate)
Assumptions (to be checked against the real Groq invoice before launch):
- Model: `openai/gpt-oss-120b` on Groq's **paid** tier at about **US$0.15 per
  million input tokens and US$0.60 per million output tokens**.
- One lesson day ≈ lesson (~5k in / 1.5k out) + quiz with check (~3k in / 2.5k
  out) + short-answer marking (~1.5k in / 0.5k out) ≈ **10k in / 4.5k out ≈ US$0.0042
  per lesson**.
- One coach question ≈ 5k in / 0.6k out ≈ US$0.0011.
- A new path ≈ 3k in / 6k out ≈ US$0.004, once.
- Listening mode uses the device's voice: **US$0**.

| | Lessons a day | Coach questions a day | Days active a month | AI cost a month |
|---|---|---|---|---|
| Free, typical | 2 | 3 | 15 | ~US$0.18 |
| Plus, typical | 4 | 10 | 22 | ~US$0.61 |
| Plus, heavy (fair-use ceiling) | 6 | 40 | 30 | ~US$2.10 |

A typical paid user costs about 12% of the yearly plan's monthly price
(US$5); the heaviest user allowed by fair use about 42%, so even the ceiling is
covered with margin. Payment fees (Stripe ~2.9% + US$0.30 a charge)
are the bigger cost on a monthly plan, which is another reason to favour yearly.

**Important**: Groq's *free* tier allows about 8,000 tokens a minute **for the
whole app**, which is enough for testing but only a handful of people learning
at the same moment. Real users need Groq's paid tier (pay per use, no minimum).
This is a decision before any public launch, not before building.

---

## 4. How each phase is built and checked
- Built completely, phase by phase; ARCHITECTURE.md updated each time.
- New AI content (paths, practice types, feedback) goes through the same
  generate → check → repair approach the quiz uses, and is counted in the
  daily AI allowance.
- Tests: every new flow end to end, several days with a simulated clock,
  refreshes and double clicks, AI errors and slow network; screenshots on
  phone, iPad portrait, iPad landscape and desktop, light and dark, with the
  overlap and contrast checks.
- Real-AI testing spread over days to stay inside Groq's free quota.
- A report and your go-ahead after each phase.

---

## 5. Risks
- **AI quality on any topic**: a path or lesson on a topic we never wrote a
  syllabus for can be weaker or wrong. Mitigation: a coherence and safety check
  of each path, lessons verified as quizzes are, a "report a problem" button,
  and refusing goals that are unsafe (medical, legal, financial advice beyond
  education).
- **Groq capacity and cost** at real scale (see above); possibly a second
  provider as fallback later.
- **Email deliverability**: reminders need a sending service and a domain, or
  they land in spam.
- **Payments and tax**: real charges need a business account, tax settings, and
  refund handling — out of scope until you set up the real account.
- **Streamlit limits**: fine for this stage; a public product at scale may
  later need a faster front end. Nothing in this plan locks that in.

---

## 6. Decisions needed (with recommendations)
1. **Approve the phase order** (1 paths → 2 habit → 3 mastery → 4 payments →
   5 depth). *Recommendation: yes.*
2. **New database tables** in the test database, added alongside existing
   ones, changing no existing data: learning paths (Phase 1), reminders and
   reports (Phase 2), skills (Phase 3), subscriptions (Phase 4), notes (Phase 5).
   *Recommendation: approve now for all phases, each shown to you as SQL
   before it is run.*
3. **Prices and currency**: US$8.99 / US$59.99, 7-day trial without a card,
   40% student discount. Or prices in NT$ for Taiwan first. *Recommendation:
   USD, English product, global audience; NT$ later.*
4. **AI cost per user** goes up with paths (one extra call per new goal) and
   later practice types. *Recommendation: approve, within the existing daily
   allowance per person.*
5. **Stripe for payments, test mode only**. You would create a free Stripe
   account later; for testing I can use Stripe's test mode with keys you paste
   into the test app's secrets (one manual step), or I build and test against a
   fake Stripe so you do nothing now. *Recommendation: the fake now, real test
   keys only when you want to try a test payment yourself.*
6. **Email for reminders and reports**: a sending service such as Resend
   (free up to 3,000 emails a month) needs an account and a domain.
   *Recommendation: build reminders in Phase 2 with in-app reminders working
   immediately and email switched on once you create the account (one manual
   step later).*
7. **Groq paid tier before public launch**. *Recommendation: decide at Phase 4;
   not needed for building and testing.*
8. **Language of the product**: English UI today. *Recommendation: keep
   English; add Traditional Chinese later as its own phase.*

---

## 7. Decisions made
- **Starting audience (Phase 1)**: all three — working adults growing their
  skills (career, money, business), lifelong learners following their
  curiosity (art, science, history, travel), and students learning for school
  or an exam. Onboarding suggestions and examples cover the three.
- **Certificates** become one of the paid plan's benefits (Phase 5 / Phase 4
  split).
