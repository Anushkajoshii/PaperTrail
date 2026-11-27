"""Load secrets (e.g. the Groq API key) from SSM Parameter Store into the environment.

Secrets are created by hand with the AWS CLI, so they never appear in Terraform state, in
GitHub, or in the Lambda configuration. Only names that look like PaperTrail settings are
accepted, so a stray parameter can never override something like PATH.
"""

from __future__ import annotations

import os
import re
from typing import Any

_NAME = re.compile(r"^PAPERTRAIL_[A-Z0-9_]+$")


def load_ssm_secrets(path: str, ssm_client: Any | None = None) -> list[str]:
    """Copy every SecureString under ``path`` into os.environ. Returns the names loaded."""
    if ssm_client is None:
        import boto3

        ssm_client = boto3.client("ssm")
    loaded: list[str] = []
    pages = ssm_client.get_paginator("get_parameters_by_path").paginate(
        Path=path.rstrip("/") + "/", WithDecryption=True
    )
    for page in pages:
        for param in page["Parameters"]:
            name = param["Name"].rsplit("/", 1)[-1]
            value = param["Value"]
            if _NAME.match(name) and value and value != "unset":
                os.environ[name] = value
                loaded.append(name)
    return loaded


def load_secrets_from_env() -> list[str]:
    """In Lambda: load secrets if PAPERTRAIL_SSM_SECRETS_PATH is set (before settings are read)."""
    path = os.environ.get("PAPERTRAIL_SSM_SECRETS_PATH")
    return load_ssm_secrets(path) if path else []
