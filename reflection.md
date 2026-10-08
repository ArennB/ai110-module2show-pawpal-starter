# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Users should be able to add and edit tasks, enter owner and pet info, generate a plan.

- Briefly describe your initial UML design
    Owner has pets, available time, a day start time, and preferred task types.
    Pet has care tasks, each with a duration, recurrence, and Priority (LOW, MEDIUM, or HIGH).
    Scheduler uses the owner’s pets and constraints to build a Schedule.
    Schedule tracks scheduled entries, skipped tasks, and total minutes.
    ScheduledTask connects a task to a pet and assigns its start time.

- What classes did you include, and what responsibilities did you assign to each?
    Priority — defines the three importance levels and their order. 
   
    Task — knows what a single unit of care is: its title, how long it takes, how important it is, and how often it repeats.

    Pet — holds an animal's identity and the tasks it needs. Answers "how many minutes of care do I require in total?" 

    Owner — holds the person, their pets, and the constraints on their day (available_minutes, day_start, preferred_types).

    ScheduledTask — binds one task to one pet at one start time. Its whole job is keeping those three facts together so they can't get out of sync.

    Schedule — the result. Holds the placed entries, the tasks that didn't fit, and the total time used, and renders itself as readable

    Scheduler — makes the decisions. Sorts tasks, checks what fits in the remaining time, walks the clock forward from day_start, and returns a Schedule.

**b. Design changes**

- Did your design change during implementation?
No, it did not
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?

My scheduler considers four constraints:

Available time: Tasks must fit within the owner’s time budget. Tasks that do not fit are listed as skipped.

Priority: Higher-priority tasks are scheduled first.

Fixed start times: Appointments are scheduled at their required times. Flexible tasks fit around them.

Completion and due date: Completed tasks and tasks due after today are left out.

- How did you decide which constraints mattered most?

I put available time and fixed appointments first because ignoring either would make the plan impossible to follow. Priority then decides which flexible tasks get scheduled when time is limited.

I also removed owner preferences because the scheduler did not actually use them. Keeping them would suggest a feature worked when it did not.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.

When tasks have the same priority, the scheduler puts shorter tasks first. For example, it schedules a 10-minute feeding before a 30-minute walk. This helps fit more tasks into the available time, but the order may feel less natural.

- Why is that tradeoff reasonable for this scenario?

A busy owner has limited time, so completing more care tasks is useful. The owner can adjust the suggested order if needed.

The scheduler also continues after a task does not fit. If 20 minutes remain, it skips a 25-minute walk but can still schedule 15 minutes of playtime. This uses the remaining time, though it may mean a lower-priority task gets scheduled while a higher-priority task is skipped.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

I used AI to turn my UML into class stubs, implement sorting, conflict detection and recurrence step by step, write tests, connect the logic to the Streamlit UI, and draft documentation.

- What kinds of prompts or questions were most helpful?

Specific, file-scoped prompts worked best, such as "add conflict detection to Scheduler in pawpal_system.py". Asking "what edge cases could break this?" was also useful, because it surfaced cases like back-to-back tasks and completing a task twice.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

The early design gave Owner a list of preferred task types, but the scheduler never used it. I removed it rather than keep a field that suggested a feature that didn't exist. I also cut down AI drafted documentation that was longer than it needed to be.

- How did you evaluate or verify what the AI suggested?

I ran `main.py` to check the output by eye, ran the pytest suite after each change, and tried the same steps in the Streamlit app.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?

Sorting (priority, tie-breaking, stability), fitting tasks into the time budget (exact fit, skipping and continuing), recurrence (daily, weekly, year rollover, late completion, undo), due dates (overdue carry-over, future tasks left out), conflict detection (overlap, back-to-back, same-time fixed tasks), and time parsing. There are 42 tests, and all pass.

- Why were these tests important?

The scheduler's value depends on these rules being right. A bug in sorting or recurrence would quietly produce a wrong plan without crashing, so tests are the only reliable way to catch it.

**b. Confidence**

- How confident are you that your scheduler works correctly?

Fairly confident (4/5). The core rules and their edge cases are covered, but the Streamlit UI is only tested by hand.

- What edge cases would you test next if you had more time?

A plan that runs past midnight, a fixed task set before the day's start time, two pets with the same name, and a fixed task that is longer than the whole time budget.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

Conflict handling. Flexible tasks are routed around fixed appointments, and clashes that can't be resolved are reported instead of hidden or crashing the app.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

I would save pets and tasks to a file so they last between sessions, allow editing and deleting tasks, and suggest a new time when two fixed tasks clash instead of only warning.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

Designing the classes first made the AI's help much more useful, because I could give it clear, small tasks. But I still had to check every suggestion, since AI will confidently add things that look right but aren't needed or don't work.
