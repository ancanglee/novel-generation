# U6 Integration Notes

U6 (Frontend + BFF) adds resources by mutating existing U1 stacks via helpers in
`shared_constructs/u6_extensions.py`.

---

## 1. Wiring snippets

### `stacks/data_stack.py`
```python
from shared_constructs.u6_extensions import extend_data_stack as apply_u6_data
apply_u6_data(self, cfg, novels_bucket=self.novels_bucket)
```

### `stacks/identity_stack.py`
```python
from shared_constructs.u6_extensions import extend_identity_stack as apply_u6_identity

self.bff_task_role = iam.Role(self, "U6BffTaskRole",
    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))
self.bff_session_secret = secrets.Secret(self, "U6BffSessionKey",
    secret_name=f"{cfg.prefix}-bff-session-signing-key",
    generate_secret_string=secrets.SecretStringGenerator(
        password_length=48,
        exclude_punctuation=True,
    ),
)
apply_u6_identity(
    self, cfg,
    bff_task_role=self.bff_task_role,
    session_signing_secret=self.bff_session_secret,
    cognito_user_pool_arn=self.user_pool.user_pool_arn,
)
```

### `stacks/compute_stack.py`
```python
from shared_constructs.u6_extensions import extend_compute_stack
service, bff_tg = extend_compute_stack(
    self, cfg,
    cluster=self.cluster,
    vpc=network.vpc,
    alb_listener=edge.https_listener,
    bff_ecr_repo=self.ecr_repos["bff-user"],
    bff_task_role=identity.bff_task_role,
    execution_role=self.task_execution_role,
    session_signing_secret=identity.bff_session_secret,
    api_base_url="https://internal-api.svc.novelgen.local",
    cognito_user_pool_id=identity.user_pool.user_pool_id,
    cognito_app_client_id=identity.app_client.user_pool_client_id,
    cognito_domain=identity.cognito_domain,
    app_base_url=f"https://app.{cfg.public_domain}",
)
self.u6_bff_service = service
self.u6_bff_tg = bff_tg
```

### `stacks/edge_stack.py`
```python
from shared_constructs.u6_extensions import extend_edge_stack
extend_edge_stack(
    self, cfg,
    distribution=self.cloudfront,
    novels_bucket=data.novels_bucket,
    alb=self.alb,
)
```

### `stacks/observability_stack.py`
```python
from shared_constructs.u6_extensions import extend_observability_stack
extend_observability_stack(
    self, cfg,
    alerts_topic=self.alerts_topic,
    bff_tg=compute.u6_bff_tg,
)
```

---

## 2. ALB global setting

The ALB's idle timeout must be raised from 60s → 900s to accommodate SSE long
connections used by U4/U5 streaming via BFF:

```python
self.alb.set_attribute("idle_timeout.timeout_seconds", "900")
```

---

## 3. Required env additions (ComputeStack)

- **bff-user** env vars are wired entirely by `extend_compute_stack`.
- **api-service** env unchanged (BFF calls it as downstream).

---

## 4. Frontend static asset deployment

Frontend build output lands at `s3://novels-raw-{env}/frontend/` (I2=A):
```bash
pnpm --filter @novelgen/frontend-user build
aws s3 sync apps/frontend-user/dist/ s3://novels-raw-${ENV}/frontend/ \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "index.html"
aws s3 cp apps/frontend-user/dist/index.html \
    s3://novels-raw-${ENV}/frontend/index.html \
    --cache-control "no-cache, must-revalidate"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/index.html"
```

---

## 5. Expected `cdk diff`

- `AWS::CloudFront::Distribution` (+3 behaviors)
- `AWS::ECS::Service` (new `bff-user`)
- `AWS::ECS::TaskDefinition` (new)
- `AWS::ElasticLoadBalancingV2::TargetGroup` + 2 ListenerRules
- `AWS::SecretsManager::Secret` (BFF session key)
- `AWS::IAM::Policy` updates
- `AWS::CloudWatch::Alarm` ×5
- `AWS::S3::BucketPolicy` (+ frontend prefix OAC grant)
- `AWS::ApplicationAutoScaling::ScalableTarget` + `ScalingPolicy`

Deploy time: ~7 minutes.
