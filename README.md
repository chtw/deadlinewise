# DeadlineWise Complete

For public deployment from GitHub, follow `DEPLOY_TO_APP_RUNNER.md`.

## Features

- DynamoDB CRUD: add, view, edit, complete and delete tasks
- Countdown, overdue handling and colour-coded urgency
- Explainable priority scores
- Focus Next recommendation
- Seven-day workload/clash detection
- Module/type/status filters and sorting
- Reminder preference per task
- SNS reminder Lambda code with duplicate-reminder prevention
- Responsive interface and `/health` AWS connection test

## Run locally

Open this folder in Cursor or VS Code, then run in PowerShell:

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\Activate.ps1
pip install -r requirements.txt
aws configure
python app.py
```

Open http://127.0.0.1:5000 and test http://127.0.0.1:5000/health.

## AWS checklist

### A. DynamoDB (required first)

1. Use region **Asia Pacific (Singapore)** (`ap-southeast-1`).
2. DynamoDB → Tables → Create table.
3. Table: `DeadlineTasks`.
4. Partition key: `task_id`, type String. No sort key.
5. Keep default settings.

The local IAM user needs the actions in `aws-policy-local-app.json`. Replace
`YOUR_ACCOUNT_ID` before using the custom policy. `AmazonDynamoDBFullAccess`
also works for initial testing but is broader than required.

### B. SNS email reminder

1. SNS → Topics → Create topic → Standard.
2. Name: `DeadlineWiseReminders`.
3. Create subscription: Protocol `Email`; Endpoint: your email.
4. Open the confirmation email and confirm the subscription.
5. Copy the topic ARN.

### C. Lambda reminder checker

1. Lambda → Create function → Author from scratch.
2. Name: `DeadlineWiseReminderChecker`; runtime Python 3.13.
3. Paste `reminder_lambda.py` into `lambda_function.py` and deploy.
4. Configuration → Environment variables:
   - `DYNAMODB_TABLE` = `DeadlineTasks`
   - `SNS_TOPIC_ARN` = the copied SNS topic ARN
5. Add the permissions in `aws-policy-reminder-lambda.json` to Lambda's
   execution role, replacing both placeholders.
6. Use a test event `{}`. A task due inside its reminder period should send one
   email and change `reminder_sent` to true in DynamoDB.

### D. EventBridge Scheduler

1. EventBridge Scheduler → Create schedule.
2. Name: `DeadlineWiseHourlyReminder`.
3. Recurring schedule: `rate(1 hour)`; flexible time window Off.
4. Target: AWS Lambda Invoke; select `DeadlineWiseReminderChecker`.
5. Let the console create a new execution role, then create the schedule.

## Demo path

Add task → verify DynamoDB item → show priority/countdown → show workload clash
→ edit progress → trigger Lambda test → receive SNS email → complete task.
