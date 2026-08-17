import os
from datetime import datetime,timezone
import boto3
TABLE_NAME=os.getenv("DYNAMODB_TABLE","DeadlineTasks"); FROM_EMAIL=os.environ["SES_FROM_EMAIL"]
table=boto3.resource("dynamodb").Table(TABLE_NAME); ses=boto3.client("ses")
def lambda_handler(event,context):
    sent=0; result=table.scan(FilterExpression="item_type=:t AND reminder_enabled=:yes AND reminder_sent=:no AND #s<>:done",ExpressionAttributeNames={"#s":"status"},ExpressionAttributeValues={":t":"task",":yes":True,":no":False,":done":"Completed"})
    for task in result.get("Items",[]):
        try:
            deadline=datetime.fromisoformat(task["deadline"]); deadline=deadline.replace(tzinfo=timezone.utc) if deadline.tzinfo is None else deadline; hours=(deadline-datetime.now(timezone.utc)).total_seconds()/3600
            if not 0<=hours<=float(task.get("reminder_hours",24)): continue
            p=table.get_item(Key={"task_id":f"USER#{task['owner_id']}"}).get("Item",{})
            if not p.get("notifications_enabled",True): continue
            email=p.get("email") or task.get("owner_email")
            if not email: continue
            ses.send_email(Source=FROM_EMAIL,Destination={"ToAddresses":[email]},Message={"Subject":{"Data":f"DeadlineWise: {task['title']} is due soon"},"Body":{"Text":{"Data":f"{task['title']} ({task['module']}) is due on {task['deadline']}. Progress: {task.get('progress',0)}%."}}})
            table.update_item(Key={"task_id":task["task_id"]},UpdateExpression="SET reminder_sent=:v",ExpressionAttributeValues={":v":True}); sent+=1
        except Exception as e: print(task.get("task_id"),repr(e))
    return {"reminders_sent":sent}
