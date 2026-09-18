import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}
        job_id_filter = params.get("job_id")

        result = table.scan()
        items = result.get("Items", [])

        if job_id_filter:
            items = [i for i in items if i.get("job_id") == job_id_filter]

        items.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return _response(200, {"count": len(items), "candidates": items})

    except Exception as e:
        print(f"ERROR: {e}")
        return _response(500, {"error": "Something went wrong. Please try again later."})


def _response(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": ALLOWED_ORIGIN},
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }
