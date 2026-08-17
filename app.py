import os
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError
from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-for-production")

REGION = os.getenv("AWS_REGION", "ap-southeast-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE", "DeadlineTasks")
SGT = ZoneInfo("Asia/Singapore")
table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def scan_all():
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return items


def deadline_datetime(text):
    return datetime.fromisoformat(text).replace(tzinfo=SGT)


def task_analysis(task):
    now = datetime.now(SGT)
    deadline = deadline_datetime(task["deadline"])
    seconds = (deadline - now).total_seconds()
    progress = int(task.get("progress", 0))
    weight = int(task.get("grade_weight", 0))
    difficulty = task.get("difficulty", "Medium")
    completed = task.get("status") == "Completed"

    if completed:
        urgency, css, countdown, urgency_points = "Completed", "completed-status", "Completed", 0
    elif seconds < 0:
        overdue_hours = max(1, int(abs(seconds) // 3600))
        if overdue_hours >= 24:
            days = overdue_hours // 24
            countdown = f"Overdue by {days} day{'s' if days != 1 else ''}"
        else:
            countdown = f"Overdue by {overdue_hours} hour{'s' if overdue_hours != 1 else ''}"
        urgency, css, urgency_points = "Overdue", "overdue", 50
    elif seconds <= 3600:
        minutes = max(1, int(seconds // 60))
        countdown = f"Due in {minutes} minute{'s' if minutes != 1 else ''}"
        urgency, css, urgency_points = "Due soon", "due-soon", 40
    elif seconds <= 86400:
        hours = int(seconds // 3600)
        countdown = f"Due in {hours} hour{'s' if hours != 1 else ''}"
        urgency, css, urgency_points = "Due soon", "due-soon", 40
    else:
        days = int(seconds // 86400)
        countdown = "Due tomorrow" if days == 1 else f"Due in {days} days"
        if seconds <= 3 * 86400:
            urgency, css, urgency_points = "Urgent", "urgent", 30
        elif seconds <= 7 * 86400:
            urgency, css, urgency_points = "Approaching", "approaching", 20
        else:
            urgency, css, urgency_points = "Upcoming", "upcoming", 10

    remaining = 100 - progress
    score = round(urgency_points + remaining * 0.2 + weight * 0.2 + {"Easy": 5, "Medium": 10, "Hard": 15}.get(difficulty, 10), 1)
    reasons = []
    if not completed:
        if seconds < 0: reasons.append("The deadline has passed")
        elif seconds <= 86400: reasons.append("The deadline is within 24 hours")
        elif seconds <= 3 * 86400: reasons.append("The deadline is within 3 days")
        elif seconds <= 7 * 86400: reasons.append("The deadline is within 7 days")
        if remaining >= 40: reasons.append(f"{remaining}% of the work remains")
        if difficulty == "Hard": reasons.append("The task has high difficulty")
        if weight >= 15: reasons.append(f"It contributes {weight}% of the module grade")
        if not reasons: reasons.append("The task is currently manageable")

    return {"countdown": countdown, "urgency": urgency, "urgency_class": css,
            "priority_score": score, "priority_reasons": reasons,
            "seconds_left": seconds}


def read_form():
    progress = max(0, min(100, int(request.form["progress"])))
    return {
        "title": request.form["title"].strip(),
        "module": request.form["module"].strip().upper(),
        "task_type": request.form["task_type"],
        "deadline": request.form["deadline"],
        "estimated_hours": Decimal(request.form["estimated_hours"]),
        "grade_weight": Decimal(request.form["grade_weight"]),
        "difficulty": request.form["difficulty"],
        "progress": Decimal(progress),
        "reminder_hours": Decimal(request.form.get("reminder_hours", "24")),
    }


@app.route("/")
def dashboard():
    tasks = scan_all()
    for task in tasks:
        task.update(task_analysis(task))
    tasks.sort(key=lambda t: (t.get("status") == "Completed", -t["priority_score"]))
    active = [t for t in tasks if t.get("status") != "Completed"]
    due_week = [t for t in active if 0 <= t["seconds_left"] <= 7 * 86400]
    week_hours = sum(float(t.get("estimated_hours", 0)) * (100 - int(t.get("progress", 0))) / 100 for t in due_week)
    workload = "Overloaded" if week_hours > 20 else "Busy" if week_hours > 10 or len(due_week) >= 3 else "Manageable"
    modules = sorted({t["module"] for t in tasks})
    return render_template("dashboard.html", tasks=tasks, modules=modules,
                           focus=active[0] if active else None, due_week=due_week,
                           week_hours=round(week_hours, 1), workload=workload)


@app.route("/tasks/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        item = read_form()
        item.update({"task_id": str(uuid.uuid4()), "status": "Pending",
                     "created_at": datetime.now(SGT).isoformat(timespec="seconds"),
                     "reminder_sent": False})
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(task_id)")
        flash("Task saved to AWS DynamoDB.", "success")
        return redirect(url_for("dashboard"))
    return render_template("task_form.html", task=None)


@app.route("/tasks/<task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = table.get_item(Key={"task_id": task_id}).get("Item")
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        values = read_form()
        values["reminder_sent"] = False
        attribute_names = {f"#field{i}": key for i, key in enumerate(values)}
        attribute_values = {f":value{i}": value for i, value in enumerate(values.values())}
        expression = "SET " + ", ".join(
            f"#field{i}=:value{i}" for i in range(len(values))
        )
        table.update_item(Key={"task_id": task_id}, UpdateExpression=expression,
                          ExpressionAttributeNames=attribute_names,
                          ExpressionAttributeValues=attribute_values)
        flash("Task updated successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("task_form.html", task=task)


@app.post("/tasks/<task_id>/complete")
def complete_task(task_id):
    table.update_item(Key={"task_id": task_id},
        UpdateExpression="SET #s=:s, progress=:p",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "Completed", ":p": Decimal(100)})
    flash("Task marked as completed.", "success")
    return redirect(url_for("dashboard"))


@app.post("/tasks/<task_id>/delete")
def delete_task(task_id):
    table.delete_item(Key={"task_id": task_id})
    flash("Task deleted.", "success")
    return redirect(url_for("dashboard"))


@app.get("/health")
def health():
    try:
        table.load()
        return {"status": "ok", "table": TABLE_NAME, "region": REGION}
    except ClientError as error:
        return {"status": "error", "message": str(error)}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
