# DeadlineWise multi-user AWS edition

Included: Cognito accounts; private per-student DynamoDB tasks; dashboard and explainable priorities; CRUD, progress, filters, notes and group work; separate monthly calendar; account-wide and per-task reminder controls; EventBridge checks; and private SES emails.

## 1. Cognito

1. Go to **Amazon Cognito → User pools → Create user pool**.
2. Use **Email** for sign-in and require `email` and `name`.
3. Create a **public app client without a client secret**.
4. Paste the User pool ID and App client ID into `frontend/config.js`.

## 2. API Gateway JWT authorizer

Create a JWT authorizer on the existing HTTP API:

- Issuer: `https://cognito-idp.ap-southeast-1.amazonaws.com/YOUR_USER_POOL_ID`
- Audience: your Cognito app client ID
- Identity source: `$request.header.Authorization`

Attach it to the `$default` route, or every `/tasks` and `/me` route. Keep `GET /health` public. CORS must allow `Authorization, Content-Type`; methods `GET, POST, PUT, DELETE, OPTIONS`; and your Netlify origin.

## 3. API Lambda

Replace `DeadlineWiseTaskAPI` with `aws_backend/api_lambda.py` and deploy. Keep environment variables `DYNAMODB_TABLE=DeadlineTasks` and `ALLOWED_ORIGIN=https://YOUR-SITE.netlify.app`.

The existing table can remain with String partition key `task_id`. Old tasks lack an owner and intentionally will not appear to signed-in students.

## 4. Private reminders with SES

SNS broadcasts to subscribers, so it is unsuitable for private multi-user reminders. This version uses SES.

1. In **Amazon SES → Verified identities**, verify the sender email.
2. In the SES sandbox, recipient emails must also be verified.
3. Replace the reminder Lambda with `aws_backend/reminder_lambda.py`.
4. Add `DYNAMODB_TABLE=DeadlineTasks` and `SES_FROM_EMAIL=your-verified@email.com`.
5. Attach `aws_backend/reminder-policy.json` after replacing `YOUR_ACCOUNT_ID`.
6. Keep the existing EventBridge schedule connected to the reminder Lambda.

## 5. Publish

Copy these files into the GitHub-connected repository, then run:

```powershell
git add -A
git commit -m "Add calendar accounts and notification settings"
git push
```

Netlify publishes `frontend/`. Test using two accounts: each must see only its own tasks. Also test notification off, per-task reminder off, calendar, CRUD, completion, logout and session expiry.
