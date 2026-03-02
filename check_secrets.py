import os
import boto3
import json

session = boto3.session.Session()
client = session.client('secretsmanager', region_name='ap-south-1')
response = client.get_secret_value(SecretId='doc-healing/production/secrets')
secret_dict = json.loads(response['SecretString'])
print("Keys in secret:", secret_dict.keys())
