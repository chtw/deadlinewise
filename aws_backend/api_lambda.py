import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3

TABLE_NAME = os.getenv("DYNAMODB_TABLE", "DeadlineTasks")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
table = boto3.resource("dynamodb").Table(TABLE_NAME)


def convert(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=convert),
    }


def all_tasks():
    items = []
    result = table.scan()
    items.extend(result.get("Items", []))
    while result.get("LastEvaluatedKey"):
        result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
        items.extend(result.get("Items", []))
    return items


def task_values(data):
    required = ["title", "module", "task_type", "deadline", "difficulty"]
    if any(not data.get(field) for field in required):
        raise ValueError("Please complete all required task fields")
    return {
        "title": str(data["title"]).strip(),
        "module": str(data["module"]).strip().upper(),
        "task_type": data["task_type"],
        "deadline": data["deadline"],
        "estimated_hours": Decimal(str(data.get("estimated_hours", 1))),
        "grade_weight": Decimal(str(data.get("grade_weight", 0))),
        "difficulty": data["difficulty"],
        "progress": Decimal(str(max(0, min(100, int(data.get("progress", 0)))))),
        "reminder_hours": Decimal(str(data.get("reminder_hours", 24))),
    }


def lambda_handler(event, context):
    try:
        request = event.get("requestContext", {}).get("http", {})
        method = request.get("method", event.get("httpMethod", "GET"))
        path = event.get("rawPath", event.get("path", "/"))
        if method == "OPTIONS":
            return response(204, {})
        if method == "GET" and path in ("/health", "/api/health"):
            table.load()
            return response(200, {"status": "ok", "table": TABLE_NAME})
        if method == "GET" and path in ("/tasks", "/api/tasks"):
            return response(200, {"tasks": all_tasks()})

        parts = [part for part in path.split("/") if part and part != "api"]
        data = json.loads(event.get("body") or "{}")
        if method == "POST" and parts == ["tasks"]:
            item = task_values(data)
            item.update({"task_id": str(uuid.uuid4()), "status": "Pending",
                         "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
                         "reminder_sent": False})
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(task_id)")
            return response(201, {"task": item})
        if len(parts) >= 2 and parts[0] == "tasks":
            task_id = parts[1]
            if method == "DELETE":
                table.delete_item(Key={"task_id": task_id})
                return response(200, {"message": "Task deleted"})
            if method == "POST" and len(parts) == 3 and parts[2] == "complete":
                table.update_item(Key={"task_id": task_id}, UpdateExpression="SET #s=:s, progress=:p",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":s": "Completed", ":p": Decimal(100)})
                return response(200, {"message": "Task completed"})
            if method == "PUT":
                values = task_values(data); values["reminder_sent"] = False
                names = {f"#f{i}": key for i, key in enumerate(values)}
                vals = {f":v{i}": value for i, value in enumerate(values.values())}
                expression = "SET " + ", ".join(f"#f{i}=:v{i}" for i in range(len(values)))
                table.update_item(Key={"task_id": task_id}, UpdateExpression=expression,
                                  ExpressionAttributeNames=names, ExpressionAttributeValues=vals)
                return response(200, {"message": "Task updated"})
        return response(404, {"error": "Route not found"})
    except ValueError as error:
        return response(400, {"error": str(error)})
    except Exception as error:
        print(error)
        return response(500, {"error": "Server error. Check Lambda logs."})
