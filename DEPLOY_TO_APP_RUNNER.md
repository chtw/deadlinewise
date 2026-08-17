# Deploy DeadlineWise from GitHub to AWS App Runner

GitHub stores the source code. AWS App Runner runs Flask and supplies the public
HTTPS URL.

## 1. Upload this folder to GitHub

Do not upload `venv`, access-key CSV files, `.env`, or AWS credentials. The
included `.gitignore` excludes these files.

From this folder:

```powershell
git init
git add .
git commit -m "Deploy DeadlineWise"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## 2. Create the App Runner instance role

In IAM, create a role for the **App Runner instance role** use case. Name it:

```text
DeadlineWiseAppRunnerRole
```

Give it access to the `DeadlineTasks` DynamoDB table. You may initially attach
`AmazonDynamoDBFullAccess` for testing, then replace it with the restricted
policy in `aws-policy-local-app.json`.

This role lets the deployed app use DynamoDB without access keys.

## 3. Create the App Runner service

1. AWS Console → App Runner → Create service.
2. Source: Source code repository.
3. Connect GitHub, then select your repository and the `main` branch.
4. Deployment: Automatic.
5. Configuration source: Configure all settings here.
6. Runtime: Python 3.
7. Build command:

```text
pip install -r requirements.txt
```

8. Start command:

```text
gunicorn --bind 0.0.0.0:8080 app:app
```

9. Port: `8080`.
10. Instance role: `DeadlineWiseAppRunnerRole`.

## 4. Environment variables

Add:

```text
AWS_REGION=ap-southeast-1
DYNAMODB_TABLE=DeadlineTasks
FLASK_SECRET_KEY=replace-with-a-long-random-value
```

Generate the Flask secret locally with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

This Flask value is not an AWS access key. Never add `AWS_ACCESS_KEY_ID` or
`AWS_SECRET_ACCESS_KEY` to App Runner; the instance role supplies access.

## 5. Verify

After the service status becomes Running, open the App Runner URL and `/health`:

```text
https://YOUR_APP_RUNNER_URL/
https://YOUR_APP_RUNNER_URL/health
```

Add and edit a task, then verify the same item inside DynamoDB.

## 6. After the hackathon

Delete the App Runner service if it is no longer needed so it stops consuming
AWS credits.
