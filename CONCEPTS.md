<div align="center">

# 🧠 Design Concepts & Rationale

This file explains **why** each decision was made — the questions most likely to come up in an interview.

![AWS](https://img.shields.io/badge/AWS-Free%20Tier-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Region](https://img.shields.io/badge/Region-eu--north--1-232F3E?style=flat-square)

</div>

---

### Contents

[![Data Design](https://img.shields.io/badge/Data_Design-30363D?style=flat-square)](#data)
[![AI Matching](https://img.shields.io/badge/AI_Matching-30363D?style=flat-square)](#ai)
[![Decoupling](https://img.shields.io/badge/Decoupling-30363D?style=flat-square)](#decoupling)
[![Security](https://img.shields.io/badge/Security-30363D?style=flat-square)](#security)
[![Cost](https://img.shields.io/badge/Cost-30363D?style=flat-square)](#cost)

---

<a id="data"></a>
## 🗃️ Data Design

| Question | Answer |
|:---|:---|
| Why two DynamoDB tables instead of one? | Jobs and candidate evaluations are fundamentally different entities with different lifecycles — a job is created once and rarely changes; evaluations are created continuously as candidates apply. Separating them keeps each table's access patterns simple instead of mixing two record shapes with conditional logic everywhere. |
| Why is there no endpoint to create jobs? | The platform's core value is the scoring pipeline, not job management — adding a full CRUD API for jobs would be a separate, self-contained feature. Writing test jobs directly to DynamoDB was a deliberate scope decision to keep the build focused. |

---

<a id="ai"></a>
## 🤖 AI Matching

| Question | Answer |
|:---|:---|
| Why Comprehend's key-phrase extraction instead of a full ML resume parser? | Key phrases give genuinely useful matching signal — multi-word skills are treated as single concepts — without needing to train or host a custom model. It's the same approach proven in an earlier AI-enhanced project in this series, applied here from the recruiter's side instead of the candidate's. |
| Why does the analyzer fall back to keyword extraction instead of just failing? | A temporary AI service issue shouldn't mean a candidate's submission is silently lost. Falling back to simple keyword matching keeps the pipeline functional — with reduced precision — until Comprehend is available again. |
| Is the match score a reliable hiring signal on its own? | No — it's a first-pass filter to prioritize review time, not a hiring decision. A high score means the resume's language overlaps with the job description; it says nothing about actual competence, which is exactly why the missing-skills list is shown alongside the score rather than the score alone. |

---

<a id="decoupling"></a>
## 📬 Decoupling

| Question | Answer |
|:---|:---|
| Why does `resume-intake` queue the work instead of scoring immediately? | Comprehend calls and DynamoDB writes take real time, and a candidate submitting a resume shouldn't wait on that. SQS lets the intake function return an instant confirmation while `resume-analyzer` does the actual work in the background. |
| Why archive the resume to S3 if the full text already travels through SQS to the analyzer? | The SQS message is transient — once processed, it's gone. The S3 copy is the durable record, useful for re-analysis, audit, or manual review later without asking the candidate to resubmit. |

---

<a id="security"></a>
## 🔐 Security

| Question | Answer |
|:---|:---|
| Why protect `/evaluations` with Cognito instead of a shared password? | API Gateway rejects unauthenticated requests before any Lambda code runs, and each recruiter has their own real account rather than a password anyone with the link could use. |
| Why the SPA app client type specifically? | A "Traditional web application" client type expects a server that can securely hold a Client Secret. Browser JavaScript has no secure place to keep one, so Cognito rejects that flow entirely for public, client-side apps — the SPA type exists for exactly this case. |
| Why does the IAM policy list both DynamoDB tables explicitly instead of a wildcard table ARN? | Least privilege — the Lambda functions only ever need these two specific tables. A wildcard would grant access to any table created later in the account, which is a broader blast radius than the application requires. |

---

<a id="cost"></a>
## 💰 Cost

| Question | Answer |
|:---|:---|
| Why doesn't this project need the same teardown discipline as the WAF-based projects in this series? | Every service used here — Lambda, SQS, DynamoDB, SNS, Cognito, API Gateway, S3, CloudFront, and Comprehend at this volume — has an always-free tier or near-zero idle cost. Nothing bills by the hour regardless of traffic, unlike WAF or EC2/ALB in earlier projects. |
| Why On-Demand DynamoDB for both tables? | Submission volume is unpredictable and low at this scale — On-Demand avoids both throttling risk and the cost of provisioning capacity for traffic that may not arrive. |
