#!/usr/bin/env python3
"""Deploy Phase 3 Outlook Power Automate flows (calendar logging + unknown sender alerts)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
OUTLOOK_CONFIG_PATH = ROOT / "config" / "cre-outlook-workflows.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_unknown_sender_flow(config: dict[str, Any]) -> dict[str, Any]:
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    outlook_ref = config["connectionReferences"]["outlook"]["logicalName"]
    dataverse_ref = config["connectionReferences"]["dataverse"]["logicalName"]
    mailbox = config["mailbox"]
    task_defaults = config.get("taskDefaults", {})

    if mailbox.get("type") == "shared":
        trigger_name = "When_a_new_email_arrives_in_a_shared_mailbox_(V2)"
        trigger_operation = "SharedMailboxOnNewEmailV2"
        trigger_parameters = {
            "mailboxAddress": mailbox["address"],
            "folderPath": mailbox.get("folderPath", "Inbox"),
            "includeAttachments": False,
        }
    else:
        trigger_name = "When_a_new_email_arrives_(V3)"
        trigger_operation = "OnNewEmailV3"
        trigger_parameters = {
            "folderPath": mailbox.get("folderPath", "Inbox"),
            "includeAttachments": False,
        }

    due_days = task_defaults.get("dueInDays", 1)
    priority = task_defaults.get("priorityCode", 2)

    triggers = {
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
    }

    actions = {
        "Sender_email": {
            "type": "Compose",
            "inputs": "@if(contains(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), toLower(trim(substring(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), add(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), 1), sub(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '>'), add(indexOf(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''), '<'), 1))))), toLower(trim(coalesce(triggerBody()?['from'], triggerBody()?['From'], ''))))",
            "runAfter": {},
        },
        "List_matching_contacts": {
            "type": "OpenApiConnection",
            "inputs": {
                "host": {
                    "connectionName": "shared_commondataserviceforapps",
                    "operationId": "ListRecords",
                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                },
                "parameters": {
                    "entityName": "contacts",
                    "$filter": "statecode eq 0 and (emailaddress1 eq '@{outputs('Sender_email')}' or emailaddress2 eq '@{outputs('Sender_email')}' or emailaddress3 eq '@{outputs('Sender_email')}')",
                    "$top": 1,
                },
                "authentication": "@parameters('$authentication')",
            },
            "runAfter": {"Sender_email": ["Succeeded"]},
        },
        "List_matching_leads": {
            "type": "OpenApiConnection",
            "inputs": {
                "host": {
                    "connectionName": "shared_commondataserviceforapps",
                    "operationId": "ListRecords",
                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                },
                "parameters": {
                    "entityName": "leads",
                    "$filter": "statecode eq 0 and emailaddress1 eq '@{outputs('Sender_email')}'",
                    "$top": 1,
                },
                "authentication": "@parameters('$authentication')",
            },
            "runAfter": {"List_matching_contacts": ["Succeeded"]},
        },
        "Sender_not_in_CRM": {
            "type": "If",
            "expression": {
                "and": [
                    {
                        "equals": [
                            "@length(coalesce(body('List_matching_contacts')?['value'], json('[]')))",
                            0,
                        ]
                    },
                    {
                        "equals": [
                            "@length(coalesce(body('List_matching_leads')?['value'], json('[]')))",
                            0,
                        ]
                    },
                ]
            },
            "actions": {
                "Create_review_task": {
                    "type": "OpenApiConnection",
                    "inputs": {
                        "host": {
                            "connectionName": "shared_commondataserviceforapps",
                            "operationId": "CreateRecord",
                            "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                        },
                        "parameters": {
                            "entityName": "tasks",
                            "item/subject": "@concat('Unknown sender - review email from ', outputs('Sender_email'))",
                            "item/description": "@concat('An email arrived from a sender not found in CRM contacts or leads.', decodeUriComponent('%0A%0A'), 'Subject: ', coalesce(triggerBody()?['subject'], triggerBody()?['Subject'], ''), decodeUriComponent('%0A'), 'Preview: ', coalesce(triggerBody()?['bodyPreview'], triggerBody()?['BodyPreview'], ''), decodeUriComponent('%0A%0A'), 'Open App for Outlook to create a contact from the email signature.')",
                            "item/scheduledend": f"@addDays(utcNow(), {due_days})",
                            "item/prioritycode": priority,
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                }
            },
            "else": {"actions": {}},
            "runAfter": {"List_matching_leads": ["Succeeded"]},
        },
    }

    definition = flow_deploy.flow_definition_skeleton(actions, triggers)
    return flow_deploy.wrap_clientdata(outlook_ref, dataverse_ref, definition)


def build_calendar_log_flow(config: dict[str, Any]) -> dict[str, Any]:
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    outlook_ref = config["connectionReferences"]["outlook"]["logicalName"]
    dataverse_ref = config["connectionReferences"]["dataverse"]["logicalName"]

    triggers = {
        "When_an_event_is_added,_updated_or_deleted_(V3)": {
            "type": "OpenApiConnectionNotification",
            "inputs": {
                "host": {
                    "connectionName": "shared_office365",
                    "operationId": "OnCalendarEventV3",
                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
                },
                "parameters": {
                    "table": "Calendar",
                },
                "authentication": "@parameters('$authentication')",
            },
            "splitOn": "@triggerBody()?['value']",
        }
    }

    actions = {
        "Event_is_accepted": {
            "type": "If",
            "expression": {
                "or": [
                    {
                        "equals": [
                            "@toLower(coalesce(triggerBody()?['responseType'], triggerBody()?['ResponseType'], ''))",
                            "accepted",
                        ]
                    },
                    {
                        "equals": [
                            "@toLower(coalesce(triggerBody()?['showAs'], triggerBody()?['ShowAs'], ''))",
                            "busy",
                        ]
                    },
                ]
            },
            "actions": {
                "Required_attendees": {
                    "type": "Compose",
                    "inputs": "@coalesce(triggerBody()?['requiredAttendees'], triggerBody()?['RequiredAttendees'], '')",
                },
                "Optional_attendees": {
                    "type": "Compose",
                    "inputs": "@coalesce(triggerBody()?['optionalAttendees'], triggerBody()?['OptionalAttendees'], '')",
                    "runAfter": {"Required_attendees": ["Succeeded"]},
                },
                "Attendee_emails": {
                    "type": "Compose",
                    "inputs": "@concat(outputs('Required_attendees'), ';', outputs('Optional_attendees'))",
                    "runAfter": {"Optional_attendees": ["Succeeded"]},
                },
                "List_attendee_contacts": {
                    "type": "OpenApiConnection",
                    "inputs": {
                        "host": {
                            "connectionName": "shared_commondataserviceforapps",
                            "operationId": "ListRecords",
                            "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                        },
                        "parameters": {
                            "entityName": "contacts",
                            "$filter": "statecode eq 0 and (contains('@{outputs('Attendee_emails')}', emailaddress1) or contains('@{outputs('Attendee_emails')}', emailaddress2) or contains('@{outputs('Attendee_emails')}', emailaddress3))",
                            "$top": 5,
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                    "runAfter": {"Attendee_emails": ["Succeeded"]},
                },
                "For_each_contact": {
                    "type": "Foreach",
                    "foreach": "@coalesce(body('List_attendee_contacts')?['value'], json('[]'))",
                    "actions": {
                        "Create_appointment": {
                            "type": "OpenApiConnection",
                            "inputs": {
                                "host": {
                                    "connectionName": "shared_commondataserviceforapps",
                                    "operationId": "CreateRecord",
                                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                                },
                                "parameters": {
                                    "entityName": "appointments",
                                    "item/subject": "@coalesce(triggerBody()?['subject'], triggerBody()?['Subject'], 'Outlook meeting')",
                                    "item/description": "@concat('Logged from accepted Outlook calendar event.', decodeUriComponent('%0A%0A'), coalesce(triggerBody()?['bodyPreview'], triggerBody()?['bodyPreview'], ''))",
                                    "item/scheduledstart": "@coalesce(triggerBody()?['start'], triggerBody()?['Start'])",
                                    "item/scheduledend": "@coalesce(triggerBody()?['end'], triggerBody()?['End'])",
                                    "item/location": "@coalesce(triggerBody()?['location'], triggerBody()?['Location'], '')",
                                    "item/instancetypecode": 0,
                                    "item/prioritycode": 2,
                                    "item/regardingobjectid_contact@odata.bind": "@concat('/contacts(', items('For_each_contact')?['contactid'], ')')",
                                },
                                "authentication": "@parameters('$authentication')",
                            },
                        }
                    },
                    "runAfter": {"List_attendee_contacts": ["Succeeded"]},
                },
            },
            "else": {"actions": {}},
            "runAfter": {},
        }
    }

    definition = flow_deploy.flow_definition_skeleton(actions, triggers)
    return flow_deploy.wrap_clientdata(outlook_ref, dataverse_ref, definition)


def deploy_outlook_workflows(client: Any, solution_name: str, config: dict[str, Any]) -> list[str]:
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    flow_deploy.ensure_connection_references(client, solution_name, config["connectionReferences"])

    workflow_ids: list[str] = []
    builders = {
        "calendarLog": build_calendar_log_flow,
        "unknownSender": build_unknown_sender_flow,
    }

    for key, builder in builders.items():
        flow_meta = config["flows"][key]
        print(f"\nDeploying flow: {flow_meta['name']}")
        clientdata = builder(config)
        workflow_id = flow_deploy.deploy_workflow(
            client,
            solution_name,
            flow_meta["name"],
            flow_meta.get("description", flow_meta["name"]),
            clientdata,
        )
        workflow_ids.append(workflow_id)

    return workflow_ids


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    flow_deploy = load_module("cre_flow_deploy", ROOT / "scripts" / "cre_flow_deploy.py")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    config = json.loads(OUTLOOK_CONFIG_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    base_client = deploy.DataverseClient(environment_url, token)
    solution_name = metadata["solution"]["name"]
    client = flow_deploy.FlowClient(base_client, solution_name)

    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")

    workflow_ids = deploy_outlook_workflows(client, solution_name, config)
    print("\nOutlook flows deployed in draft state.")
    print("Next steps (one-time per flow in Power Automate):")
    print("  1. Open Solutions > CRE Relationship Management")
    for flow_key in config["flows"]:
        print(f"     - {config['flows'][flow_key]['name']}")
    print("  2. Edit each flow and sign in to Office 365 Outlook and Dataverse connections")
    print("  3. Save and turn each flow On")
    print(f"  Flow ids: {', '.join(workflow_ids)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
