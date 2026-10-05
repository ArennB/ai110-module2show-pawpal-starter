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
from enum import IntEnum


MINUTES_PER_DAY = 24 * 60


def format_time(minutes_since_midnight: int) -> str:
    """Render minutes since midnight as "HH:MM", e.g. 545 -> "09:05".

    Wraps at midnight, so a plan running past 24:00 reads 00:20 rather than 24:20.
    """
    hours, minutes = divmod(minutes_since_midnight % MINUTES_PER_DAY, 60)
    return f"{hours:02d}:{minutes:02d}"


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

    def mark_complete(self) -> None:
        """Mark this task done, so it drops out of today's plan."""
        self.is_completed = True

    def mark_incomplete(self) -> None:
        """Mark this task outstanding again."""
        self.is_completed = False


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
        """Every task across every pet, each paired with the pet it belongs to.

        Pairing keeps the pet attached to its task, so later steps can say which
        animal a line of the plan is about.
        """
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def pending_tasks(self) -> list[tuple[Pet, Task]]:
        """The (pet, task) pairs that are not finished yet."""
        return [(pet, task) for pet, task in self.all_tasks() if not task.is_completed]


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


@dataclass
class Schedule:
    """The finished plan: what got scheduled, and what did not fit.

    Both lists carry the pet as well as the task, so the plan can say which
    animal each line is about.
    """

    entries: list[ScheduledTask] = field(default_factory=list)
    skipped: list[tuple[Pet, Task]] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        """Minutes of care planned. Derived, so it cannot fall out of sync."""
        return sum(entry.task.duration_minutes for entry in self.entries)

    def add_entry(self, entry: ScheduledTask) -> None:
        """Append a placed task to the plan."""
        self.entries.append(entry)

    def summary(self) -> str:
        """Human-readable plan explaining what happens when, and what was skipped.

        Line format follows the README "Sample Output" section:
            08:00 - Morning walk for Mochi (30 min) [priority: high]
        """
        if not self.entries and not self.skipped:
            return "No tasks to plan."

        lines: list[str] = []

        if self.entries:
            lines.append("Daily plan:")
            for entry in self.entries:
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

        return "\n".join(lines)


class Scheduler:
    """The brain: retrieves, organizes, and manages tasks across all of an
    owner's pets.

    Retrieves them via Owner.pending_tasks(), organizes them with _sort_tasks()
    and build_plan(), and manages their completion state across days with
    reset_for_new_day().

    Deliberately not a dataclass: it holds no state. Everything it needs arrives
    as a parameter, which keeps it testable without any UI.
    """

    def build_plan(self, owner: Owner) -> Schedule:
        """Plan one day across all of the owner's pets.

        Retrieves every unfinished (pet, task) pair, sorts them, then walks a
        clock forward from owner.day_start_minutes placing each task while it
        still fits inside owner.available_minutes. Pairs that do not fit go into
        Schedule.skipped. Completed tasks are left out entirely.
        """
        schedule = Schedule()
        pet_tasks = owner.pending_tasks()

        # The clock is the single source of truth for elapsed time: minutes used
        # is always clock - day_start, so there is no second counter to desync.
        clock = owner.day_start_minutes

        for pet, task in self._sort_tasks(pet_tasks):
            used_minutes = clock - owner.day_start_minutes
            if self._fits(task, used_minutes, owner.available_minutes):
                schedule.add_entry(ScheduledTask(pet, task, clock))
                clock += task.duration_minutes
            else:
                # Keep going rather than stopping at the first task that does not
                # fit: a shorter, lower-priority task may still fill the gap.
                schedule.skipped.append((pet, task))

        return schedule

    def _sort_tasks(self, pet_tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Order pairs for planning: priority high to low, then shortest first.

        Takes pairs rather than bare tasks so the pet survives the sort and each
        entry can be turned into a ScheduledTask.

        README "Smarter Scheduling" -> Task sorting.
        """

        def sort_key(pet_task: tuple[Pet, Task]) -> tuple[int, int]:
            _, task = pet_task
            # Negated priority sorts HIGH first; duration then favours short tasks,
            # which fits more care into the same budget.
            return (-task.priority, task.duration_minutes)

        # sorted() is stable, so equal-priority, equal-duration tasks stay in the
        # order the owner entered them.
        return sorted(pet_tasks, key=sort_key)

    def _fits(self, task: Task, used_minutes: int, budget_minutes: int) -> bool:
        """Whether this task still fits in the remaining time.

        README "Smarter Scheduling" -> Filtering.
        """
        return used_minutes + task.duration_minutes <= budget_minutes

    def reset_for_new_day(self, owner: Owner) -> int:
        """Bring recurring tasks back for a new day, and report how many returned.

        A "once" task stays completed forever; anything recurring is marked
        outstanding again so it reappears in tomorrow's plan. This is what makes
        Task.frequency do real work rather than just describe the task.

        README "Smarter Scheduling" -> Recurring tasks.
        """
        revived = 0
        for _, task in owner.all_tasks():
            if task.frequency != "once" and task.is_completed:
                task.mark_incomplete()
                revived += 1
        return revived
