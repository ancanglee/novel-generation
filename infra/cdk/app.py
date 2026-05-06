"""CDK App entry. Wires 8 layered stacks per U1 Infrastructure Design."""

from __future__ import annotations

import aws_cdk as cdk

from config import load_config
from stacks.agentcore_stack import AgentCoreStack
from stacks.compute_stack import ComputeStack
from stacks.data_stack import DataStack
from stacks.edge_stack import EdgeStack
from stacks.identity_stack import IdentityStack
from stacks.messaging_stack import MessagingStack
from stacks.network_stack import NetworkStack
from stacks.observability_stack import ObservabilityStack


def main() -> None:
    app = cdk.App()
    cfg = load_config()

    env = cdk.Environment(account=cfg.account, region=cfg.region)
    tags = {"Project": "NovelGen", "Env": cfg.env_name, "ManagedBy": "cdk"}

    network = NetworkStack(app, f"{cfg.prefix}-network", cfg=cfg, env=env)

    data = DataStack(app, f"{cfg.prefix}-data", cfg=cfg, network=network, env=env)

    identity = IdentityStack(app, f"{cfg.prefix}-identity", cfg=cfg, data=data, env=env)

    messaging = MessagingStack(
        app, f"{cfg.prefix}-messaging", cfg=cfg, data=data, identity=identity, env=env
    )

    compute = ComputeStack(
        app,
        f"{cfg.prefix}-compute",
        cfg=cfg,
        network=network,
        data=data,
        identity=identity,
        messaging=messaging,
        env=env,
    )

    EdgeStack(app, f"{cfg.prefix}-edge", cfg=cfg, compute=compute, env=env)

    ObservabilityStack(
        app, f"{cfg.prefix}-observability", cfg=cfg, data=data, compute=compute, env=env
    )

    AgentCoreStack(app, f"{cfg.prefix}-agentcore", cfg=cfg, data=data, identity=identity, env=env)

    for k, v in tags.items():
        cdk.Tags.of(app).add(k, v)

    app.synth()


if __name__ == "__main__":
    main()
