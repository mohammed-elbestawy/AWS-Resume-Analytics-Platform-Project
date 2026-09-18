import json
import os
import re
import uuid
import boto3
from datetime import datetime

sqs = boto3.client("sqs")
s3 = boto3.client("s3")

QUEUE_URL   = os.environ["QUEUE_URL"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_RESUME_LENGTH = 20000


def lambda_handler(event, context):
    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        required = ["candidate_name", "candidate_email", "job_id", "resume_text"]
        missing = [f for f in required if not str(body.get(f, "")).strip()]
        if missing:
            return _response(400, {"error": "Missing fields: " + ", ".join(missing)})

        if not EMAIL_RE.match(body["candidate_email"]):
            return _response(400, {"error": "Invalid email format"})

        candidate_id = str(uuid.uuid4())
        resume_text = body["resume_text"].strip()[:MAX_RESUME_LENGTH]

        # Archival copy — not needed for analysis itself, since the
        # text travels through SQS directly to the analyzer.
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"resumes/{candidate_id}.txt",
            Body=resume_text.encode("utf-8"),
            ContentType="text/plain",
        )

        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({
                "candidate_id": candidate_id,
                "candidate_name": body["candidate_name"].strip(),
                "candidate_email": body["candidate_email"].strip(),
                "job_id": body["job_id"].strip(),
                "resume_text": resume_text,
                "submitted_at": datetime.utcnow().isoformat(),
            }),
        )

        return _response(200, {
            "candidate_id": candidate_id,
            "message": "Resume received and queued for evaluation.",
        })

    except Exception as e:
        print(f"ERROR: {e}")
        return _response(500, {"error": "Something went wrong. Please try again later."})


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": ALLOWED_ORIGIN},
        "body": json.dumps(body, ensure_ascii=False),
    }
