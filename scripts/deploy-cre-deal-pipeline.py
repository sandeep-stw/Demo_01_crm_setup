#!/usr/bin/env python3
"""Deploy Phase 2 deal pipeline: opportunity fields, views, and form."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
PIPELINE_PATH = ROOT / "config" / "cre-deal-pipeline.json"
VIEWS_DIR = ROOT / "views"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge_metadata(base: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    merged.setdefault("globalOptionSets", {}).update(pipeline.get("globalOptionSets", {}))
    merged["opportunityExtensions"] = pipeline["opportunityExtensions"]
    return merged


def deploy_pipeline_views(client: Any, pipeline: dict[str, Any]) -> None:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    for view in pipeline.get("views", []):
        fetch_path = VIEWS_DIR / view["fetchXmlFile"]
        if not fetch_path.exists():
            print(f"  Skipped missing view file: {fetch_path.name}")
            continue
        fetch_xml = deploy.normalize_fetchxml(fetch_path.read_text(encoding="utf-8"))
        name = view["name"]
        existing = client.get(
            "savedqueries?"
            + urllib.parse.urlencode(
                {
                    "$select": "savedqueryid,name",
                    "$filter": f"name eq '{name.replace(chr(39), chr(39)+chr(39))}'",
                    "$top": "1",
                }
            )
        )
        if existing.get("value"):
            print(f"  View exists: {name}")
            continue
        payload = {
            "name": name,
            "description": view.get("description", name),
            "fetchxml": fetch_xml,
            "querytype": 0,
            "returnedtypecode": "opportunity",
            "isdefault": False,
            "isquickfindquery": False,
        }
        client.post("savedqueries", payload)
        print(f"  Created view: {name}")
        time.sleep(0.3)


def deploy_opportunity_form(client: Any, solution_name: str, pipeline: dict[str, Any]) -> None:
    deploy_app = load_module("deploy_cre_app", ROOT / "scripts" / "deploy-cre-app.py")
    fb = load_module("cre_form_builder", ROOT / "scripts" / "cre_form_builder.py")
    app_client = deploy_app.AppClient(client, solution_name)
    form_config = pipeline["form"]

    standard_map = {
        "name": fb.standard_field("name", "Topic"),
        "customerid": fb.standard_field("customerid", "Potential Customer", "Lookup"),
        "estimatedvalue": fb.standard_field("estimatedvalue", "Est. Revenue", "Money"),
        "closeprobability": fb.standard_field("closeprobability", "Probability", "Integer"),
        "estimatedclosedate": fb.standard_field("estimatedclosedate", "Est. Close Date", "DateTime"),
        "ownerid": fb.standard_field("ownerid", "Owner", "Lookup"),
    }
    field_lookup = {f["schemaName"]: f for f in pipeline["opportunityExtensions"]["fields"]}

    def resolve_field(schema: str) -> dict[str, Any]:
        if schema in standard_map:
            return standard_map[schema]
        field = field_lookup.get(schema)
        if not field:
            raise ValueError(f"Unknown field in form config: {schema}")
        return field

    tabs: dict[str, list[dict[str, Any]]] = {}
    for tab_name, schemas in form_config.get("standardFields", {}).items():
        tabs.setdefault(tab_name, []).extend(resolve_field(schema) for schema in schemas)
    for tab_name, schemas in form_config.get("tabs", {}).items():
        tabs.setdefault(tab_name, []).extend(resolve_field(schema) for schema in schemas)

    form_xml = fb.build_simple_form(tabs)
    deploy_app.upsert_form(
        app_client,
        solution_name,
        "opportunity",
        form_config["name"],
        form_xml,
    )


def register_bpf_guidance(pipeline: dict[str, Any]) -> None:
    print("\nBusiness process flows (create in maker portal):")
    for bpf in pipeline.get("businessProcessFlows", []):
        stages = " → ".join(bpf["stages"])
        print(f"  - {bpf['name']}")
        print(f"      Business line: {bpf['businessLine']}")
        print(f"      Stages: {stages}")
    print("  See docs/cre-phase2-deal-pipeline.md for BPF designer steps.")


def deploy_deal_pipeline(client: Any, metadata: dict[str, Any], pipeline: dict[str, Any]) -> None:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    solution_name = metadata["solution"]["name"]

    print("Deploying deal pipeline option sets...")
    deploy.deploy_option_sets(client, metadata)

    print("Deploying opportunity custom fields...")
    deploy.extend_entity(
        client,
        pipeline["opportunityExtensions"]["entity"],
        pipeline["opportunityExtensions"]["fields"],
        metadata,
    )

    print("Publishing customizations...")
    deploy.publish_customizations(client)

    print("Deploying opportunity views...")
    deploy_pipeline_views(client, pipeline)

    print("Deploying CRE Opportunity form...")
    deploy_opportunity_form(client, solution_name, pipeline)

    register_bpf_guidance(pipeline)


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    base_metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    metadata = merge_metadata(base_metadata, pipeline)

    environment_url, token = deploy.get_access_token()
    client = deploy.DataverseClient(environment_url, token)
    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")

    deploy_deal_pipeline(client, metadata, pipeline)
    print("\nDeal pipeline deployment complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
