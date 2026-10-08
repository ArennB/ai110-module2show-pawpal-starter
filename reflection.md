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
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
