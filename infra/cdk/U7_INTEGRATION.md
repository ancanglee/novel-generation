# U7 Integration Notes

U7 (Admin Frontend + API) adds resources by mutating existing U1 stacks via
helpers in `shared_constructs/u7_extensions.py`.

## 1. Wiring snippets

### `stacks/data_stack.py`
```python
from shared_constructs.u7_extensions import extend_data_stack as apply_u7_data
apply_u7_data(self, cfg, novels_bucket=self.novels_bucket)
```

### `stacks/identity_stack.py`
```python
from shared_constructs.u7_extensions import extend_identity_stack as apply_u7_identity
apply_u7_identity(
    self, cfg,
    api_service_role=self.api_task_role,
    audit_events_table=data.audit_events_table,
    cognito_user_pool=self.user_pool,
)
```

### `stacks/edge_stack.py`
```python
from shared_constructs.u7_extensions import extend_edge_stack as apply_u7_edge
apply_u7_edge(self, cfg, distribution=self.cloudfront, novels_bucket=data.novels_bucket)
```

### `stacks/observability_stack.py`
```python
from shared_constructs.u7_extensions import extend_observability_stack as apply_u7_obs
apply_u7_obs(self, cfg, alerts_topic=self.alerts_topic)
```

---

## 2. Expected `cdk diff`

- `AWS::CloudFront::Distribution` (+1 behavior `/admin/*`)
- `AWS::S3::Bucket` policy / lifecycle (+1 lifecycle rule for `admin/`)
- `AWS::IAM::Policy` (+3 statements on api-service role: Deny audit / CloudWatch / Cognito admin)
- `AWS::CloudWatch::Alarm` × 3

Deploy time: ~4 minutes.

---

## 3. Frontend deployment

```bash
pnpm --filter @novelgen/frontend-admin build
aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-${ENV}/admin/ \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "index.html"
aws s3 cp apps/frontend-admin/dist/index.html \
    s3://novels-raw-${ENV}/admin/index.html \
    --cache-control "no-cache, must-revalidate"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/admin/index.html"
```

---

## 4. Cognito admin user bootstrap

U7 does **not** provision the Admin User Pool Group (I3=C, deferred to V2).
To grant admin access, set the following custom attribute on the target user
via AWS CLI or Console:

```
custom:global_role = admin
```

The `@require_admin_role` dependency validates this claim on every `/admin/*`
request.

---

## 5. Security baseline summary

Current admin defense layers:
1. Cognito JWT `custom:global_role` claim (KMS-signed, tamper-evident)
2. ApiService `@require_admin_role` FastAPI dependency (403 gate)
3. DDB `audit_events` IAM Deny UpdateItem/DeleteItem/BatchWriteItem (runtime immutability)

Deferred (V2):
- Admin Group + MFA enforcement (I3=C)
- S3 Object Lock for audit archives (I2=C)
- PII masking middleware (D4=C)
- Budget / cost guardrail (F6=C)

Operational mitigations recommended for V1:
- Keep admin user count ≤ 5
- Rotate admin passwords quarterly
- Enable CloudTrail alarm on `cognito-idp:AdminAddUserToGroup`
