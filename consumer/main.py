import json
from urllib.parse import unquote_plus

import boto3
from secret_keys import SecretKeys

secret_keys = SecretKeys()
sqs_client = boto3.client("sqs", region_name=secret_keys.REGION_NAME)
ecs_client = boto3.client("ecs", region_name=secret_keys.REGION_NAME)
SUBNETS = secret_keys.SUBNETS.split(",") if secret_keys.SUBNETS else []

SECURITY_GROUPS = (
    secret_keys.SECURITY_GROUPS.split(",") if secret_keys.SECURITY_GROUPS else []
)


def check_running_tasks(running_tasks: dict):
    if not running_tasks:
        return
    response = ecs_client.describe_tasks(
        cluster=secret_keys.CLUSTER_NAME, tasks=list(running_tasks)
    )
    for task in response.get("tasks", []):
        if task["lastStatus"] != "STOPPED":
            continue
        s3_key = running_tasks.pop(task["taskArn"])
        exit_code = task["containers"][0].get("exitCode")
        if exit_code == 0:
            print(f"Processed {s3_key} successfully")
        else:
            print(
                f"Failed to process {s3_key}: exit_code={exit_code} "
                f"reason={task.get('stoppedReason')}"
            )


def poll_sqs():
    running_tasks = {}
    while True:
        check_running_tasks(running_tasks)
        response = sqs_client.receive_message(
            QueueUrl=secret_keys.VIDEO_PROCESSING_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
        )
        for message in response.get("Messages", []):
            message_body = json.loads(message["Body"])
            if message_body.get("Event") == "s3:TestEvent":
                sqs_client.delete_message(
                    QueueUrl=secret_keys.VIDEO_PROCESSING_QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"],
                )
                print("Deleted S3 test event")
                continue

            if "Records" in message_body:
                s3_record = message_body.get("Records")[0]["s3"]
                bucket_name = s3_record.get("bucket").get("name")
                s3_key = unquote_plus(s3_record.get("object").get("key"))
                # spin up a docker container
                response = ecs_client.run_task(
                    cluster=secret_keys.CLUSTER_NAME,
                    launchType="FARGATE",
                    taskDefinition=secret_keys.TASK_DEFINITION_NAME,
                    overrides={
                        "containerOverrides": [
                            {
                                "name": "video-transcoder",
                                "environment": [
                                    {"name": "S3_BUCKET", "value": bucket_name},
                                    {"name": "S3_KEY", "value": s3_key},
                                    {
                                        "name": "S3_PROCESSED_VIDEOS_BUCKET",
                                        "value": secret_keys.S3_PROCESSED_VIDEOS_BUCKET,
                                    },
                                ],
                            }
                        ],
                    },
                    networkConfiguration={
                        "awsvpcConfiguration": {
                            "subnets": SUBNETS,
                            "securityGroups": SECURITY_GROUPS,
                            "assignPublicIp": "ENABLED",
                        }
                    },
                )
                for failure in response.get("failures", []):
                    print(f"Failed to start task for {s3_key}: {failure}")
                for task in response.get("tasks", []):
                    running_tasks[task["taskArn"]] = s3_key
                    print(f"Started task {task['taskArn'].split('/')[-1]} for {s3_key}")
                sqs_client.delete_message(
                    QueueUrl=secret_keys.VIDEO_PROCESSING_QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"],
                )


poll_sqs()
