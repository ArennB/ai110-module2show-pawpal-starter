from datetime import date

import streamlit as st

from pawpal_system import Owner, Pet, Priority, Scheduler, Task, format_time, parse_time

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Prefix for the per-task "done" checkbox keys, so a new day can clear them.
DONE_PREFIX = "done_"

# Maps the status selectbox onto filter_tasks' is_completed argument, where None
# means "do not filter on status".
STATUS_FILTERS = {"All": None, "To do": False, "Done": True}

st.title("🐾 PawPal+")
st.caption(
    "Plan a day of pet care around the time you have: highest-priority tasks first,"
    " fixed appointments kept, and clashes flagged."
)

with st.expander("Scenario"):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.
"""
    )

with st.expander("How the scheduler decides"):
    st.markdown(
        """
- Tasks with a fixed start time are placed first, at that time.
- The rest are ordered highest priority first, shortest first on ties, and each
  goes into the first free slot from the start of the day.
- A task that would exceed the time available is skipped, and the next one is tried.
- Two fixed-time tasks that overlap are both kept and flagged as a conflict.
"""
    )


def done_key(task: Task) -> str:
    """Checkbox key for a task, tied to the object rather than its list position.

    Completing a task inserts a new one into the list, which would shift
    positional keys and move tick marks onto the wrong rows.
    """
    return f"{DONE_PREFIX}{id(task)}"


def due_label(task: Task, today: date) -> str:
    """How a task's due date reads in the table: today, overdue, or a future date."""
    if task.due_date == today:
        return "today"
    if task.due_date < today and not task.is_completed:
        return "overdue"
    return str(task.due_date)


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
        st.success(f"Added {pet_name} the {species}.")

if st.session_state.pets:
    st.table(
        [
            {"Name": pet.name, "Species": pet.animal_type, "Tasks": len(pet.tasks)}
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
        when = f" at {format_time(required_start)}" if required_start is not None else ""
        st.success(f"Added '{task_title}' for {target.name}{when}.")

# Rebuilt on every rerun from the current widget values and the stored pets, so
# edits to the owner name or time budget always take effect.
owner = Owner(owner_name, available_minutes=int(available_minutes))
for pet in st.session_state.pets:
    owner.add_pet(pet)

scheduler = Scheduler()
today = date.today()

# Apply last run's checkbox changes before drawing anything, so the table and
# counts below reflect them on this run rather than one click late. Completing
# goes through the Pet, which also queues the next occurrence of a recurring
# task; unticking removes that queued instance again.
completion_notes: list[str] = []
for pet, task in owner.all_tasks():
    ticked = st.session_state.get(done_key(task))
    if ticked is None:
        continue
    if ticked and not task.is_completed:
        follow_on = pet.complete_task(task)
        note = f"Marked '{task.title}' for {pet.name} done."
        if follow_on is not None:
            note += f" Next {task.frequency} instance queued for {follow_on.due_date}."
        completion_notes.append(note)
    elif not ticked and task.is_completed:
        pet.uncomplete_task(task)

if owner.all_tasks():
    for note in completion_notes:
        st.success(note)

    total_count = len(owner.all_tasks())
    done_count = len(owner.filter_tasks(is_completed=True))
    st.progress(done_count / total_count, text=f"{done_count} of {total_count} tasks done")

    overdue = [
        (pet, task)
        for pet, task in owner.filter_tasks(is_completed=False, due_by=today)
        if task.due_date < today
    ]
    if overdue:
        st.warning(
            f"{len(overdue)} overdue task(s) carried over from earlier days: "
            + ", ".join(f"{task.title} ({pet.name})" for pet, task in overdue)
        )

    col_pet_filter, col_status_filter = st.columns(2)
    with col_pet_filter:
        pet_filter = st.selectbox(
            "Show pet", ["All pets"] + [pet.name for pet in st.session_state.pets]
        )
    with col_status_filter:
        status_filter = st.selectbox("Show status", list(STATUS_FILTERS))

    visible = scheduler.sort_tasks(
        owner.filter_tasks(
            pet_name=None if pet_filter == "All pets" else pet_filter,
            is_completed=STATUS_FILTERS[status_filter],
        )
    )

    if not visible:
        st.info("No tasks match these filters.")
    else:
        st.caption(
            f"Showing {len(visible)} of {total_count} task(s), in the order the"
            " scheduler considers them: highest priority first, shortest first on ties."
        )
        st.table(
            [
                {
                    "Task": task.title,
                    "Pet": pet.name,
                    "Minutes": task.duration_minutes,
                    "Priority": task.priority.name.title(),
                    "Repeats": task.frequency,
                    "Time": format_time(task.required_start) if task.is_pinned else "flexible",
                    "Due": due_label(task, today),
                    "Status": "Done" if task.is_completed else "To do",
                }
                for pet, task in visible
            ]
        )

        st.markdown("**Check off tasks**")
        for pet, task in visible:
            st.checkbox(
                f"{task.title} ({pet.name})",
                value=task.is_completed,
                key=done_key(task),
            )

st.divider()

st.subheader("Build Schedule")
st.caption("Plans the outstanding tasks into the time available.")

build_clicked = st.button("Generate schedule", type="primary")

if build_clicked:
    if not owner.all_tasks():
        st.warning("Add at least one pet and one task first.")
    else:
        schedule = scheduler.build_plan(owner)
        conflicts = scheduler.find_conflicts(schedule)

        col_planned, col_skipped, col_clash = st.columns(3)
        col_planned.metric(
            "Planned", f"{schedule.total_minutes} min", f"of {owner.available_minutes} available",
            delta_color="off",
        )
        col_skipped.metric("Skipped", f"{len(schedule.skipped)} task(s)")
        col_clash.metric("Conflicts", len(conflicts))

        if not schedule.entries and not schedule.skipped:
            st.info("Nothing is due today - every task is done or scheduled for later.")
        elif not schedule.skipped:
            st.success(
                f"Everything fits: {len(schedule.entries)} task(s) in"
                f" {schedule.total_minutes} of {owner.available_minutes} minutes."
            )
        else:
            st.warning(
                f"{len(schedule.skipped)} task(s) did not fit in"
                f" {owner.available_minutes} minutes. Free up more time or lower the"
                " priority of something else."
            )

        if schedule.entries:
            st.markdown("**Today's plan**")
            # entries is in placement order (fixed-time tasks first), so sort by
            # start time to read as a timeline.
            st.table(
                [
                    {
                        "Time": f"{entry.start_time}-{entry.end_time}",
                        "Task": entry.task.title,
                        "Pet": entry.pet.name,
                        "Minutes": entry.task.duration_minutes,
                        "Priority": entry.task.priority.name.title(),
                        "Placed": "fixed time" if entry.task.is_pinned else "flexible",
                    }
                    for entry in sorted(schedule.entries, key=lambda e: e.start_minutes)
                ]
            )

        if schedule.skipped:
            st.markdown("**Skipped - not enough time left**")
            st.table(
                [
                    {
                        "Task": task.title,
                        "Pet": pet.name,
                        "Minutes": task.duration_minutes,
                        "Priority": task.priority.name.title(),
                    }
                    for pet, task in scheduler.sort_tasks(schedule.skipped)
                ]
            )

        if conflicts:
            # Only two fixed-time tasks can clash; flexible ones are always
            # routed around them. So the fix is for the owner to move one.
            st.markdown("**Conflicts**")
            for warning in schedule.warnings:
                st.warning(warning)
            st.caption(
                "Both tasks have a fixed start time, so the scheduler kept them and"
                " flagged the overlap. Change one of the times to resolve it."
            )
        elif schedule.entries:
            st.success(scheduler.describe_conflicts(schedule))

upcoming = scheduler.upcoming_tasks(owner)
if upcoming:
    st.divider()
    st.subheader("Queued for later")
    st.caption("Created automatically when a recurring task was completed.")
    st.table(
        [
            {
                "Due": str(task.due_date),
                "Task": task.title,
                "Pet": pet.name,
                "Repeats": task.frequency,
            }
            for pet, task in upcoming
        ]
    )
