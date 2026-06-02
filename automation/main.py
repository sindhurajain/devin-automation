import asyncio
import logging
from datetime import datetime
from typing import Any, List

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func

from automation.config import settings
from automation.db import SessionLocal, init_db
from automation.devin import cancel_devin_session, create_devin_session, wait_for_session_completion
from automation.github import comment_on_issue, verify_github_signature
from automation.models import Task, TaskStatus
from automation.schemas import TaskRead

app = FastAPI(title="Devin Automation Service")

logger = logging.getLogger("automation")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
file_handler = logging.FileHandler(settings.log_file)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def get_db_session():
    return SessionLocal()


def queue_task(issue_number: int, issue_title: str, issue_body: str, issue_url: str, issue_repo: str) -> Task:
    with get_db_session() as db:
        existing = (
            db.query(Task)
            .filter(Task.issue_number == issue_number, Task.issue_repo == issue_repo)
            .order_by(Task.created_at.desc())
            .first()
        )
        if existing and existing.status != TaskStatus.failed.value:
            logger.info("Skipping duplicate task for issue #%s", issue_number)
            return existing

        task = Task(
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            issue_url=issue_url,
            issue_repo=issue_repo,
            status=TaskStatus.queued.value,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info("Queued task %s for issue #%s", task.id, issue_number)
        return task


def update_task_status(task_id: int, **kwargs) -> None:
    with get_db_session() as db:
        db_task = db.query(Task).filter(Task.id == task_id).one_or_none()
        if not db_task:
            return
        for key, value in kwargs.items():
            setattr(db_task, key, value)
        db.commit()


def cancel_issue_tasks(issue_number: int, issue_repo: str) -> int:
    with get_db_session() as db:
        tasks = (
            db.query(Task)
            .filter(
                Task.issue_number == issue_number,
                Task.issue_repo == issue_repo,
                Task.status.in_([TaskStatus.queued.value, TaskStatus.running.value]),
            )
            .all()
        )
        for task in tasks:
            if task.devin_session_id and task.status == TaskStatus.running.value:
                try:
                    cancel_devin_session(task.devin_session_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to cancel remote Devin session %s for task %s: %s",
                        task.devin_session_id,
                        task.id,
                        exc,
                    )
            task.status = TaskStatus.cancelled.value
            task.error_message = "Issue closed before completion"
            task.finished_at = datetime.utcnow()
        db.commit()
        return len(tasks)


def prepare_task_for_processing(task_id: int) -> Task | None:
    with get_db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).one_or_none()
        if not task:
            logger.error("Task %s not found for processing", task_id)
            return None

        if task.status == TaskStatus.queued.value:
            task.status = TaskStatus.running.value
            task.started_at = datetime.utcnow()
            db.commit()
            db.refresh(task)
            return task

        if task.status == TaskStatus.running.value:
            if not task.devin_session_id:
                logger.warning(
                    "Task %s is running without a Devin session ID; restarting task.",
                    task.id,
                )
                task.status = TaskStatus.queued.value
                db.commit()
                return None
            return task

        logger.info("Task %s already in status %s", task.id, task.status)
        return None


def ensure_devin_session(task: Task) -> tuple[str, str]:
    if task.devin_session_id:
        logger.info("Resuming existing Devin session %s for task %s", task.devin_session_id, task.id)
        return task.devin_session_id, task.devin_session_url or ""

    try:
        comment_on_issue(task.issue_number, f"Devin has started working on this issue. Task ID: {task.id}")
    except Exception as exc:
        logger.warning("Failed to post start comment for issue #%s: %s", task.issue_number, exc)

    session_response = create_devin_session(
        issue_number=task.issue_number,
        issue_title=task.issue_title,
        issue_body=task.issue_body or "",
        repo_url=f"https://github.com/{task.issue_repo}",
    )
    session_id = session_response.get("session_id")
    session_url = session_response.get("url")
    update_task_status(task.id, devin_session_id=session_id, devin_session_url=session_url)
    logger.info("Created Devin session %s for task %s", session_id, task.id)
    return session_id, session_url


def finalize_task(task_id: int, issue_number: int, final_session: dict[str, Any]) -> None:
    pr_url = None
    pulls = final_session.get("pull_requests", []) or []
    if pulls:
        pr_url = pulls[0].get("pr_url")

    status = final_session.get("status")
    status_detail = final_session.get("status_detail")
    has_open_pr = any(
        pull.get("pr_state") == "open" and pull.get("pr_url")
        for pull in pulls
    )

    if status == "exit" or status_detail == "finished" or has_open_pr:
        update_task_status(
            task_id,
            status=TaskStatus.success.value,
            pr_url=pr_url,
            finished_at=datetime.utcnow(),
        )
        logger.info("Task %s completed successfully, PR=%s", task_id, pr_url)
        comment_text = (
            f"Devin completed the fix for issue #{issue_number}."
            f" PR: {pr_url}" if pr_url else " Fix completed."
        )
        comment_on_issue(issue_number, comment_text)
        return

    error_message = final_session.get("error_message") or status_detail or "Unknown Devin error"
    update_task_status(
        task_id,
        status=TaskStatus.failed.value,
        error_message=error_message,
        finished_at=datetime.utcnow(),
    )
    logger.error("Task %s failed in session %s: %s", task_id, final_session.get("session_id"), error_message)
    comment_on_issue(
        issue_number,
        f"Devin failed to complete this task: {error_message}. See session {final_session.get('session_id')}",
    )


def fail_task(task_id: int, issue_number: int, exc: Exception) -> None:
    update_task_status(
        task_id,
        status=TaskStatus.failed.value,
        error_message=str(exc),
        finished_at=datetime.utcnow(),
    )
    logger.exception("Task %s execution failed", task_id)
    try:
        comment_on_issue(
            issue_number,
            f"Devin automation encountered an error while processing this issue: {exc}",
        )
    except Exception:
        logger.exception("Unable to comment failure for issue #%s", issue_number)


def process_task_sync(task_id: int) -> None:
    task = prepare_task_for_processing(task_id)
    if not task:
        return

    logger.info("Starting Devin remediation for issue #%s", task.issue_number)
    try:
        session_id, session_url = ensure_devin_session(task)
        final_session, timed_out = wait_for_session_completion(session_id)
        if timed_out and final_session.get("status") not in {"exit", "error"}:
            logger.warning(
                "Devin session %s did not reach a terminal state in the polling window. Keeping task %s in running state for later recovery.",
                session_id,
                task.id,
            )
            return

        finalize_task(task.id, task.issue_number, final_session)
    except Exception as exc:
        fail_task(task.id, task.issue_number, exc)


async def process_task(task_id: int) -> None:
    await asyncio.to_thread(process_task_sync, task_id)


@app.on_event("startup")
async def startup_event() -> None:
    init_db()
    logger.info("Automation service starting")
    with get_db_session() as db:
        recover_tasks = db.query(Task).filter(Task.status.in_([TaskStatus.queued.value, TaskStatus.running.value])).all()
    for task in recover_tasks:
        logger.info("Recovering task %s on startup with status %s", task.id, task.status)
        asyncio.create_task(process_task(task.id))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
) -> JSONResponse:
    body = await request.body()
    if not verify_github_signature(settings.github_webhook_secret, x_hub_signature_256 or "", body):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event = x_github_event or ""
    if event != "issues":
        return JSONResponse({"detail": "Event ignored"}, status_code=202)

    issue = payload.get("issue") or {}
    repo = payload.get("repository") or {}
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")
    issue_url = issue.get("html_url", "")
    issue_repo = repo.get("full_name", settings.github_repo)
    action = payload.get("action")
    issue_state = issue.get("state")
    labels = [label.get("name", "") for label in issue.get("labels", [])]

    logger.info(
        "Received GitHub issue event %s for issue #%s state=%s labels=%s",
        action,
        issue_number,
        issue_state,
        labels,
    )

    if issue_state == "closed":
        cancelled = cancel_issue_tasks(issue_number, issue_repo)
        detail = "Issue is closed."
        if cancelled:
            detail = "Issue is closed and pending Devin task was cancelled."
        return JSONResponse({"detail": detail}, status_code=202)

    if "devin-fix" not in labels:
        return JSONResponse({"detail": "Issue does not have devin-fix label"}, status_code=202)

    task = queue_task(issue_number, issue_title, issue_body, issue_url, issue_repo)
    if task.status == TaskStatus.queued.value:
        background_tasks.add_task(process_task, task.id)
        try:
            comment_on_issue(issue_number, f"Devin automation queued this task and will begin processing shortly.")
        except Exception as exc:
            logger.warning("Unable to comment queue status for issue #%s: %s", issue_number, exc)
    else:
        logger.info("Task for issue #%s already exists with status %s", issue_number, task.status)

    return JSONResponse({"task_id": task.id, "status": task.status})


@app.get("/tasks", response_model=List[TaskRead])
async def list_tasks() -> List[TaskRead]:
    with get_db_session() as db:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
        return tasks


@app.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: int) -> TaskRead:
    with get_db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task


@app.get("/metrics")
async def metrics() -> dict[str, float | int]:
    with get_db_session() as db:
        total_issues = db.query(func.count(Task.id)).scalar() or 0
        active_sessions = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.running.value).scalar() or 0
        completed_success = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.success.value).scalar() or 0
        completed_failed = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.failed.value).scalar() or 0
        average_time = 0.0
        duration_query = (
            db.query(func.avg(func.extract('epoch', Task.finished_at - Task.started_at)))
            .filter(Task.status == TaskStatus.success.value, Task.started_at.isnot(None), Task.finished_at.isnot(None))
        )
        avg_seconds = duration_query.scalar() or 0.0
        if avg_seconds:
            average_time = float(avg_seconds)
        success_rate = float(completed_success) / float(total_issues) * 100.0 if total_issues else 0.0

    return {
        "total_issues_received": total_issues,
        "active_sessions": active_sessions,
        "completed_success": completed_success,
        "completed_failed": completed_failed,
        "success_rate": round(success_rate, 2),
        "avg_completion_time_seconds": round(average_time, 2),
    }


@app.get("/status")
async def status() -> dict[str, object]:
    metrics_data = await metrics()
    with get_db_session() as db:
        recent = (
            db.query(Task)
            .order_by(Task.created_at.desc())
            .limit(5)
            .all()
        )
    return {
        "metrics": metrics_data,
        "recent_tasks": [
            {
                "id": task.id,
                "issue_number": task.issue_number,
                "status": task.status,
                "pr_url": task.pr_url,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
            }
            for task in recent
        ],
    }
