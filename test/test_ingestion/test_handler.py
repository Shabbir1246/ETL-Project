import os
from datetime import datetime
import logging
from unittest.mock import patch
import boto3
import pytest
from moto import mock_s3, mock_secretsmanager
from src.ingestion.handler import handler


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-2"


@pytest.fixture(scope="function")
def s3_client(aws_credentials):
    """Mocks the call to the AWS S3 client."""
    with mock_s3():
        yield boto3.client("s3", region_name="eu-west-2")


@pytest.fixture(scope="function")
def secrets_client(aws_credentials):
    """Mocks the call to the AWS SecretsManager client."""
    with mock_secretsmanager():
        yield boto3.client("secretsmanager", region_name="eu-west-2")


def test_handler_uses_mock_aws_credentials():
    """Checks the tests aren't using the actual AWS keys at any point"""
    logging.info(os.environ['AWS_ACCESS_KEY_ID'])
    logging.info(os.environ['AWS_SECRET_ACCESS_KEY'])
    logging.info(os.environ['AWS_DEFAULT_REGION'])
    assert os.environ['AWS_ACCESS_KEY_ID'] == "test"
    assert os.environ['AWS_SECRET_ACCESS_KEY'] == "test"
    assert os.environ['AWS_DEFAULT_REGION'] == "eu-west-2"


def test_handler_logs_bucket_empty_and_pulling_dataset_when_needed(
    s3_client, secrets_client, caplog
):
    """Tests the handler produces logs for pulling data when a bucket is empty.
    Tests for incorrect logs being sent."""
    secrets_client.create_secret(
        Name="Totesys-Credentials", SecretString="""
                        {
                            "host": "x",
                            "port": "x",
                            "database": "x",
                            "user": "x",
                            "password" : "x"
                        }
                        """
    )
    s3_client.create_bucket(
        Bucket="ingestion-data-bucket-marble",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
    )
    with (patch('src.ingestion.handler.connect_to_database') as mock_conn,
          patch('src.ingestion.handler.fetch_tables',
                return_value=['table1', 'table2', 'table3']),
          patch('src.ingestion.handler.get_previous_update_dt',
                return_value=True),
          patch('src.ingestion.handler.fetch_data_from_tables',
                return_value={'table_name': 'table1', 'data': ['data1']})):
        mock_conn.cursor = True
        mock_conn.execute = True
        handler("event", "context")
        assert "has been updated. Pulling new data" in caplog.text
        assert "No need to update." not in caplog.text


def test_handler_logs_no_need_to_update_if_bucket_has_file(
    s3_client, secrets_client, caplog
):
    """Tests the handler produces logs for not pulling data
    when most recent file is up to date. Tests for incorrect
    logs being sent."""
    secrets_client.create_secret(
        Name="Totesys-Credentials", SecretString="""
                        {
                            "host": "x",
                            "port": "x",
                            "database": "x",
                            "user": "x",
                            "password" : "x"
                        }
                        """
    )
    s3_client.create_bucket(
        Bucket="ingestion-data-bucket-marble",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
    )
    with patch('src.ingestion.handler.connect_to_database') as mock_conn:
        mock_conn.cursor = True
        mock_conn.execute = True
        file_names = [
            "currency",
            "payment",
            "department",
            "design",
            "counterparty",
            "purchase_order",
            "payment_type",
            "sales_order",
            "address",
            "staff",
            "transaction",
        ]
        prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for name in file_names:
            s3_client.put_object(
                Bucket="ingestion-data-bucket-marble",
                Key=f"{prefix}-{name}.csv")
        handler("event", "context")
    assert "has been updated. Pulling new data" not in caplog.text
    assert "has no initial data. Pulling data" not in caplog.text
    assert "No need to update" in caplog.text


def test_handler_checks_for_initial_data(s3_client, secrets_client, caplog):
    """Tests the handler is able to check whether initial data
    exists in the bucket, and responds appropriately."""
    secrets_client.create_secret(
        Name="Totesys-Credentials", SecretString="""
                        {
                            "host": "x",
                            "port": "x",
                            "database": "x",
                            "user": "x",
                            "password" : "x"
                        }
                        """
    )

    s3_client.create_bucket(
        Bucket="ingestion-data-bucket-marble",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
    )

    with (patch('src.ingestion.handler.connect_to_database') as mock_conn,
          patch('src.ingestion.handler.fetch_tables',
                return_value=['table1', 'table2', 'table3']),
          patch('src.ingestion.handler.get_previous_update_dt',
                return_value=False),
          patch('src.ingestion.handler.fetch_data_from_tables',
                return_value={'table_name': 'table1', 'data': ['data1']})):
        mock_conn.cursor = True
        mock_conn.execute = True
        handler("event", "context")
        assert "has been updated. Pulling new data" not in caplog.text
        assert "has no initial data. Pulling data" in caplog.text
        assert "No need to update" not in caplog.text
