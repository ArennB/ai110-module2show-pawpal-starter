"""PawPal+ command line demo.

Builds a small household by hand and prints today's schedule, so the scheduling
logic in pawpal_system.py can be seen working without starting Streamlit.

Run it with:
    python main.py
"""

from pawpal_system import Owner, Pet, Priority, Scheduler, Task, format_time


def build_household() -> Owner:
    """Create one owner with two pets and a handful of tasks of varying length."""
    owner = Owner("Jordan", available_minutes=75, day_start_minutes=8 * 60)

    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, Priority.HIGH, frequency="daily"))
    mochi.add_task(Task("Feeding", 10, Priority.HIGH, frequency="daily"))

    luna = Pet("Luna", "cat")
    luna.add_task(Task("Feeding", 10, Priority.HIGH, frequency="daily"))
    luna.add_task(Task("Playtime", 15, Priority.MEDIUM, frequency="daily"))
    luna.add_task(Task("Brush fur", 20, Priority.LOW, frequency="weekly"))

    owner.add_pet(mochi)
    owner.add_pet(luna)
    return owner


def main() -> None:
    owner = build_household()
    schedule = Scheduler().build_plan(owner)

    pets = ", ".join(f"{pet.name} ({pet.animal_type})" for pet in owner.pets)
    requested = sum(task.duration_minutes for _, task in owner.all_tasks())

    print("=" * 64)
    print("Today's Schedule")
    print("=" * 64)
    print(f"Owner: {owner.name}")
    print(f"Pets:  {pets}")
    print(
        f"Time:  {owner.available_minutes} min available"
        f" from {format_time(owner.day_start_minutes)}"
        f" ({requested} min of care requested)"
    )
    print("-" * 64)
    print(schedule.summary())
    print("=" * 64)


if __name__ == "__main__":
    main()
