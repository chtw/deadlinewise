# DeadlineWise: Netlify frontend + AWS backend

This replaces the Flask website deployment. Netlify hosts `frontend/`; API
Gateway invokes `aws_backend/api_lambda.py`; the existing `DeadlineTasks` table
and reminder Lambda/SNS/EventBridge continue working.

## AWS API Lambda

1. Lambda → Create function → Python 3.13 → `DeadlineWiseTaskAPI`.
2. Paste `aws_backend/api_lambda.py` into `lambda_function.py`, then Deploy.
3. Add environment variable `DYNAMODB_TABLE=DeadlineTasks`.
4. Add the permissions in `api-lambda-policy.json` to its execution role after
   replacing `YOUR_ACCOUNT_ID`.

## API Gateway

1. API Gateway → Create API → HTTP API → Build.
2. Integration: Lambda → `DeadlineWiseTaskAPI`.
3. Add route `$default` pointing to the Lambda integration, or add routes:
   `GET /tasks`, `POST /tasks`, `PUT /tasks/{task_id}`,
   `DELETE /tasks/{task_id}`, `POST /tasks/{task_id}/complete`, `GET /health`.
4. Enable CORS: origin `*` initially; methods GET, POST, PUT, DELETE, OPTIONS;
   header `Content-Type`.
5. Deploy and copy the Invoke URL.

## Connect the frontend

Open `frontend/config.js` and replace:

```text
PASTE_YOUR_API_GATEWAY_URL_HERE
```

with the Invoke URL, without a trailing slash. Commit and push.

## Netlify

1. Netlify → Add new project → Import an existing project → GitHub.
2. Select the repository containing this project.
3. Publish directory: `frontend`.
4. Deploy. Netlify provides the public HTTPS URL.
5. After deployment, set the API Lambda environment variable
   `ALLOWED_ORIGIN` to the Netlify URL and update API Gateway CORS from `*` to
   that URL.

Never put AWS access keys in `config.js` or any frontend file.
