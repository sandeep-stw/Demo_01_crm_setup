#!/usr/bin/env python3
"""Import the CRE solution shell and add deployed components to it."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
VIEWS_PATH = ROOT / "config" / "cre-views.json"
PIPELINE_PATH = ROOT / "config" / "cre-deal-pipeline.json"
SOLUTION_ZIP = ROOT / "solutions" / "CreRelationshipManagement" / "bin" / "Debug" / "CreRelationshipManagement.zip"

# https://learn.microsoft.com/en-us/power-apps/developer/data-platform/reference/component-types
COMPONENT_ENTITY = 1
COMPONENT_ATTRIBUTE = 2
COMPONENT_RELATIONSHIP = 10
COMPONENT_OPTION_SET = 9
COMPONENT_SAVED_QUERY = 26


def load_deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def solution_exists(client: Any, unique_name: str) -> bool:
    try:
        result = client.get(
            "solutions?"
            + urllib.parse.urlencode(
                {
                    "$select": "solutionid,uniquename,friendlyname",
                    "$filter": f"uniquename eq '{unique_name}'",
                    "$top": "1",
                }
            )
        )
        return bool(result.get("value"))
    except RuntimeError:
        return False


def wait_for_import(client: Any, solution_name: str, timeout_seconds: int = 300) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if solution_exists(client, solution_name):
            return
        time.sleep(3)
    raise RuntimeError(f"Solution '{solution_name}' was not available after {timeout_seconds}s")


def import_solution_zip(client: Any, zip_path: Path, solution_name: str) -> None:
    if not zip_path.exists():
        raise RuntimeError(
            f"Solution package not found at {zip_path}. "
            "Run: dotnet build solutions/CreRelationshipManagement/CreRelationshipManagement.cdsproj"
        )
    import_job_id = str(uuid.uuid4())
    payload = {
        "CustomizationFile": base64.b64encode(zip_path.read_bytes()).decode("ascii"),
        "OverwriteUnmanagedCustomizations": True,
        "PublishWorkflows": True,
        "ImportJobId": import_job_id,
    }
    client.post("ImportSolution", payload)
    print(f"Importing solution package (job {import_job_id})...")
    wait_for_import(client, solution_name)
    print("Solution package imported.")


def add_component(
    client: Any,
    solution_name: str,
    component_id: str,
    component_type: int,
    *,
    label: str,
    include_subcomponents: bool = False,
) -> None:
    payload: dict[str, Any] = {
        "ComponentId": component_id,
        "ComponentType": component_type,
        "SolutionUniqueName": solution_name,
        "AddRequiredComponents": False,
    }
    if component_type == COMPONENT_ENTITY:
        payload["DoNotIncludeSubcomponents"] = not include_subcomponents
    try:
        client.post("AddSolutionComponent", payload)
        print(f"  Added {label}")
    except RuntimeError as error:
        message = str(error)
        if "0x80071151" in message or "already a member" in message.lower():
            print(f"  Already in solution: {label}")
            return
        raise


def entity_metadata_id(client: Any, logical_name: str) -> str:
    result = client.get(f"EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId")
    return result["MetadataId"]


def attribute_metadata_id(client: Any, entity: str, logical_name: str) -> str:
    result = client.get(
        f"EntityDefinitions(LogicalName='{entity}')/Attributes(LogicalName='{logical_name.lower()}')?$select=MetadataId"
    )
    return result["MetadataId"]


def option_set_metadata_id(client: Any, name: str) -> str:
    result = client.get(f"GlobalOptionSetDefinitions(Name='{name}')?$select=MetadataId")
    return result["MetadataId"]


def saved_query_id(client: Any, name: str) -> str:
    escaped = name.replace("'", "''")
    result = client.get(
        "savedqueries?"
        + urllib.parse.urlencode(
            {
                "$select": "savedqueryid,name",
                "$filter": f"name eq '{escaped}'",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    if not rows:
        raise RuntimeError(f"Saved query not found: {name}")
    return rows[0]["savedqueryid"]


def register_cre_solution(client: Any, metadata: dict[str, Any]) -> None:
    solution_name = metadata["solution"]["name"]
    print(f"Ensuring solution '{solution_name}' exists in environment...")

    if not solution_exists(client, solution_name):
        import_solution_zip(client, SOLUTION_ZIP, solution_name)
        if not solution_exists(client, solution_name):
            raise RuntimeError(f"Solution '{solution_name}' was not created after import.")
    else:
        print(f"Solution exists: {solution_name}")

    print("Adding global option sets...")
    for option_set_name in metadata.get("globalOptionSets", {}):
        try:
            metadata_id = option_set_metadata_id(client, option_set_name)
            add_component(client, solution_name, metadata_id, COMPONENT_OPTION_SET, label=f"OptionSet {option_set_name}")
        except RuntimeError as error:
            print(f"  Skipped OptionSet {option_set_name}: {error}")
        time.sleep(0.2)

    print("Adding Contact and Account field extensions...")
    for section_key in ("contactExtensions", "accountExtensions", "opportunityExtensions"):
        if section_key not in metadata:
            continue
        section = metadata[section_key]
        entity = section["entity"]
        for field in section["fields"]:
            schema = field["schemaName"].lower()
            try:
                metadata_id = attribute_metadata_id(client, entity, schema)
                add_component(
                    client,
                    solution_name,
                    metadata_id,
                    COMPONENT_ATTRIBUTE,
                    label=f"{entity}.{schema}",
                )
            except RuntimeError as error:
                print(f"  Skipped {entity}.{schema}: {error}")
            time.sleep(0.2)

    print("Adding custom entities (with columns and relationships)...")
    for entity_key in metadata.get("entities", {}):
        metadata_id = entity_metadata_id(client, entity_key)
        add_component(
            client,
            solution_name,
            metadata_id,
            COMPONENT_ENTITY,
            label=f"Entity {entity_key}",
            include_subcomponents=True,
        )
        time.sleep(0.5)

    print("Adding saved views...")
    if VIEWS_PATH.exists():
        views_config = json.loads(VIEWS_PATH.read_text(encoding="utf-8"))
        for view in views_config.get("views", []):
            try:
                query_id = saved_query_id(client, view["name"])
                add_component(
                    client,
                    solution_name,
                    query_id,
                    COMPONENT_SAVED_QUERY,
                    label=f"View {view['name']}",
                )
            except RuntimeError as error:
                print(f"  Skipped view {view['name']}: {error}")
            time.sleep(0.2)

    if PIPELINE_PATH.exists():
        pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
        for view in pipeline.get("views", []):
            try:
                query_id = saved_query_id(client, view["name"])
                add_component(
                    client,
                    solution_name,
                    query_id,
                    COMPONENT_SAVED_QUERY,
                    label=f"View {view['name']}",
                )
            except RuntimeError as error:
                print(f"  Skipped view {view['name']}: {error}")
            time.sleep(0.2)

    client.post("PublishAllXml", {})
    print(f"\nSolution '{solution_name}' is ready in Power Apps > Solutions.")


def load_metadata() -> dict[str, Any]:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if PIPELINE_PATH.exists():
        pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
        metadata.setdefault("globalOptionSets", {}).update(pipeline.get("globalOptionSets", {}))
        if "opportunityExtensions" in pipeline:
            metadata["opportunityExtensions"] = pipeline["opportunityExtensions"]
    return metadata


def main() -> int:
    deploy = load_deploy_module()
    metadata = load_metadata()
    environment_url, token = deploy.get_access_token()
    client = deploy.DataverseClient(environment_url, token)
    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")
    register_cre_solution(client, metadata)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
