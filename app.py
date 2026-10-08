from datetime import date

import streamlit as st

from pawpal_system import Owner, Pet, Priority, Scheduler, Task, format_time, parse_time

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Prefix for the per-task "done" checkbox keys, so a new day can clear them.
DONE_PREFIX = "done_"

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Owner")
owner_name = st.text_input("Owner name", value="Jordan")
available_minutes = st.number_input(
    "Time available today (minutes)", min_value=5, max_value=600, value=60, step=5
)

# Pets accumulate across button clicks, so unlike the widgets above they have to
# live in session_state to survive Streamlit's rerun on every interaction. The
# tasks ride along inside each Pet, which is where the model says they belong.
if "pets" not in st.session_state:
    st.session_state.pets = []

st.markdown("### Pets")
st.caption("Add each animal you care for. Tasks are assigned to a pet below.")

col_name, col_species = st.columns(2)
with col_name:
    pet_name = st.text_input("Pet name", value="Mochi")
with col_species:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    if not pet_name.strip():
        st.warning("Give the pet a name first.")
    elif any(pet.name == pet_name for pet in st.session_state.pets):
        st.warning(f"{pet_name} is already on the list.")
    else:
        st.session_state.pets.append(Pet(pet_name, species))

if st.session_state.pets:
    st.table(
        [
            {"name": pet.name, "species": pet.animal_type, "tasks": len(pet.tasks)}
            for pet in st.session_state.pets
        ]
    )
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")

if not st.session_state.pets:
    st.info("Add a pet before adding tasks.")
else:
    st.caption("Add a few tasks. These feed straight into the scheduler below.")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        task_pet_name = st.selectbox(
            "For pet", [pet.name for pet in st.session_state.pets]
        )
    with col2:
        task_title = st.text_input("Task title", value="Morning walk")
    with col3:
        duration = st.number_input(
            "Duration (minutes)", min_value=1, max_value=240, value=20
        )
    with col4:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    with col5:
        frequency = st.selectbox("Repeats", ["once", "daily", "weekly"], index=1)

    fixed_text = st.text_input(
        "Fixed start time (optional)",
        placeholder="HH:MM, e.g. 09:00 for a vet appointment",
    )

    if st.button("Add task"):
        # Unparseable text degrades to a flexible task with a warning, rather
        # than blocking the add or raising.
        required_start = parse_time(fixed_text) if fixed_text.strip() else None
        if fixed_text.strip() and required_start is None:
            st.warning(f"Could not read '{fixed_text}' as HH:MM - adding it as flexible.")

        target = next(
            pet for pet in st.session_state.pets if pet.name == task_pet_name
        )
        # Priority["HIGH"] turns the selectbox string into the enum the scheduler sorts on.
        target.add_task(
            Task(
                task_title,
                int(duration),
                Priority[priority.upper()],
                frequency=frequency,
                required_start=required_start,
            )
        )

# Rebuilt on every rerun from the current widget values and the stored pets, so
# edits to the owner name or time budget always take effect.
owner = Owner(owner_name, available_minutes=int(available_minutes))
for pet in st.session_state.pets:
    owner.add_pet(pet)

if owner.all_tasks():
    st.write("Current tasks:")
    st.caption(
        "Tick a task to mark it done. Completing a recurring task queues the next one."
    )

    for pet, task in owner.all_tasks():
        repeats = "" if task.frequency == "once" else f", {task.frequency}"
        pinned = f" at {format_time(task.required_start)}" if task.is_pinned else ""
        due = "" if task.due_date <= date.today() else f" due {task.due_date}"
        label = (
            f"{task.title} for {pet.name} ({task.duration_minutes} min)"
            f" [{task.priority.name.lower()}{repeats}]{pinned}{due}"
        )
        # Keyed on the Task's identity, not its position: completing a task
        # inserts a new one into the list, which would shift positional keys and
        # move tick marks onto the wrong rows.
        ticked = st.checkbox(label, value=task.is_completed, key=f"{DONE_PREFIX}{id(task)}")

        # Completing goes through the Pet, which also queues the next occurrence
        # of a recurring task; unticking removes that queued instance again.
        if ticked and not task.is_completed:
            follow_on = pet.complete_task(task)
            if follow_on is not None:
                st.caption(f"    Next {task.frequency} instance due {follow_on.due_date}.")
        elif not ticked and task.is_completed:
            pet.uncomplete_task(task)

    done_count = len(owner.all_tasks()) - len(owner.pending_tasks())
    st.caption(f"{done_count} of {len(owner.all_tasks())} done.")

st.divider()

st.subheader("Build Schedule")
st.caption("Plans the tasks above into the time available, highest priority first.")

scheduler = Scheduler()

build_clicked = st.button("Generate schedule")

if build_clicked:
    if not owner.all_tasks():
        st.warning("Add at least one pet and one task first.")
    else:
        schedule = scheduler.build_plan(owner)

        conflicts = scheduler.find_conflicts(schedule)

        col_planned, col_skipped, col_clash = st.columns(3)
        col_planned.metric("Planned", f"{schedule.total_minutes} min")
        col_skipped.metric("Skipped", f"{len(schedule.skipped)} task(s)")
        col_clash.metric("Conflicts", len(conflicts))

        st.text(schedule.summary())

        if conflicts:
            st.error(scheduler.describe_conflicts(schedule))

upcoming = scheduler.upcoming_tasks(owner)
if upcoming:
    st.divider()
    st.subheader("Queued for later")
    st.caption("Created automatically when a recurring task was completed.")
    st.table(
        [
            {
                "due": str(task.due_date),
                "pet": pet.name,
                "task": task.title,
                "repeats": task.frequency,
            }
            for pet, task in upcoming
        ]
    )
