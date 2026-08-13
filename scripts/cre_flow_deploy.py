#!/usr/bin/env python3
"""Shared helpers for deploying Power Automate cloud flows to Dataverse."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

COMPONENT_WORKFLOW = 29
COMPONENT_CONNECTION_REFERENCE = 371


class FlowClient:
    def __init__(self, base_client: Any, solution_name: str) -> None:
        self._client = base_client
        self.base_url = base_client.base_url
        self.headers = dict(base_client.headers)
        self.headers["MSCRM.SolutionUniqueName"] = solution_name

    def get(self, path: str) -> Any:
        return self._client.get(path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, payload)

    def patch(self, path: str, payload: dict[str, Any]) -> None:
        self._request("PATCH", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
                entity_id = response.headers.get("OData-EntityId")
                parsed = json.loads(body) if body else None
                if entity_id:
                    return {"_entity_id": entity_id, "body": parsed}
                return parsed
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed ({error.code}): {detail}") from error

    @staticmethod
    def parse_entity_id(result: Any, entity_set: str) -> str:
        if isinstance(result, dict) and "_entity_id" in result:
            match = re.search(rf"{entity_set}\(([^)]+)\)", result["_entity_id"])
            if match:
                return match.group(1).strip("'")
        raise RuntimeError(f"Could not parse entity id for {entity_set}: {result}")


def connection_references_block(outlook_ref: str, dataverse_ref: str) -> dict[str, Any]:
    return {
        "shared_office365": {
            "runtimeSource": "embedded",
            "connection": {"connectionReferenceLogicalName": outlook_ref},
            "api": {"name": "shared_office365"},
        },
        "shared_commondataserviceforapps": {
            "runtimeSource": "embedded",
            "connection": {"connectionReferenceLogicalName": dataverse_ref},
            "api": {"name": "shared_commondataserviceforapps"},
        },
    }


def flow_definition_skeleton(actions: dict[str, Any], triggers: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$connections": {"defaultValue": {}, "type": "Object"},
            "$authentication": {"defaultValue": {}, "type": "SecureObject"},
        },
        "triggers": triggers,
        "actions": actions,
    }


def wrap_clientdata(
    outlook_ref: str,
    dataverse_ref: str,
    definition: dict[str, Any],
) -> dict[str, Any]:
    return {
        "properties": {
            "connectionReferences": connection_references_block(outlook_ref, dataverse_ref),
            "definition": definition,
        },
        "schemaVersion": "1.0.0.0",
    }


def add_solution_component(
    client: FlowClient,
    solution_name: str,
    component_id: str,
    component_type: int,
    label: str,
) -> None:
    payload = {
        "ComponentId": component_id,
        "ComponentType": component_type,
        "SolutionUniqueName": solution_name,
        "AddRequiredComponents": False,
    }
    try:
        client.post("AddSolutionComponent", payload)
        print(f"  Added to solution: {label}")
    except RuntimeError as error:
        message = str(error)
        if "0x80071151" in message or "already a member" in message.lower():
            print(f"  Already in solution: {label}")
            return
        raise


def upsert_connection_reference(
    client: FlowClient,
    solution_name: str,
    definition: dict[str, str],
) -> str:
    logical_name = definition["logicalName"]
    existing = client.get(
        "connectionreferences?"
        + urllib.parse.urlencode(
            {
                "$filter": f"connectionreferencelogicalname eq '{logical_name}'",
                "$select": "connectionreferenceid,connectionreferencelogicalname",
                "$top": "1",
            }
        )
    )
    rows = existing.get("value", [])
    if rows:
        ref_id = rows[0]["connectionreferenceid"]
        print(f"  Connection reference exists: {logical_name}")
    else:
        payload = {
            "connectionreferencelogicalname": logical_name,
            "connectionreferencedisplayname": definition["displayName"],
            "connectorid": definition["connectorId"],
            "description": definition.get("description", definition["displayName"]),
        }
        result = client.post("connectionreferences", payload)
        ref_id = FlowClient.parse_entity_id(result, "connectionreferences")
        print(f"  Created connection reference: {logical_name}")
    try:
        add_solution_component(client, solution_name, ref_id, COMPONENT_CONNECTION_REFERENCE, logical_name)
    except RuntimeError as error:
        if "msdyn_Connector" in str(error):
            print(f"  Connection reference in solution context: {logical_name}")
        else:
            raise
    return ref_id


def find_workflow(client: FlowClient, name: str) -> str | None:
    escaped = name.replace("'", "''")
    for path in (
        "workflows?"
        + urllib.parse.urlencode(
            {
                "$filter": f"name eq '{escaped}' and category eq 5",
                "$select": "workflowid,name,statecode",
                "$top": "1",
            }
        ),
        "workflows/Microsoft.Dynamics.CRM.RetrieveUnpublishedMultiple()?$select=workflowid,name,statecode,category",
    ):
        try:
            result = client.get(path)
            for row in result.get("value", []):
                if row.get("name") == name and row.get("category", 5) == 5:
                    return row["workflowid"]
        except RuntimeError:
            continue
    return None


def deploy_workflow(
    client: FlowClient,
    solution_name: str,
    name: str,
    description: str,
    clientdata: dict[str, Any],
) -> str:
    clientdata_text = json.dumps(clientdata, separators=(",", ":"))
    existing_id = find_workflow(client, name)
    payload = {
        "category": 5,
        "name": name,
        "type": 1,
        "primaryentity": "none",
        "description": description,
        "clientdata": clientdata_text,
    }
    if existing_id:
        client.patch(
            f"workflows({existing_id})",
            {"clientdata": clientdata_text, "description": description},
        )
        workflow_id = existing_id
        print(f"  Updated flow: {name}")
    else:
        result = client.post("workflows", payload)
        workflow_id = FlowClient.parse_entity_id(result, "workflows")
        print(f"  Created flow: {name} ({workflow_id})")
    add_solution_component(client, solution_name, workflow_id, COMPONENT_WORKFLOW, name)
    return workflow_id


def ensure_connection_references(
    client: FlowClient,
    solution_name: str,
    connection_references: dict[str, dict[str, str]],
) -> None:
    print("Ensuring connection references...")
    for definition in connection_references.values():
        upsert_connection_reference(client, solution_name, definition)
