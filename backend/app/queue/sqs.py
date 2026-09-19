from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3

from app.core.config import (
    SQS_ACCESS_KEY,
    SQS_ANALYSIS_QUEUE_NAME,
    SQS_ENDPOINT_URL,
    SQS_REGION,
    SQS_SECRET_KEY,
    WORKER_VISIBILITY_TIMEOUT,
)


@lru_cache(maxsize=1)
def get_sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=SQS_ENDPOINT_URL,
        region_name=SQS_REGION,
        aws_access_key_id=SQS_ACCESS_KEY,
        aws_secret_access_key=SQS_SECRET_KEY,
    )


@lru_cache(maxsize=1)
def get_analysis_queue_url() -> str:
    response = get_sqs_client().get_queue_url(
        QueueName=SQS_ANALYSIS_QUEUE_NAME
    )

    return response["QueueUrl"]


def send_analysis_message(payload: dict[str, Any]) -> str:
    response = get_sqs_client().send_message(
        QueueUrl=get_analysis_queue_url(),
        MessageBody=json.dumps(payload),
    )

    return response["MessageId"]


def receive_analysis_messages(
    *,
    wait_time_seconds: int = 20,
    max_messages: int = 1,
) -> list[dict[str, Any]]:
    response = get_sqs_client().receive_message(
        QueueUrl=get_analysis_queue_url(),
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time_seconds,
        VisibilityTimeout=WORKER_VISIBILITY_TIMEOUT,
        AttributeNames=["ApproximateReceiveCount"],
    )

    return response.get("Messages", [])


def delete_analysis_message(receipt_handle: str) -> None:
    get_sqs_client().delete_message(
        QueueUrl=get_analysis_queue_url(),
        ReceiptHandle=receipt_handle,
    )


def queue_healthcheck() -> None:
    get_sqs_client().get_queue_attributes(
        QueueUrl=get_analysis_queue_url(),
        AttributeNames=["QueueArn"],
    )

def get_queue_metrics() -> dict[str, int]:
    response = get_sqs_client().get_queue_attributes(
        QueueUrl=get_analysis_queue_url(),
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
        ],
    )
    attrs = response.get("Attributes", {})
    return {
        "visible": int(attrs.get("ApproximateNumberOfMessages", "0")),
        "inflight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
    }
