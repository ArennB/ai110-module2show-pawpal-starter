"""Tests for the PawPal+ logic layer."""

from pawpal_system import Pet, Priority, Task


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
