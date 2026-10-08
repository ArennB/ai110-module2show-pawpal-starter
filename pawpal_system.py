"""PawPal+ logic layer.

Backend classes for the pet care planner, converted from diagrams/uml_draft.mmd.
This module holds no Streamlit code so it can be imported and tested on its own.

Structure:
    Priority       - how important a task is
    Task           - a single activity: description, time, frequency, completion
    Pet            - pet details and a list of tasks
    Owner          - manages multiple pets, provides access to all their tasks
    ScheduledTask  - one Task placed at a start time, for one Pet
    Schedule       - the finished plan (entries + what got skipped)
    Scheduler      - the brain: retrieves, organizes, and manages tasks

Times are held as minutes since midnight and formatted only for display, which
keeps the clock arithmetic in build_plan to plain integer addition.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import IntEnum


MINUTES_PER_DAY = 24 * 60

# How far ahead each recurring task's next instance falls due. A frequency that
# is absent here (such as "once") does not repeat.
FREQUENCY_STEPS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def format_time(minutes_since_midnight: int) -> str:
    """Render minutes since midnight as "HH:MM", e.g. 545 -> "09:05".

    Wraps at midnight, so a plan running past 24:00 reads 00:20 rather than 24:20.
    """
    hours, minutes = divmod(minutes_since_midnight % MINUTES_PER_DAY, 60)
    return f"{hours:02d}:{minutes:02d}"


def parse_time(text: str) -> int | None:
    """Parse "HH:MM" into minutes since midnight, or None if it is not a valid time.

    Returns None rather than raising on anything it cannot read, so malformed
    input from a form degrades to "no fixed time" instead of taking the app down.

    Hours and minutes are range-checked separately rather than as a total:
    "08:99" would otherwise roll over into a perfectly plausible-looking 09:39.

    Args:
        text: The value to read, e.g. "09:00". Anything may be passed.

    Returns:
        Minutes since midnight (0 to 1439), or None for empty, malformed or
        out-of-range input.
    """
    try:
        hours_text, minutes_text = str(text).strip().split(":")
        hours, minutes = int(hours_text), int(minutes_text)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        return None
    return hours * 60 + minutes


def _frequency_note(task: "Task") -> str:
    """", daily" for a recurring task, or "" for a one-off, for display."""
    return "" if task.frequency == "once" else f", {task.frequency}"


class Priority(IntEnum):
    """How important a task is.

    IntEnum so tasks sort correctly with no extra ranking helper:
    Priority.HIGH > Priority.LOW is True.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class Task:
    """A single pet care activity: what it is, how long it takes, how important
    it is, how often it repeats, and whether it is done yet.

    e.g. a 30 minute high-priority morning walk, repeated daily.
    """

    title: str
    duration_minutes: int
    priority: Priority
    frequency: str = "once"  # "once", "daily", "weekly"
    is_completed: bool = False
    due_date: date = field(default_factory=date.today)
    # Minutes since midnight for a task that must happen at a set time, such as
    # a vet appointment. None means the scheduler may place it anywhere.
    required_start: int | None = None
    # The instance spawned when this one was completed. Excluded from equality
    # and repr so two tasks still compare on their own fields.
    successor: "Task | None" = field(default=None, compare=False, repr=False)

    @property
    def is_pinned(self) -> bool:
        """Whether this task must run at a set time rather than wherever it fits."""
        return self.required_start is not None

    def mark_complete(self) -> None:
        """Mark this task done, so it drops out of today's plan."""
        self.is_completed = True

    def mark_incomplete(self) -> None:
        """Mark this task outstanding again."""
        self.is_completed = False

    def is_due(self, on: date | None = None) -> bool:
        """Whether this task is outstanding and due on or before the given day."""
        return not self.is_completed and self.due_date <= (on or date.today())

    def next_occurrence(self, completed_on: date | None = None) -> "Task | None":
        """A fresh copy of this task due next time round, or None if it is a one-off.

        Looks the frequency up in FREQUENCY_STEPS to get the interval; a
        frequency that is not listed, such as "once", does not repeat and yields
        None. The new due date counts forward from the day the task was
        completed rather than from its own due date, so finishing a daily task
        late still puts the next one a day ahead instead of back in today's plan.

        The copy keeps the title, duration, priority, frequency and any fixed
        start time, and starts outstanding with no successor of its own.

        Args:
            completed_on: The day this task was finished; defaults to today.

        Returns:
            The next Task instance, or None for a task that does not repeat. It
            is not attached to any pet - see Pet.complete_task for that.
        """
        step = FREQUENCY_STEPS.get(self.frequency)
        if step is None:
            return None
        return Task(
            self.title,
            self.duration_minutes,
            self.priority,
            frequency=self.frequency,
            due_date=(completed_on or date.today()) + step,
            required_start=self.required_start,
        )


@dataclass
class Pet:
    """An animal and the tasks it needs."""

    name: str
    animal_type: str
    # default_factory gives each Pet its own empty list instead of one shared list.
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet."""
        self.tasks.append(task)

    def complete_task(self, task: Task, completed_on: date | None = None) -> Task | None:
        """Mark a task done, queue its next occurrence, and return that new task.

        Lives on Pet rather than Task because Pet owns the list the new instance
        has to go into, and Task deliberately holds no reference back to its Pet
        - adding one would make the generated __eq__ recurse.

        The new instance is recorded on the original as its successor, so an
        undo can find and remove it again.

        Completing a task that is already done is a no-op: it returns the
        successor queued the first time instead of queueing a duplicate.

        Args:
            task: One of this pet's tasks.
            completed_on: The day it was finished; defaults to today.

        Returns:
            The queued next instance, or None if the task does not repeat.
        """
        if task.is_completed:
            return task.successor
        task.mark_complete()
        task.successor = task.next_occurrence(completed_on)
        if task.successor is not None:
            self.tasks.append(task.successor)
        return task.successor

    def uncomplete_task(self, task: Task) -> None:
        """Undo a completion, removing the next occurrence it queued up.

        The successor is matched by identity rather than equality. Two instances
        of the same daily task compare equal as dataclasses, so list.remove would
        drop whichever appeared first - which may be the original, not the copy.
        Filtering on `is` removes exactly the object that was queued.

        Safe on a task that never spawned anything: it simply marks it
        outstanding again.
        """
        task.mark_incomplete()
        if task.successor is not None:
            self.tasks = [item for item in self.tasks if item is not task.successor]
        task.successor = None


@dataclass
class Owner:
    """Manages multiple pets and provides access to all of their tasks.

    Also carries the constraints on the owner's day (how much time they have,
    and when it starts).
    """

    name: str
    pets: list[Pet] = field(default_factory=list)
    available_minutes: int = 60
    day_start_minutes: int = 8 * 60  # 08:00

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner."""
        self.pets.append(pet)

    def all_tasks(self) -> list[tuple[Pet, Task]]:
        """Every (pet, task) pair across all of this owner's pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def filter_tasks(
        self,
        pet_name: str | None = None,
        is_completed: bool | None = None,
        due_by: date | None = None,
    ) -> list[tuple[Pet, Task]]:
        """The (pet, task) pairs matching the given pet, completion status and due date.

        Each argument defaults to None meaning "do not filter on this", so the
        three can be combined freely and filter_tasks() with none of them returns
        everything. None rather than a default like False matters: otherwise
        there would be no way to ask for completed tasks across all pets without
        secretly filtering on something else as well.

        Args:
            pet_name: Exact pet name to match; case sensitive.
            is_completed: True for finished tasks, False for outstanding ones.
            due_by: Latest due date to include, so overdue tasks still count.

        Returns:
            Matching (pet, task) pairs in pet order, then task order.
        """
        return [
            (pet, task)
            for pet, task in self.all_tasks()
            if (pet_name is None or pet.name == pet_name)
            and (is_completed is None or task.is_completed is is_completed)
            and (due_by is None or task.due_date <= due_by)
        ]

    def pending_tasks(self, on: date | None = None) -> list[tuple[Pet, Task]]:
        """The (pet, task) pairs outstanding and due on or before the given day.

        The date bound is what keeps recurrence honest: without it, the instance
        spawned for tomorrow would appear in today's plan the moment its
        predecessor was ticked off. Tasks due earlier than the given day are
        included, so something missed yesterday carries over rather than
        vanishing.

        Args:
            on: The day being planned; defaults to today.
        """
        return self.filter_tasks(is_completed=False, due_by=on or date.today())


@dataclass
class ScheduledTask:
    """One task placed at a start time, for one pet.

    Holding the pet, the task, and the start time in a single object means they
    cannot drift out of sync the way parallel lists can.
    """

    pet: Pet
    task: Task
    start_minutes: int

    @property
    def start_time(self) -> str:
        """Start time as "HH:MM", for display."""
        return format_time(self.start_minutes)

    @property
    def end_minutes(self) -> int:
        """The minute of the day this task finishes."""
        return self.start_minutes + self.task.duration_minutes

    @property
    def end_time(self) -> str:
        """Finish time as "HH:MM", for display."""
        return format_time(self.end_minutes)

    def overlaps(self, other: "ScheduledTask") -> bool:
        """Whether this placement shares any minute of the day with another.

        Treats each placement as a half-open interval [start, end), so a task
        ending at 08:30 and one starting at 08:30 are back to back rather than
        in conflict. Two intervals intersect exactly when each starts before the
        other ends, which is the pair of comparisons below; the test is
        symmetric, so a.overlaps(b) always equals b.overlaps(a).
        """
        return self.start_minutes < other.end_minutes and other.start_minutes < self.end_minutes


@dataclass
class Schedule:
    """The finished plan: what got scheduled, and what did not fit.

    Both lists carry the pet as well as the task, so the plan can say which
    animal each line is about.
    """

    entries: list[ScheduledTask] = field(default_factory=list)
    skipped: list[tuple[Pet, Task]] = field(default_factory=list)
    # Problems the scheduler could not resolve but chose not to fail over, such
    # as two fixed-time tasks claiming the same slot.
    warnings: list[str] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        """Minutes of care planned. Derived, so it cannot fall out of sync."""
        return sum(entry.task.duration_minutes for entry in self.entries)

    def add_entry(self, entry: ScheduledTask) -> None:
        """Append a placed task to the plan."""
        self.entries.append(entry)

    def summary(self) -> str:
        """Render the plan as readable lines, including what was skipped."""
        if not self.entries and not self.skipped:
            return "No tasks to plan."

        lines: list[str] = []

        if self.entries:
            lines.append("Daily plan:")
            # Sorted for display: pinned tasks are placed before the flexible
            # ones, so entries is in insertion order, not clock order.
            for entry in sorted(self.entries, key=lambda item: item.start_minutes):
                lines.append(
                    f"  {entry.start_time} - {entry.task.title} for {entry.pet.name}"
                    f" ({entry.task.duration_minutes} min)"
                    f" [priority: {entry.task.priority.name.lower()}"
                    f"{_frequency_note(entry.task)}]"
                )
            lines.append(f"  Total planned: {self.total_minutes} min")
            lines.append("  Order: highest priority first, shortest first on ties.")
        else:
            lines.append("Daily plan: nothing fit in the time available.")

        if self.skipped:
            lines.append("")
            lines.append("Skipped (not enough time left):")
            for pet, task in self.skipped:
                lines.append(
                    f"  {task.title} for {pet.name}"
                    f" ({task.duration_minutes} min)"
                    f" [priority: {task.priority.name.lower()}"
                    f"{_frequency_note(task)}]"
                )

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  {warning}" for warning in self.warnings)

        return "\n".join(lines)


class Scheduler:
    """The brain: retrieves, organizes, and manages tasks across all of an
    owner's pets.

    Retrieves them via Owner.pending_tasks(), organizes them with sort_tasks()
    and build_plan(), and looks across days with upcoming_tasks().

    Deliberately not a dataclass: it holds no state. Everything it needs arrives
    as a parameter, which keeps it testable without any UI.
    """

    def build_plan(self, owner: Owner, on: date | None = None) -> Schedule:
        """Plan one day across all of the owner's pets, skipping what does not fit.

        Runs in two passes, because a fixed-time task cannot be moved and a
        flexible one can:

        1. Pinned tasks (those with a required_start) are placed at their stated
           time, earliest first, so that the rest of the day has something solid
           to work around.
        2. Flexible tasks follow in sort_tasks() order, each starting at the
           first free minute _next_free_slot() can find.

        A task is placed only if _fits() says the owner still has the minutes for
        it. Otherwise it goes to Schedule.skipped and the loop continues rather
        than stopping, since a shorter task further down the list may still fit.

        Elapsed time and booked time are tracked separately: the clock is where
        the day has reached, used_minutes is how much work is committed. Routing
        around a pinned task leaves an idle gap, which moves the clock on but
        costs the owner nothing.

        Any overlap surviving both passes is two pinned tasks claiming the same
        slot, which cannot be resolved automatically. Both are kept and the clash
        is recorded in Schedule.warnings instead of raising.

        Args:
            owner: Whose pets, tasks and daily constraints to plan around.
            on: The day being planned; defaults to today. Tasks due later and
                tasks already completed are left out.

        Returns:
            A Schedule holding the placed entries, the skipped (pet, task) pairs,
            and a warning line for each unresolved clash.
        """
        schedule = Schedule()
        pet_tasks = owner.pending_tasks(on)

        pinned = [(pet, task) for pet, task in pet_tasks if task.is_pinned]
        flexible = [(pet, task) for pet, task in pet_tasks if not task.is_pinned]

        used_minutes = 0

        for pet, task in sorted(pinned, key=lambda pet_task: pet_task[1].required_start):
            if self._fits(task, used_minutes, owner.available_minutes):
                schedule.add_entry(ScheduledTask(pet, task, task.required_start))
                used_minutes += task.duration_minutes
            else:
                schedule.skipped.append((pet, task))

        clock = owner.day_start_minutes
        for pet, task in self.sort_tasks(flexible):
            if not self._fits(task, used_minutes, owner.available_minutes):
                schedule.skipped.append((pet, task))
                continue

            clock = self._next_free_slot(clock, task.duration_minutes, schedule)
            schedule.add_entry(ScheduledTask(pet, task, clock))
            clock += task.duration_minutes
            used_minutes += task.duration_minutes

        schedule.warnings.extend(
            self._describe_pair(earlier, later)
            for earlier, later in self.find_conflicts(schedule)
        )
        return schedule

    def _next_free_slot(
        self, start_minutes: int, duration_minutes: int, schedule: Schedule
    ) -> int:
        """The earliest minute at or after start where duration clears every entry.

        Sweeps the schedule looking for an entry the candidate window would
        overlap. On finding one it jumps the candidate to that entry's end and
        sweeps again, because landing past one blocker can run straight into the
        next. The loop ends because the candidate only ever moves forward and
        there are finitely many entries.

        Args:
            start_minutes: Earliest acceptable start, as minutes since midnight.
            duration_minutes: How long the task needs.
            schedule: The plan so far, whose entries must be avoided.

        Returns:
            The first minute at or after start_minutes where a block of
            duration_minutes fits without touching an existing entry.
        """
        candidate = start_minutes
        shifted = True
        while shifted:
            shifted = False
            for entry in schedule.entries:
                if (
                    candidate < entry.end_minutes
                    and entry.start_minutes < candidate + duration_minutes
                ):
                    candidate = entry.end_minutes
                    shifted = True
        return candidate

    def sort_tasks(self, pet_tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Order (pet, task) pairs by priority high to low, then shortest first.

        The key is a tuple, so Python compares the second element only when the
        first ties. Priority is negated because Priority is an IntEnum where HIGH
        is the largest value, and negating it flips the ascending sort into
        most-important-first. Duration is left ascending so that short tasks win
        ties, which packs more care into the same time budget.

        sorted() is stable, so tasks matching on both keys stay in the order the
        owner entered them. Pairs are taken and returned rather than bare tasks,
        so the pet survives the sort and each entry can become a ScheduledTask.

        Args:
            pet_tasks: The (pet, task) pairs to order.

        Returns:
            A new list in placement order; the input is left untouched.
        """

        def sort_key(pet_task: tuple[Pet, Task]) -> tuple[int, int]:
            _, task = pet_task
            return (-task.priority, task.duration_minutes)

        return sorted(pet_tasks, key=sort_key)

    def _fits(self, task: Task, used_minutes: int, budget_minutes: int) -> bool:
        """Whether this task still fits inside the remaining time budget."""
        return used_minutes + task.duration_minutes <= budget_minutes

    def find_conflicts(
        self, schedule: Schedule
    ) -> list[tuple[ScheduledTask, ScheduledTask]]:
        """Every pair of entries that overlap in time, earliest pair first.

        Sorts the entries by start time, then compares each entry against the
        ones after it, so a pair is reported once rather than twice and the
        results come out in clock order. Comparison is purely on time, so a
        single pet double-booked and two pets needing the owner at once are
        caught the same way.

        This is a pairwise scan rather than a sweep line: a day holds a handful
        of tasks, so the quadratic cost is irrelevant and the simpler version is
        one a reader can check by eye.

        Args:
            schedule: The plan to inspect.

        Returns:
            A list of (earlier, later) ScheduledTask pairs sharing at least one
            minute. Empty when the plan is clean.
        """
        ordered = sorted(schedule.entries, key=lambda entry: entry.start_minutes)
        return [
            (earlier, later)
            for index, earlier in enumerate(ordered)
            for later in ordered[index + 1 :]
            if earlier.overlaps(later)
        ]

    def _describe_pair(self, earlier: ScheduledTask, later: ScheduledTask) -> str:
        """One line naming an overlapping pair and whose tasks they are."""
        same = "same pet" if earlier.pet.name == later.pet.name else "different pets"
        return (
            f"{earlier.task.title} for {earlier.pet.name}"
            f" ({earlier.start_time}-{earlier.end_time})"
            f" overlaps {later.task.title} for {later.pet.name}"
            f" ({later.start_time}-{later.end_time}) [{same}]"
        )

    def describe_conflicts(self, schedule: Schedule) -> str:
        """A readable report of the overlaps in a schedule."""
        conflicts = self.find_conflicts(schedule)
        if not conflicts:
            return "No conflicts: every task has the day to itself."

        lines = [f"{len(conflicts)} conflict(s):"]
        lines.extend(f"  {self._describe_pair(a, b)}" for a, b in conflicts)
        return "\n".join(lines)

    def upcoming_tasks(self, owner: Owner, after: date | None = None) -> list[tuple[Pet, Task]]:
        """The (pet, task) pairs queued for a later day, soonest first.

        The mirror image of Owner.pending_tasks: that returns what is due now,
        this returns what is waiting. Mostly these are instances created when a
        recurring task was completed, which is why they are sorted by due date
        rather than by priority - the question being answered is "what is coming
        up", not "what should I do first".

        Args:
            owner: Whose tasks to look through.
            after: Tasks due strictly later than this day qualify; defaults to
                today.
        """
        day = after or date.today()
        later = [
            (pet, task)
            for pet, task in owner.all_tasks()
            if not task.is_completed and task.due_date > day
        ]
        return sorted(later, key=lambda pet_task: pet_task[1].due_date)
