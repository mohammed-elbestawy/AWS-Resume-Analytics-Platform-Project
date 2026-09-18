<a id="top"></a>

# 🛠️ Build Log — Resume Analytics Platform

Each step below is the correct way to do it, with a short explanation of its purpose.

## 📋 Quick Navigation

| Step | Section |
|---|---|
| 1 | [🗃️ DynamoDB Tables](#step-1) |
| 2 | [📬 SQS Queue](#step-2) |
| 3 | [📣 SNS Topic](#step-3) |
| 4 | [🔑 Cognito User Pool](#step-4) |
| 5 | [🔐 IAM Role & Policy](#step-5) |
| 6 | [🪣 S3 Bucket (Resume Storage)](#step-6) |
| 7 | [⚡ Lambda: resume-intake](#step-7) |
| 8 | [⚡ Lambda: resume-analyzer](#step-8) |
| 9 | [⚡ Lambda: get-evaluations](#step-9) |
| 10 | [🔌 API Gateway](#step-10) |
| 11 | [🌍 S3 + CloudFront (Frontend)](#step-11) |
| 12 | [✅ End-to-End Test](#step-12) |

---

<a id="step-1"></a>
## Step 1 — 🗃️ DynamoDB Tables

Two separate tables — one for job descriptions, one for candidate results — instead of overloading a single table with two different kinds of records.

| Table | Partition key | Purpose |
|---|---|---|
| `job-descriptions` | `job_id` (String) | Stores each job's title and description text |
| `candidate-evaluations` | `candidate_id` (String) | Stores each candidate's score and missing skills |

Both use On-demand capacity mode.

![Jobs table](screenshots/01-dynamodb-jobs.png)
![Candidates table](screenshots/01-dynamodb-candidates.png)

---

<a id="step-2"></a>
## Step 2 — 📬 SQS Queue

This lets the candidate get an instant confirmation, instead of waiting for the AI scoring to finish first.

| Setting | Value |
|---|---|
| Name | `resume-analysis-queue` |
| Type | Standard |
| Visibility timeout | 60 seconds |

![SQS queue](screenshots/02-sqs-queue.png)

---

<a id="step-3"></a>
## Step 3 — 📣 SNS Topic

Notifies the recruiter every time a new candidate finishes scoring.

| Setting | Value |
|---|---|
| Topic name | `evaluation-notifications` |
| Type | Standard |
| Subscription | Email, confirmed |

![SNS topic](screenshots/03-sns-topic.png)

---

<a id="step-4"></a>
## Step 4 — 🔑 Cognito User Pool

Real login for the recruiter dashboard.

| Setting | Value |
|---|---|
| Pool name | `recruiter-auth-pool` |
| Application type | **Single-page application (SPA)** |
| Recruiter user | Created manually in the Users tab |

The app client is created as **SPA** from the start — this type has no Client Secret, which browser-side JavaScript needs since it has nowhere secure to hold one.

![Cognito user pool](screenshots/04-cognito-pool.png)
![Recruiter user created](screenshots/04-cognito-user.png)

---

<a id="step-5"></a>
## Step 5 — 🔐 IAM Role & Policy

Scoped to exactly what the three Lambda functions use — both DynamoDB tables, the specific S3 bucket, the specific queue, and the two Comprehend actions actually called.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::resume-storage-*/*"
    },
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
      "Resource": "arn:aws:sqs:*:*:resume-analysis-queue"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:UpdateItem"],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/job-descriptions",
        "arn:aws:dynamodb:*:*:table/candidate-evaluations"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "comprehend:DetectKeyPhrases",
      "Resource": "*"
    }
  ]
}
```

![IAM role](screenshots/05-iam-role.png)

---

<a id="step-6"></a>
## Step 6 — 🪣 S3 Bucket (Resume Storage)

Keeps an archived copy of every submitted resume, fully private.

| Setting | Value |
|---|---|
| Name | `resume-storage-<account-id>` |
| Block all public access | On |

![S3 resume storage](screenshots/06-s3-storage.png)

---

<a id="step-7"></a>
## Step 7 — ⚡ Lambda: resume-intake

Validates the submission, archives the resume to S3, and queues it for scoring.

| Setting | Value |
|---|---|
| Name | `resume-intake` |
| Runtime | Python 3.12 |
| Env vars | `QUEUE_URL`, `BUCKET_NAME`, `ALLOWED_ORIGIN` |
| Timeout | 15 sec |

Full code: [`code/lambda/resume_intake/lambda_function.py`](code/lambda/resume_intake/lambda_function.py)

![Lambda intake config](screenshots/07-lambda-intake-config.png)

---

<a id="step-8"></a>
## Step 8 — ⚡ Lambda: resume-analyzer

Triggered by SQS. Extracts key phrases from both the job description and the resume via Comprehend, computes a match score, stores it, and notifies the recruiter.

| Setting | Value |
|---|---|
| Name | `resume-analyzer` |
| Runtime | Python 3.12 |
| Env vars | `TABLE_NAME` (candidate-evaluations), `JOBS_TABLE_NAME`, `TOPIC_ARN` |
| Trigger | SQS — `resume-analysis-queue` |
| Timeout | 30 sec |

**Note on region:** Comprehend isn't available in `eu-north-1`, so the client explicitly targets `eu-west-1`:
```python
comprehend = boto3.client("comprehend", region_name="eu-west-1")
```

**Note on resilience:** the key-phrase extraction has a fallback — if Comprehend is unavailable for any reason, it drops to a simple keyword extractor instead of failing the whole function. Scoring still works, just with less linguistic precision until Comprehend responds again.

Full code: [`code/lambda/resume_analyzer/lambda_function.py`](code/lambda/resume_analyzer/lambda_function.py)

![Lambda analyzer config](screenshots/08-lambda-analyzer-config.png)
![SQS trigger attached](screenshots/08-lambda-trigger.png)

---

<a id="step-9"></a>
## Step 9 — ⚡ Lambda: get-evaluations

Returns every candidate, ranked by match score, to the authenticated recruiter dashboard. Supports an optional `job_id` filter.

| Setting | Value |
|---|---|
| Name | `get-evaluations` |
| Runtime | Python 3.12 |
| Env vars | `TABLE_NAME`, `ALLOWED_ORIGIN` |

Full code: [`code/lambda/get_evaluations/lambda_function.py`](code/lambda/get_evaluations/lambda_function.py)

![Lambda get-evaluations config](screenshots/09-lambda-getevals-config.png)

---

<a id="step-9.5"></a>
### Adding a Test Job

There's no dedicated endpoint for creating jobs in this version — a job is added directly in DynamoDB for testing:

1. **DynamoDB** → `job-descriptions` → **Explore table items** → **Create item**
2. `job_id`: `cloud-security-01`
3. Add attribute `title` = `Cloud Security Engineer`
4. Add attribute `jd_text` = a real job description (a couple of sentences is enough for testing)

![Test job created](screenshots/09-dynamodb-job-created.png)

---

<a id="step-10"></a>
## Step 10 — 🔌 API Gateway

Connects the frontend to all three Lambda functions, with the recruiter route protected by Cognito.

| Setting | Value |
|---|---|
| API name | `resume-evaluation-api` (REST, Regional) |
| `POST /submit-resume` | Public → `resume-intake` |
| `GET /evaluations` | **Cognito-protected** → `get-evaluations` |
| Stage | `prod` |

**Important note on CORS:** there are **two separate places** that must be configured together:
1. `ALLOWED_ORIGIN` inside each Lambda (environment variable)
2. The `Access-Control-Allow-Origin` header on API Gateway's own **OPTIONS** method response

Both values must match **exactly** (`https://`, no trailing `/`), and any change in API Gateway requires **Actions → Deploy API → prod** to take effect.

![API Gateway invoke URL](screenshots/10-apigateway-invoke.png)
![Cognito authorizer attached to /evaluations](screenshots/10-apigateway-authorizer.png)

---

<a id="step-11"></a>
## Step 11 — 🌍 S3 + CloudFront (Frontend)

Hosts both the candidate submission form and the recruiter dashboard from a fully private bucket.

1. **S3** → `resume-platform-frontend-<account-id>` → leave **Block all public access** enabled
2. Upload `index.html`, `admin.html`, `style.css`, `script.js`, `admin.js` (after filling in the real API URL and Cognito IDs)
3. **CloudFront** → **Create distribution** → Origin: the S3 bucket
4. **Allow private S3 bucket access to CloudFront**: leave enabled ✅ — this sets up OAC automatically
5. **Origin settings**: Use recommended origin settings
6. **Cache settings**: choose **Customize cache settings**:
   - Viewer protocol policy: Redirect HTTP to HTTPS
   - Allowed HTTP methods: GET, HEAD
7. **Enable security protections**: **Do not enable security protections**
8. **Create distribution** → copy the generated bucket policy from the banner → paste into **S3 → Bucket policy → Edit → Save**

![CloudFront distribution enabled](screenshots/11-cloudfront-distribution.png)
![S3 bucket policy scoped to CloudFront](screenshots/11-s3-bucket-policy.png)

---

<a id="step-12"></a>
## Step 12 — ✅ End-to-End Test

1. Update `ALLOWED_ORIGIN` on both public-facing Lambdas to the real CloudFront domain
2. Open the site → submit a test resume against `job_id: cloud-security-01`
3. Open `admin.html` → log in with the recruiter account → confirm the candidate appears with the correct score and missing skills

| Check | Result |
|---|---|
| Resume submission → instant confirmation | ✅ |
| Async scoring via SQS + Comprehend | ✅ |
| Recruiter notification email | ✅ |
| Dashboard shows ranked candidates | ✅ |

![Resume submitted successfully](screenshots/12-fulltest-submit.png)
![Recruiter dashboard showing ranked candidates](screenshots/12-fulltest-dashboard.png)

---

<div align="center">

**[⬆ Back to top](#top)**

</div>
