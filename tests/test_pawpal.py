"""Tests for the PawPal+ logic layer.

Every test that touches dates passes them explicitly, so results never depend on
the day the suite happens to run.
"""

from datetime import date

import pytest

from pawpal_system import (
    Owner,
    Pet,
    Priority,
    Schedule,
    ScheduledTask,
    Scheduler,
    Task,
    parse_time,
)

DAY = date(2026, 10, 7)


def make_owner(*pets: Pet, available_minutes: int = 120) -> Owner:
    """An owner with the given pets, a day starting at 08:00, and a time budget."""
    owner = Owner("Jordan", available_minutes=available_minutes)
    for pet in pets:
        owner.add_pet(pet)
    return owner


def titles(pet_tasks: list[tuple[Pet, Task]]) -> list[str]:
    """Just the task titles, in order, for readable assertions."""
    return [task.title for _, task in pet_tasks]


# --- Basics ---------------------------------------------------------------


def test_mark_complete_changes_task_status():
    """Task completion: mark_complete() flips is_completed."""
    task = Task("Morning walk", 30, Priority.HIGH)
    assert task.is_completed is False  # a new task starts outstanding

    task.mark_complete()

    assert task.is_completed is True


def test_add_task_increases_pet_task_count():
    """Task addition: add_task() grows the pet's task list."""
    pet = Pet("Mochi", "dog")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Morning walk", 30, Priority.HIGH))
    assert len(pet.tasks) == 1

    pet.add_task(Task("Feeding", 10, Priority.HIGH))
    assert len(pet.tasks) == 2


# --- Sorting --------------------------------------------------------------


def test_sort_orders_by_priority_high_to_low():
    pet = Pet("Mochi", "dog")
    pairs = [
        (pet, Task("Brush", 10, Priority.LOW)),
        (pet, Task("Walk", 10, Priority.HIGH)),
        (pet, Task("Play", 10, Priority.MEDIUM)),
    ]

    assert titles(Scheduler().sort_tasks(pairs)) == ["Walk", "Play", "Brush"]


def test_sort_breaks_priority_ties_shortest_first():
    pet = Pet("Mochi", "dog")
    pairs = [
        (pet, Task("Long walk", 45, Priority.HIGH)),
        (pet, Task("Meds", 5, Priority.HIGH)),
        (pet, Task("Feeding", 15, Priority.HIGH)),
    ]

    assert titles(Scheduler().sort_tasks(pairs)) == ["Meds", "Feeding", "Long walk"]


def test_sort_is_stable_for_full_ties():
    """Tasks equal on priority and duration keep the order they were entered in."""
    pet = Pet("Mochi", "dog")
    pairs = [(pet, Task(name, 10, Priority.MEDIUM)) for name in ["A", "B", "C"]]

    assert titles(Scheduler().sort_tasks(pairs)) == ["A", "B", "C"]


def test_sort_does_not_mutate_input():
    pet = Pet("Mochi", "dog")
    pairs = [
        (pet, Task("Brush", 10, Priority.LOW)),
        (pet, Task("Walk", 10, Priority.HIGH)),
    ]
    original = list(pairs)

    Scheduler().sort_tasks(pairs)

    assert pairs == original


def test_sort_handles_empty_list():
    assert Scheduler().sort_tasks([]) == []


def test_plan_places_flexible_tasks_back_to_back_in_sorted_order():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Brush", 10, Priority.LOW, due_date=DAY))
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=DAY))
    owner = make_owner(pet)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert [(e.task.title, e.start_time) for e in plan.entries] == [
        ("Walk", "08:00"),
        ("Brush", "08:30"),
    ]


def test_plan_fits_task_using_exactly_the_budget():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 60, Priority.HIGH, due_date=DAY))
    owner = make_owner(pet, available_minutes=60)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert len(plan.entries) == 1
    assert plan.skipped == []


def test_plan_skips_task_over_budget_but_keeps_going():
    """A task that does not fit is skipped, and a shorter one after it still gets in."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=DAY))
    pet.add_task(Task("Grooming", 45, Priority.MEDIUM, due_date=DAY))
    pet.add_task(Task("Brush", 10, Priority.LOW, due_date=DAY))
    owner = make_owner(pet, available_minutes=60)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert [e.task.title for e in plan.entries] == ["Walk", "Brush"]
    assert titles(plan.skipped) == ["Grooming"]


def test_plan_with_no_tasks_is_empty():
    owner = make_owner(Pet("Mochi", "dog"))

    plan = Scheduler().build_plan(owner, on=DAY)

    assert plan.entries == []
    assert plan.summary() == "No tasks to plan."


# --- Recurrence -----------------------------------------------------------


def test_completing_daily_task_queues_next_day():
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH, frequency="daily", due_date=DAY)
    pet.add_task(walk)

    successor = pet.complete_task(walk, completed_on=DAY)

    assert walk.is_completed is True
    assert successor is not None
    assert successor.due_date == date(2026, 10, 8)
    assert successor.is_completed is False
    assert successor in pet.tasks
    assert len(pet.tasks) == 2


def test_completing_weekly_task_queues_seven_days_later():
    pet = Pet("Mochi", "dog")
    bath = Task("Bath", 20, Priority.MEDIUM, frequency="weekly", due_date=DAY)
    pet.add_task(bath)

    successor = pet.complete_task(bath, completed_on=DAY)

    assert successor.due_date == date(2026, 10, 14)


def test_weekly_recurrence_rolls_over_year_end():
    task = Task("Bath", 20, Priority.MEDIUM, frequency="weekly")

    successor = task.next_occurrence(completed_on=date(2026, 12, 28))

    assert successor.due_date == date(2027, 1, 4)


def test_successor_copies_task_details():
    task = Task(
        "Meds", 5, Priority.HIGH, frequency="daily", due_date=DAY, required_start=9 * 60
    )

    successor = task.next_occurrence(completed_on=DAY)

    assert successor.title == "Meds"
    assert successor.duration_minutes == 5
    assert successor.priority == Priority.HIGH
    assert successor.frequency == "daily"
    assert successor.required_start == 9 * 60
    assert successor.successor is None


def test_completing_one_off_task_queues_nothing():
    pet = Pet("Mochi", "dog")
    vet = Task("Vet visit", 60, Priority.HIGH, due_date=DAY)
    pet.add_task(vet)

    assert pet.complete_task(vet, completed_on=DAY) is None
    assert len(pet.tasks) == 1


def test_late_completion_counts_from_completion_day():
    """An overdue daily task finished today comes back tomorrow, not today."""
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH, frequency="daily", due_date=date(2026, 10, 5))
    pet.add_task(walk)

    successor = pet.complete_task(walk, completed_on=DAY)

    assert successor.due_date == date(2026, 10, 8)


def test_successor_stays_out_of_todays_plan_but_is_upcoming():
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH, frequency="daily", due_date=DAY)
    pet.add_task(walk)
    owner = make_owner(pet)

    pet.complete_task(walk, completed_on=DAY)

    assert Scheduler().build_plan(owner, on=DAY).entries == []
    assert titles(Scheduler().upcoming_tasks(owner, after=DAY)) == ["Walk"]


def test_overdue_task_carries_into_today():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=date(2026, 10, 6)))
    owner = make_owner(pet)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert [e.task.title for e in plan.entries] == ["Walk"]


def test_future_task_left_out_of_today():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=date(2026, 10, 8)))
    owner = make_owner(pet)

    assert Scheduler().build_plan(owner, on=DAY).entries == []


def test_uncomplete_removes_exactly_the_queued_successor():
    """The successor equals the original as a dataclass, so removal must go by identity."""
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH, frequency="daily", due_date=DAY)
    pet.add_task(walk)
    successor = pet.complete_task(walk, completed_on=DAY)

    pet.uncomplete_task(walk)

    assert walk.is_completed is False
    assert walk.successor is None
    assert len(pet.tasks) == 1
    assert pet.tasks[0] is walk
    assert all(task is not successor for task in pet.tasks)


def test_uncomplete_one_off_task_just_reopens_it():
    pet = Pet("Mochi", "dog")
    vet = Task("Vet visit", 60, Priority.HIGH, due_date=DAY)
    pet.add_task(vet)
    pet.complete_task(vet, completed_on=DAY)

    pet.uncomplete_task(vet)

    assert vet.is_completed is False
    assert pet.tasks == [vet]


def test_completing_twice_does_not_duplicate_successor():
    pet = Pet("Mochi", "dog")
    walk = Task("Walk", 30, Priority.HIGH, frequency="daily", due_date=DAY)
    pet.add_task(walk)

    first = pet.complete_task(walk, completed_on=DAY)
    second = pet.complete_task(walk, completed_on=DAY)

    assert second is first
    assert len(pet.tasks) == 2


# --- Conflict detection ---------------------------------------------------


def placed(pet: Pet, title: str, start: str, duration: int) -> ScheduledTask:
    """A ScheduledTask built straight from a clock time, bypassing the planner."""
    return ScheduledTask(pet, Task(title, duration, Priority.MEDIUM), parse_time(start))


def test_overlapping_entries_are_a_conflict():
    pet = Pet("Mochi", "dog")
    schedule = Schedule(
        entries=[placed(pet, "Walk", "08:00", 30), placed(pet, "Feed", "08:15", 10)]
    )

    conflicts = Scheduler().find_conflicts(schedule)

    assert len(conflicts) == 1
    earlier, later = conflicts[0]
    assert (earlier.task.title, later.task.title) == ("Walk", "Feed")


def test_back_to_back_entries_do_not_conflict():
    """Intervals are half-open: ending at 08:30 and starting at 08:30 is fine."""
    pet = Pet("Mochi", "dog")
    schedule = Schedule(
        entries=[placed(pet, "Walk", "08:00", 30), placed(pet, "Feed", "08:30", 10)]
    )

    assert Scheduler().find_conflicts(schedule) == []


def test_overlap_is_symmetric():
    pet = Pet("Mochi", "dog")
    a = placed(pet, "Walk", "08:00", 30)
    b = placed(pet, "Feed", "08:15", 10)

    assert a.overlaps(b) and b.overlaps(a)


def test_conflicts_reported_once_in_clock_order():
    """Three mutually overlapping entries give three pairs, earliest first."""
    pet = Pet("Mochi", "dog")
    schedule = Schedule(
        entries=[
            placed(pet, "C", "08:20", 30),
            placed(pet, "A", "08:00", 60),
            placed(pet, "B", "08:10", 30),
        ]
    )

    pairs = [(a.task.title, b.task.title) for a, b in Scheduler().find_conflicts(schedule)]

    assert pairs == [("A", "B"), ("A", "C"), ("B", "C")]


def test_same_time_pinned_tasks_kept_with_warning():
    mochi = Pet("Mochi", "dog")
    luna = Pet("Luna", "cat")
    mochi.add_task(Task("Vet", 30, Priority.HIGH, due_date=DAY, required_start=parse_time("10:00")))
    luna.add_task(Task("Groomer", 30, Priority.HIGH, due_date=DAY, required_start=parse_time("10:00")))
    owner = make_owner(mochi, luna)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert len(plan.entries) == 2
    assert len(plan.warnings) == 1
    assert "different pets" in plan.warnings[0]


def test_flexible_task_routes_around_consecutive_pinned_tasks():
    """A flexible task blocked by one pinned task, then another, ends up after both."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Meds", 15, Priority.HIGH, due_date=DAY, required_start=parse_time("08:10")))
    pet.add_task(Task("Feed", 15, Priority.HIGH, due_date=DAY, required_start=parse_time("08:25")))
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=DAY))
    owner = make_owner(pet)

    plan = Scheduler().build_plan(owner, on=DAY)

    walk = next(e for e in plan.entries if e.task.title == "Walk")
    assert walk.start_time == "08:40"
    assert plan.warnings == []
    assert Scheduler().find_conflicts(plan) == []


def test_clean_plan_reports_no_conflicts():
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, Priority.HIGH, due_date=DAY))
    pet.add_task(Task("Feed", 10, Priority.HIGH, due_date=DAY))
    owner = make_owner(pet)

    plan = Scheduler().build_plan(owner, on=DAY)

    assert Scheduler().describe_conflicts(plan).startswith("No conflicts")


# --- Time parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [("00:00", 0), ("09:05", 545), ("23:59", 1439), (" 09:00 ", 540)],
)
def test_parse_time_valid(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["24:00", "08:60", "08:99", "", "abc", "9", None, "-1:30"])
def test_parse_time_invalid_returns_none(text):
    assert parse_time(text) is None
