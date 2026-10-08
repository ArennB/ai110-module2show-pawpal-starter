# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
================================================================
Today's Schedule
================================================================
Owner: Jordan
Pets:  Mochi (dog), Luna (cat)
Time:  75 min available from 08:00 (85 min of care requested)
----------------------------------------------------------------
Daily plan:
  08:00 - Feeding for Mochi (10 min) [priority: high, daily]
  08:10 - Feeding for Luna (10 min) [priority: high, daily]
  08:20 - Morning walk for Mochi (30 min) [priority: high, daily]
  08:50 - Playtime for Luna (15 min) [priority: medium, daily]
  Total planned: 65 min
  Order: highest priority first, shortest first on ties.

Skipped (not enough time left):
  Brush fur for Luna (20 min) [priority: low, weekly]
================================================================
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest -m pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
platform darwin -- Python 3.13.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/arenn/Documents/GitHub/ai110-module2show-pawpal-starter
plugins: anyio-4.15.1
collected 42 items                                                                                             

tests/test_pawpal.py ..........................................                                          [100%]

============================================== 42 passed in 0.04s ==============================================
```

## Features

- **Sorting by priority** - high to low, shortest first on ties
- **Time-budget fitting** - skips what doesn't fit, keeps trying shorter tasks
- **Fixed-time tasks** - pinned appointments, with flexible tasks routed around them
- **Conflict warnings** - flags overlapping tasks for the same pet or different pets
- **Daily/weekly recurrence** - completing a task queues its next occurrence
- **Filtering** - by pet, completion status, or due date

## Smarter Scheduling

All scheduling logic lives in `pawpal_system.py`. `Scheduler` makes the decisions,
`Schedule` records them.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_tasks()` | Priority high→low, then shortest first on ties |
| Filtering | `Owner.filter_tasks()`, `Owner.pending_tasks()`, `Scheduler._fits()` | By pet, completion status, due date; and by time remaining |
| Conflict handling | `Scheduler.find_conflicts()`, `ScheduledTask.overlaps()`, `Scheduler._next_free_slot()` | Avoids what it can, warns about what it can't |
| Recurring tasks | `Task.next_occurrence()`, `Pet.complete_task()` | Completing a daily/weekly task queues the next instance |

### Sorting

`Scheduler.sort_tasks(pet_tasks)` returns `(pet, task)` pairs in placement order
using a tuple key:

```python
return (-task.priority, task.duration_minutes)
```

Python compares the second element only when the first ties. `Priority` is an
`IntEnum` where `HIGH` is largest, so negating it flips the ascending sort into
most-important-first. Duration stays ascending, so a 10-minute feeding is placed
before a 30-minute walk at equal priority — this packs more care into the same
budget. `sorted()` is stable, so tasks matching on both keys keep the order they
were entered in.

Pairs are sorted rather than bare tasks so the pet survives the sort and each
entry can become a `ScheduledTask`.

Two other orderings exist: `Schedule.summary()` sorts entries by `start_minutes`
for display (pinned tasks are placed before flexible ones, so storage order isn't
clock order), and `Scheduler.upcoming_tasks()` sorts by `due_date`.

### Filtering

**By pet and completion status** — `Owner.filter_tasks(pet_name, is_completed, due_by)`.
Each argument defaults to `None` meaning *don't filter on this*, so they combine
freely:

```python
owner.filter_tasks(pet_name="Luna")                       # Luna's tasks
owner.filter_tasks(is_completed=True)                     # everything done
owner.filter_tasks(pet_name="Mochi", is_completed=False)  # Mochi's outstanding
owner.filter_tasks()                                      # everything
```

`None` rather than a default like `False` matters — otherwise you could never ask
for completed tasks across all pets without secretly filtering on something else.

**By due date** — `Owner.pending_tasks(on)` narrows to tasks outstanding *and*
due on or before a given day. Tasks due earlier are included, so something missed
yesterday carries over instead of vanishing. This is what keeps a freshly-queued
recurring task out of today's plan.

**By time remaining** — `Scheduler._fits()` checks
`used_minutes + task.duration_minutes <= budget` before each placement. Tasks that
don't fit go into `Schedule.skipped` rather than disappearing. The loop keeps
going rather than stopping at the first failure, so a short low-priority task can
still fill a gap a long high-priority one couldn't use.

### Conflict detection

Two tasks conflict when their time ranges intersect — for the same pet or across
different pets, since either way the owner can only be in one place.

`ScheduledTask.overlaps(other)` is the test, treating each placement as a
half-open interval `[start, end)`:

```python
return self.start_minutes < other.end_minutes and other.start_minutes < self.end_minutes
```

So a task ending at 08:30 and one starting at 08:30 are back-to-back, not in
conflict. The test is symmetric.

`Scheduler.find_conflicts(schedule)` sorts entries by start time and compares each
against the ones after it, so a pair is reported once and results come out in
clock order. `Scheduler.describe_conflicts()` renders them, labelling each as
*same pet* or *different pets*.

Conflicts are handled in two ways depending on whether the scheduler can do
anything about them:

- **Avoided** — `Task.required_start` pins a task to a set time (a vet
  appointment). `Scheduler.build_plan()` places pinned tasks first, then routes
  flexible tasks around them with `_next_free_slot()`, which jumps the candidate
  start past any blocker and re-checks. A flexible task therefore never collides.
- **Reported** — two *pinned* tasks wanting the same slot can't be resolved
  automatically. Both are kept, and the clash is recorded in `Schedule.warnings`
  and printed by `summary()`. The scheduler never raises; a plan always comes back.

```
09:00 - Vet appointment for Mochi (30 min) [priority: high]
09:00 - Medication for Luna (15 min) [priority: high, daily]

Warnings:
  Vet appointment for Mochi (09:00-09:30) overlaps Medication for Luna (09:00-09:15) [different pets]
```

### Recurring tasks

`Task.frequency` is `"once"`, `"daily"` or `"weekly"`, and `FREQUENCY_STEPS` maps
the repeating ones to a `timedelta`. A frequency absent from that map doesn't
repeat.

Completing a task through `Pet.complete_task(task)` marks it done and immediately
queues the next instance, due **completion day + 1** for daily and **+ 7** for
weekly. The new copy keeps the title, duration, priority, frequency and any fixed
start time.

The split matters: `Task.next_occurrence()` builds the copy but attaches it to
nothing, because `Task` holds no reference to its `Pet` — adding one would make
the generated `__eq__` recurse. `Pet` owns the list, so `Pet` does the appending.

The next date counts from the day the task was *completed*, not from its own due
date, so finishing a daily task late still puts the next one a day ahead rather
than back in today's plan.

`Pet.uncomplete_task()` undoes a completion and removes the queued instance,
matching it **by identity** — two instances of the same daily task compare equal
as dataclasses, so `list.remove` would drop whichever came first.

`Scheduler.upcoming_tasks()` lists what's queued for later, soonest first.

## Demo Walkthrough

Run the app with `streamlit run app.py`.

**What a user can do**

- Set the owner's name and minutes available today
- Add pets (name and species)
- Add tasks with a duration, priority, repeat setting, and optional fixed start time
- Filter the task list by pet or status, and check tasks off
- Generate today's schedule and see what was planned, skipped, or in conflict

**Example workflow**

1. Enter owner `Jordan` with 75 minutes available.
2. Add pets `Mochi` (dog) and `Luna` (cat).
3. Add tasks, e.g. `Feeding` for each pet, and a `Vet appointment` for Mochi fixed at `09:00`.
4. Click **Generate schedule** to view today's plan.
5. Check off a daily task; its next instance appears under **Queued for later**.

**Key scheduler behaviors**

- **Sorting** - highest priority first, shortest first on ties
- **Time budget** - tasks that don't fit are listed as skipped
- **Fixed times** - pinned tasks stay put; flexible tasks fill the free slots around them
- **Conflict warnings** - overlapping fixed-time tasks are kept and flagged
- **Recurrence** - completing a daily/weekly task queues the next one

**Sample CLI output** (`python main.py`, excerpt)

```
--- Today's Schedule --------------------------------------------
Daily plan:
  08:00 - Feeding for Mochi (10 min) [priority: high, daily]
  08:10 - Feeding for Luna (10 min) [priority: high, daily]
  08:20 - Vet paperwork for Mochi (5 min) [priority: low]
  09:00 - Vet appointment for Mochi (30 min) [priority: high]
  09:00 - Medication for Luna (15 min) [priority: high, daily]
  Total planned: 70 min
  Order: highest priority first, shortest first on ties.

Skipped (not enough time left):
  Morning walk for Mochi (30 min) [priority: high, daily]
  Playtime for Luna (15 min) [priority: medium, daily]
  Evening walk for Mochi (45 min) [priority: medium, daily]
  Brush fur for Luna (20 min) [priority: low, weekly]

Warnings:
  Vet appointment for Mochi (09:00-09:30) overlaps Medication for Luna (09:00-09:15) [different pets]

--- Queued for later --------------------------------------------
  2026-10-08  Morning walk for Mochi (daily)
  2026-10-08  Feeding for Mochi (daily)
```
