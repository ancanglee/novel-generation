"""Neptune openCypher HTTP client with self-signed SigV4 (I3=A)."""

from __future__ import annotations

import json
from typing import Any

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class NeptuneSignedClient:
    """POST openCypher queries to a Neptune Serverless endpoint with SigV4."""

    def __init__(self, endpoint: str, region: str = "us-east-1") -> None:
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"https://{endpoint}"
        self._endpoint = endpoint.rstrip("/")
        self._region = region
        self._session = boto3.Session()
        self._http = httpx.AsyncClient(
            timeout=30.0, limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

    async def close(self) -> None:
        await self._http.aclose()

    def _sign(self, url: str, method: str, body: str) -> dict[str, str]:
        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("no AWS credentials available for Neptune SigV4 signing")
        creds = credentials.get_frozen_credentials()
        req = AWSRequest(
            method=method, url=url, data=body, headers={"Content-Type": "application/json"}
        )
        SigV4Auth(creds, "neptune-db", self._region).add_auth(req)
        return dict(req.headers)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def execute_opencypher(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self._endpoint}/openCypher"
        body = json.dumps({"query": query, "parameters": parameters or {}})
        headers = self._sign(url, "POST", body)
        resp = await self._http.post(url, content=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def upsert_node(
        self,
        label: str,
        team_id: str,
        novel_id: str,
        node_id: str,
        properties: dict[str, Any],
    ) -> None:
        query = (
            f"MERGE (n:{label} {{team_id: $tid, novel_id: $nid, node_id: $node_id}}) "
            "SET n += $props"
        )
        await self.execute_opencypher(
            query,
            {"tid": team_id, "nid": novel_id, "node_id": node_id, "props": properties},
        )

    async def upsert_edge(
        self,
        from_label: str,
        to_label: str,
        edge_type: str,
        team_id: str,
        novel_id: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        query = (
            f"MATCH (a:{from_label} {{team_id: $tid, novel_id: $nid, node_id: $from_id}}) "
            f"MATCH (b:{to_label} {{team_id: $tid, novel_id: $nid, node_id: $to_id}}) "
            f"MERGE (a)-[r:{edge_type}]->(b) SET r += $props"
        )
        await self.execute_opencypher(
            query,
            {
                "tid": team_id,
                "nid": novel_id,
                "from_id": from_id,
                "to_id": to_id,
                "props": properties or {},
            },
        )

    async def neighbors(
        self,
        team_id: str,
        novel_id: str,
        node_id: str,
        edge_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if edge_type:
            query = (
                "MATCH (n {team_id: $tid, novel_id: $nid, node_id: $node_id})"
                f"-[r:{edge_type}]-(neighbor) "
                "RETURN neighbor, r LIMIT $limit"
            )
        else:
            query = (
                "MATCH (n {team_id: $tid, novel_id: $nid, node_id: $node_id})-[r]-(neighbor) "
                "RETURN neighbor, r LIMIT $limit"
            )
        result = await self.execute_opencypher(
            query,
            {"tid": team_id, "nid": novel_id, "node_id": node_id, "limit": limit},
        )
        return result.get("results", [])
