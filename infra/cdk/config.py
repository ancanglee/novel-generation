"""Environment configuration for CDK stacks."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvConfig:
    env_name: str
    region: str
    account: str | None
    vpc_cidr: str
    alert_email: str

    @property
    def prefix(self) -> str:
        """Short prefix used in resource names (novelgen + env)."""
        return f"novelgen-{self.env_name}"

    @property
    def ddb_prefix(self) -> str:
        """DynamoDB uses underscore style."""
        return f"novelgen_{self.env_name}"


def load_config() -> EnvConfig:
    env_name = os.environ.get("NOVELGEN_ENV", "dev")
    return EnvConfig(
        env_name=env_name,
        region=os.environ.get("AWS_REGION", "us-west-2"),
        account=os.environ.get("CDK_DEFAULT_ACCOUNT") or os.environ.get("AWS_ACCOUNT"),
        vpc_cidr=os.environ.get("NOVELGEN_VPC_CIDR", "10.20.0.0/16"),
        alert_email=os.environ.get("NOVELGEN_ALERT_EMAIL", "admin@example.com"),
    )
