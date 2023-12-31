import os
import datetime
import pytest
from moto import mock_s3
import boto3
from pytest import raises
from botocore.exceptions import ClientError
from src.ingestion.find_latest import (get_previous_update_dt)


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'test'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
    os.environ['AWS_SECURITY_TOKEN'] = 'test'
    os.environ['AWS_SESSION_TOKEN'] = 'test'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-west-2'


@pytest.fixture(scope="function")
def s3_client(aws_credentials):
    """Mocks the call to the AWS S3 client."""
    with mock_s3():
        yield boto3.client("s3", region_name="eu-west-2")


@pytest.fixture(scope="function")
def create_bucket(s3_client):
    s3_client.create_bucket(
        Bucket="ingestion-data-bucket-marble",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
    )


def test_extracts_datetime_from_keys_when_given_tablename_to_search(
    create_bucket, s3_client
):
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-table/00:00.csv")

    assert get_previous_update_dt("test-table") == datetime.datetime(
        2023, 1, 1, 0, 0)


def test_should_extract_most_recent_datetime_from_keys(
        create_bucket, s3_client):
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-table/00:00.csv")
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-table/00:00.csv")
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-table/00:00.csv")

    assert get_previous_update_dt("test-table") == datetime.datetime(
        2023, 1, 1, 0, 0)


def test_should_extract_datetime_from_correct_table(create_bucket, s3_client):
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-not-this-table/00:00.csv",
    )
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-not-this-table-either/00:00.csv",
    )
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2022/01/01 00:00:00-test-table.csv")
    s3_client.put_object(
        Bucket="ingestion-data-bucket-marble",
        Key="2023/01/01/test-table/00:00.csv",
    )
    assert get_previous_update_dt("test-table") == datetime.datetime(
        2023, 1, 1, 0, 0)


def test_should_return_false_if_no_matches_are_found_in_the_bucket(
        create_bucket, s3_client):
    assert get_previous_update_dt("test-table") is False


def test_raises_client_errors_to_be_handled_if_target_bucket_does_not_exist(
    create_bucket, s3_client,
):
    with raises(ClientError):
        s3_client.put_object(
            Bucket="no-bucket",
            Key="2023/01/01/test-table/00:00.csv",
        )
