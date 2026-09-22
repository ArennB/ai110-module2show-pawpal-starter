"""PawPal+ logic layer.

Backend classes for the pet care planner, converted from diagrams/uml.mmd.
This module holds no Streamlit code so it can be imported and tested on its own.

Structure (see diagrams/uml.mmd):
    Priority       - how important a task is
    Task           - one unit of pet care
    Pet            - an animal and the tasks it needs
    Owner          - the person, their pets, and their scheduling constraints
    ScheduledTask  - one Task placed at a start time, for one Pet
    Schedule       - the finished plan (entries + what got skipped)
    Scheduler      - the algorithm that turns an Owner into a Schedule

All method bodies are stubs. Implement them one at a time (README step 4).
"""

from dataclasses import dataclass, field
from enum import IntEnum


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
    """One pet care task, e.g. a 30 minute high-priority morning walk."""

    title: str
    duration_minutes: int
    priority: Priority
    task_type: str = "general"
    recurrence: str = "once"  # "once", "daily", "weekly"

    def is_due_today(self) -> bool:
        """Whether this task should be considered for today's plan.

        README "Smarter Scheduling" -> Recurring tasks.
        """
        raise NotImplementedError


@dataclass
class Pet:
    """An animal and the tasks it needs."""

    name: str
    animal_type: str
    age: int = 0
    # default_factory gives each Pet its own empty list instead of one shared list.
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet."""
        raise NotImplementedError

    def total_task_minutes(self) -> int:
        """Total duration of every task attached to this pet."""
        raise NotImplementedError


@dataclass
class Owner:
    """The person, their pets, and the constraints on their day.

    The constraint fields (available_minutes, day_start, preferred_types) live here
    for now. If more rules get added, extract them into a Constraints class.
    """

    name: str
    pets: list[Pet] = field(default_factory=list)
    available_minutes: int = 60
    day_start: str = "08:00"
    preferred_types: list[str] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner."""
        raise NotImplementedError


@dataclass
class ScheduledTask:
    """One task placed at a start time, for one pet.

    Keeping the task, its pet, and its start time in a single object means they
    cannot drift out of sync the way parallel lists can.
    """

    task: Task
    pet: Pet
    start_time: str  # "HH:MM"


@dataclass
class Schedule:
    """The finished plan: what got scheduled, and what did not fit."""

    date: str
    entries: list[ScheduledTask] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    total_minutes: int = 0

    def add_entry(self, entry: ScheduledTask) -> None:
        """Append an entry and keep total_minutes in step with it."""
        raise NotImplementedError

    def summary(self) -> str:
        """Human-readable plan explaining what happens when, and what was skipped.

        Target format (see README "Sample Output"):
            08:00 - Morning walk (30 min) [priority: high]
        """
        raise NotImplementedError


class Scheduler:
    """Builds a Schedule from an Owner.

    Deliberately not a dataclass: it holds no state. Everything it needs arrives
    as a parameter, which keeps it testable without any UI.
    """

    def build_plan(self, owner: Owner) -> Schedule:
        """Plan one day across all of the owner's pets.

        Walk a clock forward from owner.day_start, placing tasks in sorted order
        while they fit inside owner.available_minutes. Tasks that do not fit go
        into Schedule.skipped.
        """
        raise NotImplementedError

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order tasks for planning: priority high to low, then shortest first.

        README "Smarter Scheduling" -> Task sorting.
        """
        raise NotImplementedError

    def _fits(self, task: Task, used_minutes: int, budget_minutes: int) -> bool:
        """Whether this task still fits in the remaining time.

        README "Smarter Scheduling" -> Filtering.
        """
        raise NotImplementedError
