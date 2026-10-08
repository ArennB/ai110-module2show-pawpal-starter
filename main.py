"""PawPal+ command line demo.

Builds a small household by hand, then shows the scheduling logic in
pawpal_system.py working without starting Streamlit: how tasks get ordered, what
today's plan looks like, and how tasks can be filtered afterwards.

Run it with:
    python main.py
"""

from datetime import date, timedelta

from pawpal_system import (
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
    format_time,
    parse_time,
)


def build_household() -> Owner:
    """Create one owner and two pets, with tasks added deliberately out of order."""
    owner = Owner("Jordan", available_minutes=75, day_start_minutes=8 * 60)

    mochi = Pet("Mochi", "dog")
    luna = Pet("Luna", "cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)

    # Added worst-first on purpose: low priority before high, long before short,
    # and the two pets interleaved. Nothing here is in the order it should run,
    # so the sorting below has visible work to do.
    luna.add_task(Task("Brush fur", 20, Priority.LOW, frequency="weekly"))
    mochi.add_task(Task("Evening walk", 45, Priority.MEDIUM, frequency="daily"))
    luna.add_task(Task("Playtime", 15, Priority.MEDIUM, frequency="daily"))
    mochi.add_task(Task("Morning walk", 30, Priority.HIGH, frequency="daily"))
    luna.add_task(Task("Feeding", 10, Priority.HIGH, frequency="daily"))
    mochi.add_task(Task("Vet paperwork", 5, Priority.LOW, frequency="once"))
    mochi.add_task(Task("Feeding", 10, Priority.HIGH, frequency="daily"))

    # Two fixed-time tasks that both want 09:00. The scheduler honours both and
    # reports the clash rather than dropping one or refusing to plan.
    mochi.add_task(
        Task("Vet appointment", 30, Priority.HIGH, required_start=parse_time("09:00"))
    )
    luna.add_task(
        Task(
            "Medication",
            15,
            Priority.HIGH,
            frequency="daily",
            required_start=parse_time("09:00"),
        )
    )

    return owner


def describe(pet: Pet, task: Task) -> str:
    """One padded line describing a task and the pet it belongs to."""
    done = "x" if task.is_completed else " "
    return (
        f"  [{done}] {task.priority.name.lower():<6}"
        f" {task.title + ' for ' + pet.name:<28}"
        f" {task.duration_minutes:>3} min"
    )


def heading(title: str) -> None:
    """Print a section heading."""
    print()
    print(f"--- {title} " + "-" * max(0, 60 - len(title)))


def verify_conflict_warning() -> bool:
    """Plan a day with deliberate clashes and confirm the scheduler reports them."""
    scheduler = Scheduler()
    mochi = Pet("Mochi", "dog")
    luna = Pet("Luna", "cat")

    # Same pet, overlapping slots: 09:00-09:30 against 09:10-09:30.
    mochi.add_task(
        Task("Vet appointment", 30, Priority.HIGH, required_start=parse_time("09:00"))
    )
    mochi.add_task(
        Task("Grooming", 20, Priority.MEDIUM, required_start=parse_time("09:10"))
    )
    # Different pet, same slot: 09:00-09:15.
    luna.add_task(
        Task("Medication", 15, Priority.HIGH, required_start=parse_time("09:00"))
    )

    owner = Owner("Jordan", pets=[mochi, luna], available_minutes=240)
    plan = scheduler.build_plan(owner)

    checks = [
        ("a plan was still produced", len(plan.entries) == 3),
        ("no task was silently dropped", plan.skipped == []),
        ("warnings were raised", len(plan.warnings) > 0),
        ("same-pet clash detected", any("same pet" in note for note in plan.warnings)),
        (
            "different-pets clash detected",
            any("different pets" in note for note in plan.warnings),
        ),
    ]

    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")

    print()
    for note in plan.warnings:
        print(f"  ! {note}")

    return all(passed for _, passed in checks)


def main() -> None:
    owner = build_household()
    scheduler = Scheduler()

    pets = ", ".join(f"{pet.name} ({pet.animal_type})" for pet in owner.pets)
    requested = sum(task.duration_minutes for _, task in owner.all_tasks())

    print("=" * 64)
    print("PawPal+")
    print("=" * 64)
    print(f"Owner: {owner.name}")
    print(f"Pets:  {pets}")
    print(
        f"Time:  {owner.available_minutes} min available"
        f" from {format_time(owner.day_start_minutes)}"
        f" ({requested} min of care requested)"
    )

    # --- sorting -----------------------------------------------------------
    heading("Tasks as entered")
    for pet, task in owner.all_tasks():
        print(describe(pet, task))

    heading("After Scheduler.sort_tasks()")
    for pet, task in scheduler.sort_tasks(owner.all_tasks()):
        print(describe(pet, task))
    print("  (highest priority first, shortest first on ties)")

    # --- the plan ----------------------------------------------------------
    heading("Today's Schedule")
    today_plan = scheduler.build_plan(owner)
    print(today_plan.summary())

    heading("Conflict check")
    for line in scheduler.describe_conflicts(today_plan).splitlines():
        print("  " + line)
    print("  Both were kept: a clash between fixed times is the owner's to resolve.")

    # --- filtering ---------------------------------------------------------
    heading("Filtering with Owner.filter_tasks()")
    # Completed through the Pet, which also queues each recurring task's next
    # instance. Two daily tasks and one one-off, so both behaviours show up.
    mochi = owner.pets[0]
    for _, task in owner.filter_tasks(pet_name="Mochi"):
        if task.title in ("Morning walk", "Feeding", "Vet paperwork"):
            follow_on = mochi.complete_task(task)
            queued = f"next due {follow_on.due_date}" if follow_on else "does not repeat"
            print(f"  completed {task.title:<14} ({task.frequency:<6}) -> {queued}")
    print()

    views = [
        ("every task", owner.filter_tasks()),
        ("Mochi only", owner.filter_tasks(pet_name="Mochi")),
        ("Luna only", owner.filter_tasks(pet_name="Luna")),
        ("still outstanding", owner.filter_tasks(is_completed=False)),
        ("already completed", owner.filter_tasks(is_completed=True)),
        ("Mochi, outstanding", owner.filter_tasks("Mochi", is_completed=False)),
    ]
    for label, pairs in views:
        titles = ", ".join(f"{task.title} ({pet.name})" for pet, task in pairs)
        print(f"  {label:<20} {len(pairs):>2}  {titles or '-'}")

    # --- recurrence --------------------------------------------------------
    heading("Replanning after completion")
    print(scheduler.build_plan(owner).summary())

    heading("Queued for later")
    for pet, task in scheduler.upcoming_tasks(owner):
        print(f"  {task.due_date}  {task.title} for {pet.name} ({task.frequency})")

    tomorrow = date.today() + timedelta(days=1)
    heading(f"Tomorrow's plan ({tomorrow})")
    print(scheduler.build_plan(owner, on=tomorrow).summary())
    print("=" * 64)


if __name__ == "__main__":
    main()
