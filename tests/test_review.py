import models


def test_review_lists_draft_tasks_for_manager(client, login_as_user):
    login_as_user("maya@nudge.local")

    response = client.get("/review/")

    assert response.status_code == 200
    assert b"Finalize pricing page copy" in response.data
    assert b"Investigate flaky checkout test" in response.data
    assert b"Create customer rollout notes" not in response.data


def test_approving_a_draft_moves_it_to_pending(client, login_as_user):
    login_as_user("maya@nudge.local")
    task_id = _draft_task_id("Finalize pricing page copy")

    response = client.post(
        f"/review/{task_id}/approve",
        data={
            "owner": "Priya Shah",
            "description": "Finalize pricing page copy for launch",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    assert task["status"] == "pending"
    assert task["description"] == "Finalize pricing page copy for launch"
    assert task["assignee_name"] == "Priya Shah"
    assert task["assignee_id"] is not None


def test_editing_a_draft_keeps_it_in_review_queue(client, login_as_user):
    login_as_user("maya@nudge.local")
    task_id = _draft_task_id("Investigate flaky checkout test")

    response = client.post(
        f"/review/{task_id}/edit",
        data={
            "owner": "",
            "description": "Assign an owner for the flaky checkout test",
            "due_date": "",
            "priority": "normal",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    assert task["status"] == "draft"
    assert task["description"] == "Assign an owner for the flaky checkout test"
    assert task["assignee_name"] == "unassigned"
    assert task["due_date"] is None


def test_rejecting_a_draft_retains_rejected_task(client, login_as_user):
    login_as_user("maya@nudge.local")
    task_id = _draft_task_id("Investigate flaky checkout test")

    response = client.post(f"/review/{task_id}/reject")

    assert response.status_code == 302
    task = _task(task_id)
    assert task is not None
    assert task["status"] == "rejected"


def _draft_task_id(description):
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM tasks WHERE description = ? AND status = 'draft'",
            (description,),
        ).fetchone()
    assert row is not None
    return row["id"]


def _task(task_id):
    with models.get_db() as db:
        return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
