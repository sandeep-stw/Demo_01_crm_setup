#!/usr/bin/env python3
"""Deploy the CRE email-to-lead Power Automate cloud flow."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
FLOW_CONFIG_PATH = ROOT / "config" / "cre-email-lead-flow.json"

COMPONENT_WORKFLOW = 29
COMPONENT_CONNECTION_REFERENCE = 371


def load_deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def build_clientdata(config: dict[str, Any]) -> dict[str, Any]:
    outlook_ref = config["connectionReferences"]["outlook"]["logicalName"]
    dataverse_ref = config["connectionReferences"]["dataverse"]["logicalName"]
    mailbox = config["mailbox"]
    subject_filter = config["trigger"]["subjectFilter"]
    lead_source = config.get("lead", {}).get("leadSourceCode", 1)

    if mailbox.get("type") == "shared":
        trigger_name = "When_a_new_email_arrives_in_a_shared_mailbox_(V2)"
        trigger_operation = "SharedMailboxOnNewEmailV2"
        trigger_parameters = {
            "mailboxAddress": mailbox["address"],
            "folderPath": mailbox.get("folderPath", "Inbox"),
            "subjectFilter": subject_filter,
            "includeAttachments": False,
        }
    else:
        trigger_name = "When_a_new_email_arrives_(V3)"
        trigger_operation = "OnNewEmailV3"
        trigger_parameters = {
            "folderPath": mailbox.get("folderPath", "Inbox"),
            "subjectFilter": subject_filter,
            "includeAttachments": False,
        }

    return {
        "properties": {
            "connectionReferences": {
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
            },
            "definition": {
                "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
                "contentVersion": "1.0.0.0",
                "parameters": {
                    "$connections": {"defaultValue": {}, "type": "Object"},
                    "$authentication": {"defaultValue": {}, "type": "SecureObject"},
                },
                "triggers": {
                    trigger_name: {
                        "type": "OpenApiConnectionNotification",
                        "inputs": {
                            "host": {
                                "connectionName": "shared_office365",
                                "operationId": trigger_operation,
                                "apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
                            },
                            "parameters": trigger_parameters,
                            "authentication": "@parameters('$authentication')",
                        },
                        "splitOn": "@triggerBody()?['value']",
                    }
                },
                "actions": {
                    "Subject_contains_new_lead": {
                        "actions": {
                            "Create_a_new_lead": {
                                "type": "OpenApiConnection",
                                "inputs": {
                                    "host": {
                                        "connectionName": "shared_commondataserviceforapps",
                                        "operationId": "CreateRecord",
                                        "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                                    },
                                    "parameters": {
                                        "entityName": "leads",
                                        "item/subject": "@coalesce(triggerBody()?['subject'], triggerBody()?['Subject'], 'New lead from email')",
                                        "item/description": "@concat('Lead created automatically from email received at ', '{mailbox['address']}', '.', decodeUriComponent('%0A%0A'), 'From: ', coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), decodeUriComponent('%0A'), 'Body preview: ', coalesce(triggerBody()?['bodyPreview'], triggerBody()?['BodyPreview'], ''))",
                                        "item/emailaddress1": "@if(contains(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), trim(substring(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), add(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), 1), sub(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '>'), add(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), 1)))), coalesce(triggerBody()?['from'], triggerBody()?['From'], ''))",
                                        "item/leadsourcecode": lead_source,
                                    },
                                    "authentication": "@parameters('$authentication')",
                                },
                            }
                        },
                        "runAfter": {},
                        "else": {"actions": {}},
                        "expression": {
                            "and": [
                                {
                                    "contains": [
                                        "@toLower(coalesce(triggerBody()?['subject'], triggerBody()?['Subject'], ''))",
                                        "new lead",
                                    ]
                                }
                            ]
                        },
                        "type": "If",
                    }
                },
            },
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


def upsert_connection_reference(client: FlowClient, solution_name: str, key: str, definition: dict[str, str]) -> str:
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
            print(f"  Connection reference created in solution context: {logical_name}")
        else:
            raise
    return ref_id


def find_workflow(client: FlowClient, name: str) -> str | None:
    escaped = name.replace("'", "''")
    for path in (
        "workflows?" + urllib.parse.urlencode({"$filter": f"name eq '{escaped}' and category eq 5", "$select": "workflowid,name,statecode", "$top": "1"}),
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


def deploy_email_lead_flow(client: FlowClient, solution_name: str, config: dict[str, Any]) -> str:
    flow = config["flow"]
    clientdata = build_clientdata(config)
    clientdata_text = json.dumps(clientdata, separators=(",", ":"))

    print("Ensuring connection references...")
    for key in ("outlook", "dataverse"):
        upsert_connection_reference(client, solution_name, key, config["connectionReferences"][key])

    existing_id = find_workflow(client, flow["name"])
    payload = {
        "category": 5,
        "name": flow["name"],
        "type": 1,
        "primaryentity": "none",
        "description": flow.get("description", flow["name"]),
        "clientdata": clientdata_text,
    }

    if existing_id:
        client.patch(f"workflows({existing_id})", {"clientdata": clientdata_text, "description": payload["description"]})
        workflow_id = existing_id
        print(f"  Updated flow: {flow['name']}")
    else:
        result = client.post("workflows", payload)
        workflow_id = FlowClient.parse_entity_id(result, "workflows")
        print(f"  Created flow: {flow['name']} ({workflow_id})")

    add_solution_component(client, solution_name, workflow_id, COMPONENT_WORKFLOW, flow["name"])
    return workflow_id


def main() -> int:
    deploy = load_deploy_module()
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    config = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    base_client = deploy.DataverseClient(environment_url, token)
    solution_name = metadata["solution"]["name"]
    client = FlowClient(base_client, solution_name)

    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")

    workflow_id = deploy_email_lead_flow(client, solution_name, config)
    print("\nFlow deployed in draft state.")
    print("Next steps (one-time in Power Automate):")
    print("  1. Open Solutions > CRE Relationship Management > CRE - Email New Lead to CRM")
    print("  2. Edit the flow and sign in to the Office 365 Outlook and Dataverse connections")
    print("  3. Save and turn the flow On")
    print(f"  Flow id: {workflow_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
