import boto3
import json
from secret_keys import SecretKeys

secret_keys = SecretKeys()
sqs_client = boto3.client("sqs", region_name=secret_keys.REGION_NAME)


def poll_sqs():
    while True:
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
                s3_key = s3_record.get("object").get("key")
                # spin up a docker container
            

poll_sqs()
