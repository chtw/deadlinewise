import os
from datetime import datetime, timezone
import boto3
from decimal import Decimal

TABLE=os.getenv("DYNAMODB_TABLE","DeadlineTasks")
TOPIC=os.environ["SNS_TOPIC_ARN"]
table=boto3.resource("dynamodb").Table(TABLE)
sns=boto3.client("sns")

def lambda_handler(event,context):
    tasks=table.scan().get("Items",[]); now=datetime.now(timezone.utc); sent=0
    for task in tasks:
        if task.get("status")=="Completed" or task.get("reminder_sent"): continue
        # Stored datetime-local values represent Singapore time (UTC+8).
        deadline=datetime.fromisoformat(task["deadline"]+"+08:00").astimezone(timezone.utc)
        hours=(deadline-now).total_seconds()/3600
        if 0 <= hours <= int(task.get("reminder_hours",24)):
            sns.publish(TopicArn=TOPIC,Subject="DeadlineWise reminder",Message=f'{task["title"]} ({task["module"]}) is {int(task.get("progress",0))}% complete and due {task["deadline"]} Singapore time.')
            table.update_item(Key={"task_id":task["task_id"]},UpdateExpression="SET reminder_sent=:v",ExpressionAttributeValues={":v":True}); sent+=1
    return {"statusCode":200,"reminders_sent":sent}
