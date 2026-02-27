import json
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

def get_secret(secret_name: str, region_name: str = "us-east-1") -> dict:
    """
    Retrieve a secret from AWS Secrets Manager.
    
    Expected format in Secrets Manager (JSON):
    {
      "DATABASE_URL": "postgresql://user:pass@host:5432/db",
      "REDIS_URL": "redis://host:6379/0",
      "GITHUB_WEBHOOK_SECRET": "your-secret",
      "AWS_ACCESS_KEY_ID": "optional",
      "AWS_SECRET_ACCESS_KEY": "optional"
    }
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        logger.error(f"Error retrieving secret {secret_name} from AWS Secrets Manager: {e}")
        raise e

    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
        try:
            return json.loads(secret)
        except json.JSONDecodeError:
            # If the secret is not JSON, wrap it in a dict for consistency
            return {"value": secret}
    else:
        logger.error(f"Binary secrets not supported for {secret_name}")
        return {}
