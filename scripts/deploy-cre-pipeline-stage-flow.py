#!/usr/bin/env python3
"""Deploy deal pipeline stage-change automation flow."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
FLOW_CONFIG_PATH = ROOT / "config" / "cre-pipeline-stage-flow.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_clientdata(config: dict[str, Any]) -> dict[str, Any]:
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    dataverse_ref = config["connectionReferences"]["dataverse"]["logicalName"]
    due_days = config.get("taskDefaults", {}).get("dueInDays", 2)
    priority = config.get("taskDefaults", {}).get("priorityCode", 2)

    triggers = {
        "When_a_row_is_added,_modified_or_deleted": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "host": {
                    "connectionName": "shared_commondataserviceforapps",
                    "operationId": "SubscribeWebhookTrigger",
                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                },
                "parameters": {
                    "subscriptionRequest/message": 4,
                    "subscriptionRequest/entityname": "opportunity",
                    "subscriptionRequest/scope": 4,
                    "subscriptionRequest/filteringattributes": "cre_pipelinestage",
                },
                "authentication": "@parameters('$authentication')",
            },
        }
    }

    actions = {
        "Stage_changed": {
            "type": "If",
            "expression": {
                "and": [
                    {
                        "not": {
                            "equals": [
                                "@triggerOutputs()?['body/cre_pipelinestage']",
                                "@null",
                            ]
                        }
                    }
                ]
            },
            "actions": {
                "Create_stage_task": {
                    "type": "OpenApiConnection",
                    "inputs": {
                        "host": {
                            "connectionName": "shared_commondataserviceforapps",
                            "operationId": "CreateRecord",
                            "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                        },
                        "parameters": {
                            "entityName": "tasks",
                            "item/subject": "@concat('Deal stage updated: ', coalesce(triggerOutputs()?['body/name'], 'Opportunity'))",
                            "item/description": "@concat('Pipeline stage changed for opportunity. Review next actions for this deal.', decodeUriComponent('%0A%0A'), 'Stage value: ', string(triggerOutputs()?['body/cre_pipelinestage']))",
                            "item/scheduledend": f"@addDays(utcNow(), {due_days})",
                            "item/prioritycode": priority,
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                }
            },
            "else": {"actions": {}},
            "runAfter": {},
        }
    }

    definition = flow_deploy.flow_definition_skeleton(actions, triggers)
    return {
        "properties": {
            "connectionReferences": {
                "shared_commondataserviceforapps": {
                    "runtimeSource": "embedded",
                    "connection": {"connectionReferenceLogicalName": dataverse_ref},
                    "api": {"name": "shared_commondataserviceforapps"},
                },
            },
            "definition": definition,
        },
        "schemaVersion": "1.0.0.0",
    }


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    config = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    base_client = deploy.DataverseClient(environment_url, token)
    solution_name = metadata["solution"]["name"]
    client = flow_deploy.FlowClient(base_client, solution_name)

    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")

    flow_deploy.ensure_connection_references(client, solution_name, config["connectionReferences"])
    flow_meta = config["flow"]
    workflow_id = flow_deploy.deploy_workflow(
        client,
        solution_name,
        flow_meta["name"],
        flow_meta.get("description", flow_meta["name"]),
        build_clientdata(config),
    )
    print(f"\nPipeline stage flow deployed (draft). Flow id: {workflow_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
