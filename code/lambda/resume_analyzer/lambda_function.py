import json
import os
import re
import boto3

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
comprehend = boto3.client("comprehend", region_name="eu-west-1")  # not available in eu-north-1

EVAL_TABLE_NAME = os.environ["TABLE_NAME"]
JOBS_TABLE_NAME = os.environ["JOBS_TABLE_NAME"]
TOPIC_ARN       = os.environ["TOPIC_ARN"]

eval_table = dynamodb.Table(EVAL_TABLE_NAME)
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)

STOPWORDS = {
    "the","a","an","and","or","of","to","in","for","with","on",
    "at","by","is","are","be","as","this","that","we","you",
    "will","your","our","from","have","has","it","its","their",
}


def extract_key_phrases(text):
    """Prefers Comprehend for real phrase understanding; falls back to
    simple keyword extraction if Comprehend is unavailable, so the
    pipeline keeps working end to end either way."""
    try:
        result = comprehend.detect_key_phrases(Text=text[:5000], LanguageCode="en")
        return {kp["Text"].lower().strip() for kp in result["KeyPhrases"]}
    except Exception as e:
        print(f"Comprehend unavailable, falling back to keywords: {e}")
        words = re.findall(r"[a-zA-Z][a-zA-Z\+\#\.]{2,}", text.lower())
        return {w.strip(".") for w in words if w not in STOPWORDS and len(w) > 2}


def lambda_handler(event, context):
    for record in event.get("Records", []):
        try:
            process_candidate(json.loads(record["body"]))
        except Exception as e:
            print(f"Failed to process record: {e}")
    return {"statusCode": 200}


def process_candidate(data):
    job = jobs_table.get_item(Key={"job_id": data["job_id"]}).get("Item")
    if not job:
        print(f"Job not found: {data['job_id']}")
        return

    jd_phrases     = extract_key_phrases(job.get("jd_text", ""))
    resume_phrases = extract_key_phrases(data["resume_text"])

    matched = {p for p in jd_phrases if p in resume_phrases or any(p in r or r in p for r in resume_phrases)}
    missing = jd_phrases - matched
    score = round(len(matched) / len(jd_phrases) * 100) if jd_phrases else 0
    top_missing = sorted(missing, key=len, reverse=True)[:10]

    eval_table.put_item(Item={
        "candidate_id":    data["candidate_id"],
        "candidate_name":  data["candidate_name"],
        "candidate_email": data["candidate_email"],
        "job_id":          data["job_id"],
        "job_title":       job.get("title", ""),
        "match_score":     score,
        "missing_skills":  top_missing,
        "submitted_at":    data["submitted_at"],
    })

    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f"New candidate evaluated: {data['candidate_name']} ({score}% match)"[:100],
        Message=(
            f"{data['candidate_name']} was evaluated for '{job.get('title', data['job_id'])}'.\n\n"
            f"Match score: {score}%\n"
            f"Missing skills: {', '.join(top_missing)}"
        ),
    )
