"""AWS Lambda entry point for the API (and the web app): API Gateway -> Lambda -> Mangum.

Secrets are loaded from SSM before the settings are read. In AWS the store is DynamoDB, the
queue is SQS and uploads go to S3 (all chosen by environment variables set in Terraform).
"""

from mangum import Mangum

from papertrail.api.web import create_root_app
from papertrail.aws.secrets import load_secrets_from_env

load_secrets_from_env()
handler = Mangum(create_root_app(), lifespan="off")
