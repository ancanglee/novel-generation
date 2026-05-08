# U8 Infrastructure Design

## 目标

把 `infra/cdk/stacks/agentcore_stack.py` 从占位改造为真正创建 Memory / Runtime×5 / Gateway×1 / GatewayTarget×6 / WorkloadIdentity / （Browser 使用 DEFAULT identifier，不需独立 CreateBrowser）。

## 组件结构

```
infra/cdk/
├── stacks/
│   └── agentcore_stack.py              # REWRITE：改为真资源编排
├── bootstrap/                          # NEW
│   └── agentcore_bootstrap/
│       ├── handler.py                  # Lambda 入口（Custom Resource 后端）
│       └── __init__.py
└── shared_constructs/
    └── agentcore_custom_resource.py    # NEW：AwsCustomResource 包装
```

## AgentCoreStack 职责

1. **Memory**：AwsCustomResource → Lambda → `bedrock-agentcore-control.CreateMemory`
2. **WorkloadIdentity**：AwsCustomResource → Lambda → `CreateWorkloadIdentity`
3. **Gateway**：AwsCustomResource → Lambda → `CreateGateway(protocolType=MCP, authorizerConfiguration.workloadIdentityAuthorizer=True)`
4. **Gateway Targets × 6**：每个一个 AwsCustomResource → Lambda → `CreateGatewayTarget(lambdaArn=<对应 Gateway Lambda ARN>)`
5. **AgentRuntime × 5**：`CreateAgentRuntime(agentRuntimeArtifact.containerConfiguration.containerUri=<ECR image>)` — 镜像复用既有 worker-* ECR repo
6. **SSM Parameters（写入）**：
   - `/novelgen/{env}/agentcore/memory-id`
   - `/novelgen/{env}/agentcore/memory-arn`
   - `/novelgen/{env}/agentcore/workload-identity-arn`
   - `/novelgen/{env}/agentcore/gateway-id`
   - `/novelgen/{env}/agentcore/gateway-endpoint`
   - `/novelgen/{env}/agentcore/runtime/{role}-arn`（5 个）

## IAM Role

### `novelgen-{env}-agentcore-bootstrap-role`
Attached to bootstrap Lambda。允许：
```
bedrock-agentcore-control:*     (CreateMemory / Gateway / GatewayTarget / AgentRuntime / WorkloadIdentity / Update / Delete / List)
iam:PassRole                    (pass gateway-role and runtime-role)
logs:CreateLogStream/PutLogEvents
ssm:PutParameter                (for emitting resource IDs)
```

### `novelgen-{env}-gateway-role`
Gateway 调用 Lambda target 时用。允许：
```
lambda:InvokeFunction on arn:aws:lambda:{region}:{account}:function:novelgen-{env}-gateway-*
```

### `novelgen-{env}-runtime-role`
AgentCore Runtime 容器运行时用（已有 worker IAM 扩展）。新增：
```
bedrock-agentcore:GetWorkloadAccessToken
bedrock-agentcore:CreateEvent
bedrock-agentcore:RetrieveMemoryRecords
bedrock-agentcore:ListEvents
bedrock-agentcore:StartBrowserSession
bedrock-agentcore:StopBrowserSession
bedrock-agentcore:GetBrowserSession
bedrock-agentcore:InvokeAgentRuntime  (Supervisor → Sub-agent)
```

## Lambda 布局（Gateway Targets）

```
lambdas/
├── gateway-memory-facade/       # NEW
├── gateway-graph-ops/           # NEW (VPC required for Neptune)
├── gateway-vector-ops/          # NEW (VPC required for AOSS if inside VPC)
├── gateway-ingestion-fetch/     # NEW
├── gateway-ingestion-browser/   # NEW (calls AgentCore Browser + CDP)
└── gateway-ddb-jobs/            # NEW
```

每 Lambda：Python 3.12, 1024MB, 30s timeout。复用 `packages/shared-types-py`, `packages/memory-facade`, `packages/storage-adapter`。

## SSM 参数迁移

删除（或保留兼容）：
- `/novelgen/{env}/agentcore/memory-namespace-pattern`（旧）→ 改为 `{team_id}:{novel_id}` 固化到 Memory strategy 的 `namespaces` 字段。

新增（见上面 6 条 SSM path）。

## 部署顺序

CDK stack 依赖图新增边：
```
AgentCoreStack depends on DataStack (SSM table, etc.) + IdentityStack (roles)
ComputeStack (Worker ECS) depends on AgentCoreStack (for SSM lookups)
```

修改 `infra/cdk/app.py`：把 `compute` 的依赖 `.node.add_dependency(agentcore)` 添加。

## 回滚

Dev env：RemovalPolicy=DESTROY，CDK destroy 会调 bootstrap Lambda 的 onDelete。
Prod env：RemovalPolicy=RETAIN（Memory 数据），Gateway / Runtime 可重建；destroy 保留数据。
