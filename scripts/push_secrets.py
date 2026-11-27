"""Copy secret keys from your local .env into AWS SSM Parameter Store (encrypted).

    AWS_PROFILE=portfolio uv run python scripts/push_secrets.py

Only the names Terraform created placeholders for are sent. Values are never printed, so
they stay out of your terminal history, Terraform state and GitHub.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SECRETS = ("PAPERTRAIL_GROQ_API_KEY", "PAPERTRAIL_TAVILY_API_KEY")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main(argv: list[str] | None = None, ssm=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--path", default="/papertrail/prod")
    parser.add_argument("--region", default="ap-southeast-2")
    args = parser.parse_args(argv)

    env = read_env(Path(args.env_file))
    found = {k: v for k in SECRETS if (v := env.get(k))}
    if not found:
        print(f"No secrets set in {args.env_file} (looked for: {', '.join(SECRETS)})")
        return 1
    if ssm is None:
        import boto3

        ssm = boto3.client("ssm", region_name=args.region)
    for name, value in found.items():
        ssm.put_parameter(
            Name=f"{args.path}/{name}", Value=value, Type="SecureString", Overwrite=True
        )
        print(f"Stored {name} ({len(value)} characters) in {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
