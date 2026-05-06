# U1 基础设施设计（Infrastructure Design）

**Unit**：U1 Platform & Infrastructure
**阶段**：Infrastructure Design
**日期**：2026-04-27
**Region**: us-east-1
**Environment**: dev（V1 单环境）
**Domain Strategy**: CloudFront 默认域（V1 无自定义域名）
**CDK Stack 划分**: 8 个分层 Stack

---

## 1. 区域与账号

| 项 | 值 |
|---|---|
| AWS Region | `us-east-1`（N. Virginia）|
| 环境 | `dev`（仅一个）|
| CDK App 标识 | `novelgen-dev` |
| 账号 ID | 由 CDK context `--account` 传入（不硬编码）|

### 1.1 选择理由
- us-east-1 覆盖 Bedrock 全模型（Claude Opus 4.7 / Sonnet 4.6/4.7 / Haiku 4.5）
- AgentCore 全部 6 服务在 us-east-1 GA
- Neptune Serverless 与 OpenSearch Serverless 在 us-east-1 成熟
- CloudFront 自动全球分发，中国用户经边缘节点访问

---

## 2. 网络设计

### 2.1 VPC
```yaml
Name: novelgen-vpc-dev
CIDR: 10.20.0.0/16
AZ Count: 2 (us-east-1a, us-east-1b)
EnableDnsHostnames: true
EnableDnsSupport: true
NAT Gateway Count: 1 (dev 成本优先，单 AZ NAT)
```

### 2.2 子网分配
| 名称 | AZ | CIDR | 类型 | 用途 |
|---|---|---|---|---|
| public-a | us-east-1a | 10.20.0.0/24 | Public | ALB |
| public-b | us-east-1b | 10.20.1.0/24 | Public | ALB |
| private-a | us-east-1a | 10.20.16.0/22 | Private w/ NAT | ECS / Neptune |
| private-b | us-east-1b | 10.20.20.0/22 | Private w/ NAT | ECS / Neptune |
| isolated-a | us-east-1a | 10.20.32.0/24 | Isolated | 预留 |
| isolated-b | us-east-1b | 10.20.33.0/24 | Isolated | 预留 |

### 2.3 VPC Endpoints
| Endpoint | 类型 | 用途 |
|---|---|---|
| S3 | Gateway | 避免 NAT 流量费 |
| DynamoDB | Gateway | 同上 |
| Secrets Manager | Interface | ECS 访问密钥 |
| SSM Parameter Store | Interface | 配置读取 |
| CloudWatch Logs | Interface | 日志上传 |
| Bedrock Runtime | Interface | Agent 调用 |
| STS | Interface | AssumeRole |
| ECR API + DKR | Interface | 拉取镜像 |
| EventBridge | Interface | 事件发布 |

### 2.4 Security Groups
```yaml
sg-alb:
  ingress: [443 from 0.0.0.0/0]
  egress: [all to sg-ecs-api, sg-ecs-admin-front, sg-ecs-front]

sg-ecs-api:
  ingress: [8000 from sg-alb]
  egress: [443 all, 8182 to sg-neptune]

sg-ecs-front:
  ingress: [3000 from sg-alb]
  egress: [443 all]

sg-ecs-worker:
  ingress: []
  egress: [443 all, 8182 to sg-neptune]

sg-neptune:
  ingress: [8182 from sg-ecs-api, sg-ecs-worker]
  egress: []

sg-vpce:
  ingress: [443 from sg-ecs-*]
  egress: []
```

---

## 3. IAM 角色与策略

### 3.1 ECS Task Execution Role（通用）
`novelgen-ecs-task-execution-role-dev`

允许操作：
- ECR: 拉取镜像
- CloudWatch Logs: 创建 log stream 写日志
- Secrets Manager / SSM: 在容器启动时注入环境变量

### 3.2 API Service Task Role
`novelgen-api-task-role-dev`

策略摘要：
```json
{
  "Statement": [
    {"Effect":"Allow","Action":["dynamodb:GetItem","dynamodb:Query","dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:DeleteItem","dynamodb:BatchWriteItem"],
     "Resource":["arn:aws:dynamodb:us-east-1:*:table/novelgen_tenancy","arn:aws:dynamodb:us-east-1:*:table/novelgen_jobs","arn:aws:dynamodb:us-east-1:*:table/novelgen_config","arn:aws:dynamodb:us-east-1:*:table/novelgen_*/index/*"]},
    {"Effect":"Allow","Action":["dynamodb:Query","dynamodb:GetItem"],"Resource":"arn:aws:dynamodb:us-east-1:*:table/novelgen_audit"},
    {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],
     "Resource":["arn:aws:s3:::novelgen-novels-dev/*","arn:aws:s3:::novelgen-exports-dev/*"]},
    {"Effect":"Allow","Action":["states:StartExecution","states:DescribeExecution","states:SendTaskSuccess","states:SendTaskFailure"],
     "Resource":"arn:aws:states:us-east-1:*:stateMachine:novelgen-*"},
    {"Effect":"Allow","Action":["events:PutEvents"],"Resource":"arn:aws:events:us-east-1:*:event-bus/default"},
    {"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],
     "Resource":["arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-*"]},
    {"Effect":"Allow","Action":["secretsmanager:GetSecretValue"],
     "Resource":"arn:aws:secretsmanager:us-east-1:*:secret:/novelgen/dev/*"},
    {"Effect":"Allow","Action":["ssm:GetParameter","ssm:GetParameters","ssm:GetParametersByPath"],
     "Resource":"arn:aws:ssm:us-east-1:*:parameter/novelgen/dev/*"}
  ]
}
```

### 3.3 Audit Write Role
`novelgen-audit-write-role-dev`

仅允许 `PutItem` 到 audit 表：
```json
{
  "Statement": [
    {"Effect":"Allow","Action":["dynamodb:PutItem"],
     "Resource":"arn:aws:dynamodb:us-east-1:*:table/novelgen_audit",
     "Condition":{"StringEquals":{"dynamodb:Attributes":["audit_id","timestamp","actor_user_id","actor_team_id","action","target_type","target_id","before","after","request_id"]}}}
  ]
}
```

### 3.4 Worker Task Roles（5 个 Worker 类似）
`novelgen-worker-{type}-task-role-dev`

在 API Role 基础上补充：
- Neptune Data API（`neptune-db:ReadDataViaQuery`、`neptune-db:WriteDataViaQuery`）
- OpenSearch Serverless（`aoss:APIAccessAll`）
- AgentCore（`bedrock-agentcore:*`）
- SQS（`sqs:ReceiveMessage`、`sqs:DeleteMessage` 限定对应队列）

### 3.5 Step Functions Execution Role
`novelgen-sfn-execution-role-dev`
- `sqs:SendMessage`（发消息给 worker 队列）
- `states:StartExecution`（子状态机）
- `lambda:InvokeFunction`
- `events:PutEvents`
- `logs:*`（写执行日志）

### 3.6 Lambda Roles
| Lambda | 角色 |
|---|---|
| `pre-signup-trigger` | `novelgen-pre-signup-role-dev`（DynamoDB PutItem 到 tenancy）|
| `daily-cost-aggregator` | `novelgen-aggregator-role-dev`（cloudwatch:GetMetricData + DynamoDB PutItem）|
| `daily-audit-archiver` | `novelgen-archiver-role-dev`（DynamoDB Query + S3 Put）|

---

## 4. DynamoDB 表具体配置

### 4.1 `novelgen_tenancy_dev`
```yaml
PartitionKey: pk (String)           # TEAM#{team_id}
SortKey: sk (String)                # USER#{user_id} | NOVEL#{novel_id} | TEAM#META | CHAPTER#{novel_id}#{n}
BillingMode: PAY_PER_REQUEST
PointInTimeRecovery: true
TimeToLiveAttribute: ttl            # 可选
Encryption: AWS managed KMS
GlobalSecondaryIndexes:
  GSI-email:
    PK: email
    Projection: KEYS_ONLY
```

### 4.2 `novelgen_jobs_dev`
```yaml
PartitionKey: pk (String)           # TEAM#{team_id}
SortKey: sk (String)                # JOB#{job_id} | CONCURRENCY#{job_id}
BillingMode: PAY_PER_REQUEST
PointInTimeRecovery: true
TimeToLiveAttribute: ttl
GlobalSecondaryIndexes:
  GSI-status:
    PK: status (String)
    SK: created_at (String)
    Projection: ALL
  GSI-user:
    PK: owner_user_id (String)
    SK: created_at (String)
    Projection: ALL
```

### 4.3 `novelgen_audit_dev`
```yaml
PartitionKey: pk (String)           # DATE#YYYYMMDD
SortKey: sk (String)                # {timestamp}#{audit_id}
BillingMode: PAY_PER_REQUEST
PointInTimeRecovery: true
Encryption: AWS managed KMS
GlobalSecondaryIndexes:
  GSI-actor:
    PK: actor_user_id (String)
    SK: timestamp (String)
    Projection: ALL
# IAM 写锁：仅 novelgen-audit-write-role 可写；其他角色只读
```

### 4.4 `novelgen_config_dev`
```yaml
PartitionKey: pk (String)           # CONFIG | AGGREGATE#{date}#{team_id}
SortKey: sk (String)                # {type}#{version}
BillingMode: PAY_PER_REQUEST
```

---

## 5. S3 Buckets

```yaml
novelgen-novels-dev:
  Versioning: Enabled
  Lifecycle:
    - IntelligentTiering: applied to all
    - NoncurrentVersionExpiration: 90 days
  BlockPublicAccess: ALL
  Encryption: SSE-S3
  CorsRules: [GET from https://*.cloudfront.net]

novelgen-exports-dev:
  Versioning: Disabled
  Lifecycle:
    - Expiration: 30 days
  BlockPublicAccess: ALL
  Encryption: SSE-S3

novelgen-audit-archive-dev:
  Versioning: Enabled
  Lifecycle:
    - Transition(90d) → GLACIER_IR
    - Transition(365d) → DEEP_ARCHIVE
  Encryption: SSE-S3
  ObjectLockConfiguration: Governance mode, 7 years retention

novelgen-logs-dev:
  Lifecycle:
    - Expiration: 90 days
```

---

## 6. Step Functions ASL 骨架

### 6.1 AnalysisStateMachine（骨架由 U1 定义，U3 填充细节）
```json
{
  "Comment": "Novel analysis workflow: rough read -> parallel extract -> deep read -> memory write",
  "StartAt": "UpdateJobRunning",
  "States": {
    "UpdateJobRunning": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_jobs_dev",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, started_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":r": {"S": "RUNNING"}, ":t.$": "$$.State.EnteredTime"}
      },
      "Next": "EnqueueRoughRead"
    },
    "EnqueueRoughRead": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${AnalysisQueueUrl}",
        "MessageBody": {"task.$": "$", "taskToken.$": "$$.Task.Token"}
      },
      "TimeoutSeconds": 600,
      "Retry": [
        {"ErrorEquals": ["States.TaskFailed"], "IntervalSeconds": 2, "BackoffRate": 2.0, "MaxAttempts": 3}
      ],
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed", "ResultPath": "$.error"}],
      "Next": "ParallelExtract"
    },
    "ParallelExtract": {
      "Type": "Parallel",
      "Branches": [
        {"StartAt": "Classify", "States": {"Classify": {"Type": "Task", "Resource": "...", "End": true}}},
        {"StartAt": "ExtractCharacters", "States": {"ExtractCharacters": {"Type": "Task", "Resource": "...", "End": true}}},
        {"StartAt": "ExtractMap", "States": {"ExtractMap": {"Type": "Task", "Resource": "...", "End": true}}},
        {"StartAt": "AnalyzeStyle", "States": {"AnalyzeStyle": {"Type": "Task", "Resource": "...", "End": true}}}
      ],
      "Next": "DeepReadMap"
    },
    "DeepReadMap": {
      "Type": "Map",
      "ItemsPath": "$.chapters",
      "MaxConcurrencyPath": "$.concurrency.current",
      "ToleratedFailurePercentage": 5,
      "ItemProcessor": {
        "StartAt": "DeepReadChapter",
        "States": {"DeepReadChapter": {"Type": "Task", "Resource": "...", "End": true}}
      },
      "Next": "WriteMemory"
    },
    "WriteMemory": {"Type": "Task", "Resource": "...", "Next": "JobSucceeded"},
    "JobSucceeded": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_jobs_dev",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":r": {"S": "SUCCEEDED"}, ":t.$": "$$.State.EnteredTime"}
      },
      "End": true
    },
    "JobFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_jobs_dev",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t, error.$ = $.error",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":r": {"S": "FAILED"}, ":t.$": "$$.State.EnteredTime"}
      },
      "End": true
    }
  }
}
```

其他状态机（`ChapterStateMachine` / `OutlineStateMachine` / `ConsistencyStateMachine` / `IngestionStateMachine`）遵循相同的 `UpdateJobRunning → 业务 Task → UpdateJobSucceeded/Failed` 模板，由 U2/U3/U4/U5 填充具体 Task。

---

## 7. ECS 服务配置

### 7.1 Cluster
```yaml
Name: novelgen-cluster-dev
ContainerInsights: enabled
CapacityProviders: [FARGATE, FARGATE_SPOT]
DefaultCapacityProviderStrategy:
  - FARGATE: weight=1 (base=1)
```

### 7.2 Task Definitions（摘要）
| Service | CPU | Memory | Image | Port | Spot |
|---|---|---|---|---|---|
| frontend-user | 512 | 1024 | novelgen/frontend-user:latest | 3000 | no |
| frontend-admin | 256 | 512 | novelgen/frontend-admin:latest | 3001 | no |
| api-service | 1024 | 2048 | novelgen/api-service:latest | 8000 | no |
| worker-analysis | 2048 | 4096 | novelgen/worker-analysis:latest | - | yes |
| worker-generation | 2048 | 4096 | novelgen/worker-generation:latest | - | yes |
| worker-critic | 1024 | 2048 | novelgen/worker-critic:latest | - | yes |
| worker-consistency | 1024 | 2048 | novelgen/worker-consistency:latest | - | yes |
| worker-moderation | 1024 | 2048 | novelgen/worker-moderation:latest | - | yes |

### 7.3 Service Auto Scaling
```yaml
api-service:
  min=2, max=10
  policy: TargetTracking RequestCountPerTarget=50

frontend-user:
  min=2, max=6
  policy: TargetTracking CPUUtilization=60

worker-*:
  min=1, max=5
  policy: StepScaling on SQS ApproximateNumberOfMessagesVisible
    - ≥10: +1 task
    - ≥30: +2 tasks
    - <3 for 10min: -1 task
```

### 7.4 优雅停止
```yaml
StopTimeout: 30  # seconds
HealthCheck:
  path: /healthz
  interval: 30s
  timeout: 5s
  unhealthyThreshold: 3
Deregistration Delay: 30s
```

---

## 8. ALB + CloudFront

### 8.1 ALB Listener Rules（`novelgen-alb-dev`）
```yaml
Listener: HTTPS:443 (uses CF-origin cert)
Rules (from highest priority):
  1. host=admin.*.cloudfront.net, path=/api/v1/admin/* → api-service TG  (weight 100)
  2. host=admin.*.cloudfront.net, path=/*              → frontend-admin TG
  3. path=/api/v1/*                                     → api-service TG
  4. path=/healthz                                      → api-service TG (固定 200)
  5. path=/*                                            → frontend-user TG (含 BFF + SPA)
IdleTimeout: 600
```

### 8.2 CloudFront Distribution（2 个）

**User CloudFront** (`novelgen-user-dev`)：
```yaml
Aliases: []  # V1 用默认 *.cloudfront.net
Origin: novelgen-alb-dev
DefaultCacheBehavior:
  PathPattern: /*
  CachePolicy: Managed-CachingOptimized
  OriginRequestPolicy: Managed-AllViewerExceptHostHeader
CacheBehaviors:
  - PathPattern: /api/*
    CachePolicy: Managed-CachingDisabled
    OriginRequestPolicy: Managed-AllViewer
    AllowedMethods: [ALL]
  - PathPattern: /api/v1/jobs/*/stream
    CachePolicy: Managed-CachingDisabled
    OriginRequestPolicy: Managed-AllViewer
    ResponseHeadersPolicy: None
    ViewerProtocolPolicy: redirect-to-https
    # SSE 特殊配置：不缓存，透传 Last-Event-ID
Compress: true
MinTTL: 0
```

**Admin CloudFront** (`novelgen-admin-dev`)：
同上，Origin 路径映射到 `admin.*` host header。

### 8.3 WAF
```yaml
WebACL: novelgen-waf-dev
Rules:
  - AWSManagedRulesCommonRuleSet
  - AWSManagedRulesKnownBadInputsRuleSet
  - AWSManagedRulesAmazonIpReputationList
  - Custom: RateBasedRule 2000 req/5min per IP
Associations: [user-cloudfront, admin-cloudfront]
```

---

## 9. CDK Stack 划分（I3=B）

```
CDK App: novelgen-dev
├── 01-NetworkStack
│     ├── VPC, Subnets (public/private/isolated × 2AZ)
│     ├── NAT Gateway × 1
│     ├── VPC Endpoints (S3, DDB, Secrets, SSM, Logs, Bedrock, STS, ECR, Events)
│     └── Security Groups
│
├── 02-DataStack (depends on 01)
│     ├── DynamoDB × 4 (tenancy, jobs, audit, config)
│     ├── S3 Buckets × 4 (novels, exports, audit-archive, logs)
│     ├── Neptune Serverless Cluster
│     ├── OpenSearch Serverless Collection
│     ├── Secrets Manager (4 secrets)
│     └── SSM Parameter Store (10+ params)
│
├── 03-IdentityStack (depends on 01)
│     ├── Cognito User Pool + App Client
│     ├── Google/GitHub IdP
│     ├── PreSignUp Lambda
│     └── IAM Roles (ecs-exec, api-task, worker-tasks × 5, audit-write, audit-read, sfn, lambdas)
│
├── 04-MessagingStack (depends on 02, 03)
│     ├── SQS × 10 (5 queues + 5 DLQs)
│     ├── EventBridge Rules
│     ├── EventBridge Scheduler (daily-aggregator, daily-archiver)
│     └── Step Functions × 5 State Machines (骨架)
│
├── 05-ComputeStack (depends on 01, 02, 03, 04)
│     ├── ECS Cluster
│     ├── ECR Repositories × 8
│     ├── ECS TaskDefinitions × 8
│     ├── ECS Services × 8 (with Auto Scaling)
│     └── ALB + Target Groups + Listener Rules
│
├── 06-EdgeStack (depends on 05)
│     ├── CloudFront Distribution × 2 (user, admin)
│     └── WAF WebACL
│
├── 07-ObservabilityStack (depends on 02, 05)
│     ├── CloudWatch Log Groups × 10
│     ├── Metric Filters × 5
│     ├── CloudWatch Alarms × 10
│     ├── SNS Topic (admin-alerts)
│     ├── daily-cost-aggregator Lambda
│     ├── daily-audit-archiver Lambda
│     └── Cost Anomaly Detection Monitor
│
└── 08-AgentCoreStack (depends on 02, 03)
      ├── AgentCore Memory configuration
      ├── AgentCore Gateway (工具骨架)
      ├── AgentCore Browser
      ├── AgentCore Identity
      ├── AgentCore Observability project
      └── AgentCore Runtime registration
```

**部署命令**：
```bash
cdk deploy --all                     # 全量部署（首次或大规模变更）
cdk deploy NovelgenNetworkStack      # 单 stack 部署
```

---

## 10. Cost Anomaly & Budgets

```yaml
CostAnomalyMonitor:
  Name: novelgen-cost-monitor-dev
  MonitorType: DIMENSIONAL
  MonitorDimension: SERVICE

CostAnomalySubscription:
  Threshold: 20% deviation
  Frequency: DAILY
  Recipient: SNS topic novelgen-admin-alerts-dev

Budget:
  Name: novelgen-monthly-budget-dev
  Amount: USD 2000
  Alerts:
    - Threshold 80%  → SNS
    - Threshold 100% → SNS
```

---

## 11. CI/CD 基础设施

### 11.1 GitHub Actions Secrets（OIDC，不使用长期 AK/SK）
配置 GitHub OIDC 身份提供商到 AWS IAM；GitHub Actions 通过 AssumeRoleWithWebIdentity 获得临时凭证。

```yaml
IAM Role: novelgen-github-ci-role-dev
TrustPolicy: repo owner/novel-generation refs/heads/main & refs/heads/develop
Permissions:
  - ECR push
  - S3 put (CDK bootstrap bucket)
  - CloudFormation read
```

### 11.2 ECR Repositories
所有 8 个仓库配置：
```yaml
ImageScanOnPush: true
ImageTagMutability: IMMUTABLE (prod) / MUTABLE (dev)
LifecyclePolicy:
  - 保留最近 20 个 tag
  - 移除 untagged 30 天后
```

---

## 12. 健康检查与就绪

### 12.1 Endpoint
所有 ECS Service 暴露 `/healthz`：
- 200 OK + `{"status":"ok","version":"...","uptime_seconds":...}`
- 失败返回 503

### 12.2 就绪条件
- API：DynamoDB reachable + Cognito JWKs 已加载
- Worker：SQS reachable + Bedrock reachable
- Frontend：BFF reachable

---

## 13. Deployment Size Estimate

| Stack | 资源数 | CDK 部署时间估算 |
|---|---|---|
| NetworkStack | ~20 | ~3 min |
| DataStack | ~30 | ~10 min（Neptune + OpenSearch 慢） |
| IdentityStack | ~15 | ~2 min |
| MessagingStack | ~25 | ~3 min |
| ComputeStack | ~30 | ~5 min |
| EdgeStack | ~5 | ~15 min（CloudFront 慢） |
| ObservabilityStack | ~30 | ~2 min |
| AgentCoreStack | ~10 | ~3 min（Custom Resources）|
| **总计** | **~165** | **~43 min 首次全量部署** |
