"""AWS Lambda entry point for the API (wired up by Terraform in Part 10).

API Gateway -> Lambda -> Mangum -> FastAPI. In AWS the queue mode is SQS and the store is
DynamoDB; those adapters arrive in Part 10.
"""

from mangum import Mangum

from papertrail.api.app import create_app

handler = Mangum(create_app(), lifespan="off")
