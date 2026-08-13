#!/usr/bin/env python3
"""Ensure all CRE artifacts (metadata, app, forms, flow) are in the solution."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
VIEWS_PATH = ROOT / "config" / "cre-views.json"
APP_CONFIG_PATH = ROOT / "config" / "cre-app.json"
FLOW_CONFIG_PATH = ROOT / "config" / "cre-email-lead-flow.json"
OUTLOOK_WORKFLOWS_PATH = ROOT / "config" / "cre-outlook-workflows.json"

COMPONENT_FORM = 60
COMPONENT_SITEMAP = 62
COMPONENT_APP = 80
COMPONENT_WORKFLOW = 29
COMPONENT_CONNECTION_REFERENCE = 371
COMPONENT_SAVED_QUERY = 26


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_component(
    client: Any,
    solution_name: str,
    component_id: str,
    component_type: int,
    label: str,
) -> None:
    payload: dict[str, Any] = {
        "ComponentId": component_id,
        "ComponentType": component_type,
        "SolutionUniqueName": solution_name,
        "AddRequiredComponents": False,
    }
    try:
        client.post("AddSolutionComponent", payload)
        print(f"  Added {label}")
    except RuntimeError as error:
        message = str(error)
        if "0x80071151" in message or "already a member" in message.lower():
            print(f"  Already in solution: {label}")
            return
        if component_type == COMPONENT_CONNECTION_REFERENCE and "msdyn_Connector" in message:
            print(f"  Connection reference in solution context: {label}")
            return
        raise


def find_form(client: Any, entity: str, name: str) -> str | None:
    escaped = name.replace("'", "''")
    result = client.get(
        "systemforms?"
        + urllib.parse.urlencode(
            {
                "$filter": f"objecttypecode eq '{entity}' and name eq '{escaped}'",
                "$select": "formid,name",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0]["formid"] if rows else None


def find_sitemap(client: Any, unique_name: str) -> str | None:
    escaped = unique_name.replace("'", "''")
    for field in ("sitemapnameunique", "sitemapname"):
        result = client.get(
            "sitemaps?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"{field} eq '{escaped}'",
                    "$select": "sitemapid",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if rows:
            return rows[0]["sitemapid"]
    return None


def find_app(client: Any, unique_name: str) -> str | None:
    candidates = {unique_name, f"cre_{unique_name}"}
    for candidate in candidates:
        result = client.get(
            "appmodules?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"uniquename eq '{candidate}'",
                    "$select": "appmoduleid",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if rows:
            return rows[0]["appmoduleid"]
    try:
        unpublished = client.get(
            "appmodules/Microsoft.Dynamics.CRM.RetrieveUnpublishedMultiple()?$select=appmoduleid,uniquename"
        )
        for row in unpublished.get("value", []):
            if row.get("uniquename") in candidates:
                return row["appmoduleid"]
    except RuntimeError:
        pass
    return None


def find_workflow(client: Any, name: str) -> str | None:
    escaped = name.replace("'", "''")
    result = client.get(
        "workflows?"
        + urllib.parse.urlencode(
            {
                "$filter": f"name eq '{escaped}' and category eq 5",
                "$select": "workflowid,name",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0]["workflowid"] if rows else None


def find_connection_reference(client: Any, logical_name: str) -> str | None:
    result = client.get(
        "connectionreferences?"
        + urllib.parse.urlencode(
            {
                "$filter": f"connectionreferencelogicalname eq '{logical_name}'",
                "$select": "connectionreferenceid",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0]["connectionreferenceid"] if rows else None


def register_forms(client: Any, solution_name: str, app_config: dict[str, Any]) -> None:
    print("Registering forms...")
    for entity_key, form_def in app_config.get("forms", {}).items():
        entity = "cre_property" if entity_key == "cre_property" else (
            "cre_propertysuite" if entity_key == "cre_propertysuite" else entity_key
        )
        form_name = form_def["name"]
        form_id = find_form(client, entity, form_name)
        if not form_id:
            print(f"  Skipped form (not found): {entity} / {form_name}")
            continue
        add_component(client, solution_name, form_id, COMPONENT_FORM, f"Form {form_name}")


def register_sitemap(client: Any, solution_name: str, metadata: dict[str, Any], app_config: dict[str, Any]) -> None:
    print("Registering sitemap...")
    unique_name = f"{metadata['solution']['prefix']}_{app_config['app']['uniqueName']}"
    sitemap_id = find_sitemap(client, unique_name) or find_sitemap(client, app_config["app"]["name"])
    if not sitemap_id:
        print(f"  Skipped sitemap (not found): {unique_name}")
        return
    add_component(client, solution_name, sitemap_id, COMPONENT_SITEMAP, f"Sitemap {app_config['app']['name']}")


def register_app(client: Any, solution_name: str, app_config: dict[str, Any]) -> None:
    print("Registering model-driven app...")
    app = app_config["app"]
    app_id = find_app(client, app["uniqueName"])
    if not app_id:
        print(f"  Skipped app (not found): {app['name']}")
        return
    add_component(client, solution_name, app_id, COMPONENT_APP, f"App {app['name']}")


def register_flow_by_name(client: Any, solution_name: str, flow_name: str) -> None:
    workflow_id = find_workflow(client, flow_name)
    if not workflow_id:
        print(f"  Skipped flow (not found): {flow_name}")
        return
    add_component(client, solution_name, workflow_id, COMPONENT_WORKFLOW, f"Flow {flow_name}")


def register_flow(client: Any, solution_name: str, flow_config: dict[str, Any]) -> None:
    print("Registering cloud flow...")
    register_flow_by_name(client, solution_name, flow_config["flow"]["name"])


def register_outlook_flows(client: Any, solution_name: str) -> None:
    if not OUTLOOK_WORKFLOWS_PATH.exists():
        return
    outlook_config = json.loads(OUTLOOK_WORKFLOWS_PATH.read_text(encoding="utf-8"))
    print("Registering Outlook workflows...")
    for flow_def in outlook_config.get("flows", {}).values():
        register_flow_by_name(client, solution_name, flow_def["name"])


def register_connection_references(client: Any, solution_name: str, flow_config: dict[str, Any]) -> None:
    print("Registering connection references...")
    for key, definition in flow_config.get("connectionReferences", {}).items():
        logical_name = definition["logicalName"]
        ref_id = find_connection_reference(client, logical_name)
        if not ref_id:
            print(f"  Skipped connection reference (not found): {logical_name}")
            continue
        add_component(
            client,
            solution_name,
            ref_id,
            COMPONENT_CONNECTION_REFERENCE,
            f"ConnectionRef {logical_name}",
        )


def verify_solution_membership(client: Any, solution_name: str, metadata: dict[str, Any]) -> None:
    """Print a summary of CRE artifacts registered in the solution."""
    sid = client.get(
        "solutions?"
        + urllib.parse.urlencode(
            {
                "$filter": f"uniquename eq '{solution_name}'",
                "$select": "solutionid,friendlyname",
                "$top": "1",
            }
        )
    )["value"][0]["solutionid"]

    def in_solution(component_type: int, object_id: str) -> bool:
        result = client.get(
            "solutioncomponents?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"_solutionid_value eq {sid} and componenttype eq {component_type} and objectid eq {object_id}",
                    "$select": "objectid",
                    "$top": "1",
                }
            )
        )
        return bool(result.get("value"))

    print("\nSolution membership summary:")
    app_config = json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
    flow_config = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))

    for entity_key, form_def in app_config.get("forms", {}).items():
        entity = entity_key
        form_id = find_form(client, entity, form_def["name"])
        if form_id:
            status = "yes" if in_solution(COMPONENT_FORM, form_id) else "no (may be nested under entity)"
            print(f"  Form {form_def['name']}: {status}")

    app_id = find_app(client, app_config["app"]["uniqueName"])
    if app_id:
        print(f"  App {app_config['app']['name']}: {'yes' if in_solution(COMPONENT_APP, app_id) else 'no'}")

    unique_name = f"{metadata['solution']['prefix']}_{app_config['app']['uniqueName']}"
    sitemap_id = find_sitemap(client, unique_name) or find_sitemap(client, app_config["app"]["name"])
    if sitemap_id:
        print(f"  Sitemap: {'yes' if in_solution(COMPONENT_SITEMAP, sitemap_id) else 'no'}")

    workflow_id = find_workflow(client, flow_config["flow"]["name"])
    if workflow_id:
        print(f"  Flow {flow_config['flow']['name']}: {'yes' if in_solution(COMPONENT_WORKFLOW, workflow_id) else 'no'}")

    if OUTLOOK_WORKFLOWS_PATH.exists():
        outlook_config = json.loads(OUTLOOK_WORKFLOWS_PATH.read_text(encoding="utf-8"))
        for flow_def in outlook_config.get("flows", {}).values():
            wid = find_workflow(client, flow_def["name"])
            if wid:
                print(
                    f"  Flow {flow_def['name']}: {'yes' if in_solution(COMPONENT_WORKFLOW, wid) else 'no'}"
                )

    views_config = json.loads(VIEWS_PATH.read_text(encoding="utf-8"))
    missing_views = []
    for view in views_config.get("views", []):
        escaped = view["name"].replace("'", "''")
        result = client.get(
            "savedqueries?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"name eq '{escaped}'",
                    "$select": "savedqueryid",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if not rows:
            missing_views.append(view["name"] + " (not deployed)")
            continue
        if not in_solution(COMPONENT_SAVED_QUERY, rows[0]["savedqueryid"]):
            missing_views.append(view["name"])

    if missing_views:
        print(f"  Views not listed as top-level solution components: {', '.join(missing_views)}")
        print("    (Custom-entity views may still be available in the app; re-run deploy or add via maker portal.)")
    else:
        print("  All configured views: yes")


def register_all_components(client: Any, metadata: dict[str, Any]) -> None:
    solution_name = metadata["solution"]["name"]
    add_script = load_module("add_cre_to_solution", ROOT / "scripts" / "add-cre-to-solution.py")
    add_script.register_cre_solution(client, metadata)

    app_config = json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
    flow_config = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))

    register_forms(client, solution_name, app_config)
    register_sitemap(client, solution_name, metadata, app_config)
    register_app(client, solution_name, app_config)
    register_flow(client, solution_name, flow_config)
    register_outlook_flows(client, solution_name)
    register_connection_references(client, solution_name, flow_config)

    client.post("PublishAllXml", {})
    verify_solution_membership(client, solution_name, metadata)
    print(f"\nAll CRE components registered in solution '{solution_name}'.")


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    client = deploy.DataverseClient(environment_url, token)
    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")
    register_all_components(client, metadata)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
