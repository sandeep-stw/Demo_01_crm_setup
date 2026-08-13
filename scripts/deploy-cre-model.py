#!/usr/bin/env python3
"""Deploy CRE relationship management metadata to Dataverse via Web API."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
VIEWS_PATH = ROOT / "config" / "cre-views.json"
VIEWS_DIR = ROOT / "views"
API_VERSION = "v9.2"


class DataverseClient:
    def __init__(self, environment_url: str, access_token: str) -> None:
        self.base_url = environment_url.rstrip("/") + f"/api/data/{API_VERSION}"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "MSCRM.SuppressDuplicateDetection": "false",
        }

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return None
                return json.loads(body)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed ({error.code}): {detail}") from error

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)


def localized(label: str) -> dict[str, Any]:
    return {"LocalizedLabels": [{"Label": label, "LanguageCode": 1033}], "UserLocalizedLabel": {"Label": label, "LanguageCode": 1033}}


def build_option_set(name: str, display_name: str, options: list[str]) -> dict[str, Any]:
    option_metadata = []
    for index, option in enumerate(options):
        option_metadata.append(
            {
                "Value": 851250000 + index,
                "@odata.type": "Microsoft.Dynamics.CRM.OptionMetadata",
                "Label": localized(option),
            }
        )
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
        "Name": name,
        "DisplayName": localized(display_name),
        "IsGlobal": True,
        "OptionSetType": "Picklist",
        "Options": option_metadata,
    }


def build_string_attribute(schema_name: str, display_name: str, max_length: int = 100) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "MaxLength": max_length,
    }


def build_memo_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "MaxLength": 2000,
    }


def build_integer_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "MinValue": 0,
        "MaxValue": 2147483647,
    }


def build_decimal_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "MinValue": 0,
        "MaxValue": 1000000000,
        "Precision": 2,
    }


def build_money_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "PrecisionSource": 2,
    }


def build_boolean_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {
            "TrueOption": {"Value": 1, "Label": localized("Yes")},
            "FalseOption": {"Value": 0, "Label": localized("No")},
        },
    }


def build_datetime_attribute(schema_name: str, display_name: str, date_only: bool = False) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "Format": "DateOnly" if date_only else "DateAndTime",
    }


def build_url_attribute(schema_name: str, display_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "MaxLength": 500,
        "FormatName": {"Value": "Url"},
    }


def build_picklist_attribute(schema_name: str, display_name: str, option_set_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "IsGlobal": True,
            "Name": option_set_name,
        },
    }


def build_multiselect_attribute(schema_name: str, display_name: str, option_set_name: str) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MultiSelectPicklistAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "IsGlobal": True,
            "Name": option_set_name,
        },
    }


def build_lookup_attribute(schema_name: str, display_name: str, targets: list[str]) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
        "SchemaName": schema_name,
        "DisplayName": localized(display_name),
        "RequiredLevel": {"Value": "None"},
        "Targets": targets,
    }


def field_to_attribute(field: dict[str, Any]) -> dict[str, Any]:
    field_type = field["type"]
    schema_name = field["schemaName"]
    display_name = field["displayName"]

    if field_type == "String":
        return build_string_attribute(schema_name, display_name, field.get("maxLength", 100))
    if field_type == "Memo":
        return build_memo_attribute(schema_name, display_name)
    if field_type == "Integer":
        return build_integer_attribute(schema_name, display_name)
    if field_type == "Decimal":
        return build_decimal_attribute(schema_name, display_name)
    if field_type == "Money":
        return build_money_attribute(schema_name, display_name)
    if field_type == "Boolean":
        return build_boolean_attribute(schema_name, display_name)
    if field_type == "Url":
        return build_url_attribute(schema_name, display_name)
    if field_type == "DateTime":
        return build_datetime_attribute(schema_name, display_name, field.get("format") == "DateOnly")
    if field_type == "Picklist":
        return build_picklist_attribute(schema_name, display_name, field["optionSet"])
    if field_type == "MultiSelectPicklist":
        return build_multiselect_attribute(schema_name, display_name, field["optionSet"])
    if field_type == "Lookup":
        return build_lookup_attribute(schema_name, display_name, field["targets"])
    raise ValueError(f"Unsupported field type: {field_type}")


def entity_exists(client: DataverseClient, logical_name: str) -> bool:
    try:
        client.get(f"EntityDefinitions(LogicalName='{logical_name}')")
        return True
    except RuntimeError:
        return False


def attribute_exists(client: DataverseClient, entity: str, schema_name: str) -> bool:
    try:
        client.get(
            f"EntityDefinitions(LogicalName='{entity}')/Attributes(LogicalName='{schema_name.lower()}')"
        )
        return True
    except RuntimeError:
        return False


def option_set_exists(client: DataverseClient, name: str) -> bool:
    try:
        client.get(f"GlobalOptionSetDefinitions(Name='{name}')")
        return True
    except RuntimeError:
        return False


def deploy_option_sets(client: DataverseClient, metadata: dict[str, Any]) -> None:
    for name, definition in metadata["globalOptionSets"].items():
        if option_set_exists(client, name):
            print(f"Option set exists: {name}")
            continue
        payload = build_option_set(name, definition["displayName"], definition["options"])
        client.post("GlobalOptionSetDefinitions", payload)
        print(f"Created option set: {name}")
        time.sleep(0.5)


def create_custom_entity(client: DataverseClient, entity_key: str, definition: dict[str, Any]) -> None:
    logical_name = entity_key
    if entity_exists(client, logical_name):
        print(f"Entity exists: {logical_name}")
    else:
        payload = {
            "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": logical_name,
            "DisplayName": localized(definition["displayName"]),
            "DisplayCollectionName": localized(definition["pluralName"]),
            "Description": localized(definition.get("description", definition["displayName"])),
            "OwnershipType": "UserOwned",
            "IsActivity": False,
            "HasActivities": False,
            "HasNotes": True,
        }
        client.post("EntityDefinitions", payload)
        print(f"Created entity: {logical_name}")
        time.sleep(2)

    for field in definition["fields"]:
        schema_name = field["schemaName"]
        if attribute_exists(client, logical_name, schema_name):
            print(f"  Attribute exists: {logical_name}.{schema_name}")
            continue
        attribute = field_to_attribute(field)
        client.post(f"EntityDefinitions(LogicalName='{logical_name}')/Attributes", attribute)
        print(f"  Created attribute: {logical_name}.{schema_name}")
        time.sleep(0.5)


def extend_entity(client: DataverseClient, entity_name: str, fields: list[dict[str, Any]]) -> None:
    print(f"Extending entity: {entity_name}")
    for field in fields:
        schema_name = field["schemaName"]
        if attribute_exists(client, entity_name, schema_name):
            print(f"  Attribute exists: {entity_name}.{schema_name}")
            continue
        attribute = field_to_attribute(field)
        client.post(f"EntityDefinitions(LogicalName='{entity_name}')/Attributes", attribute)
        print(f"  Created attribute: {entity_name}.{schema_name}")
        time.sleep(0.5)


def publish_customizations(client: DataverseClient) -> None:
    client.post("PublishAllXml", {})
    print("Published all customizations")


def deploy_views(client: DataverseClient) -> None:
    if not VIEWS_PATH.exists():
        return
    views_config = json.loads(VIEWS_PATH.read_text(encoding="utf-8"))
    for view in views_config.get("views", []):
        entity = view["entity"]
        fetch_path = VIEWS_DIR / view["fetchXmlFile"]
        if not fetch_path.exists():
            print(f"Skipping missing view file: {fetch_path.name}")
            continue
        fetch_xml = fetch_path.read_text(encoding="utf-8").strip()
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
            print(f"View exists: {name}")
            continue
        payload = {
            "name": name,
            "description": view.get("description", name),
            "fetchxml": fetch_xml,
            "querytype": 0,
            "returnedtypecode": entity,
            "isdefault": False,
            "isquickfindquery": False,
        }
        client.post("savedqueries", payload)
        print(f"Created view: {name}")
        time.sleep(0.3)


def get_access_token() -> tuple[str, str]:
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    environment_url = os.environ.get("DATAVERSE_ENVIRONMENT_URL")

    missing = [
        name
        for name, value in {
            "AZURE_TENANT_ID": tenant_id,
            "AZURE_CLIENT_ID": client_id,
            "AZURE_CLIENT_SECRET": client_secret,
            "DATAVERSE_ENVIRONMENT_URL": environment_url,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Configure them as Cloud Agent secrets before deploying."
        )

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": f"{environment_url.rstrip('/')}/.default",
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            description = parsed.get("error_description", detail)
        except json.JSONDecodeError:
            description = detail
        raise RuntimeError(
            "Failed to acquire Azure AD access token. "
            f"Verify AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET. "
            f"Use the client secret Value (not the Secret ID). Details: {description}"
        ) from error
    return environment_url, token_payload["access_token"]


def main() -> int:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    environment_url, token = get_access_token()
    client = DataverseClient(environment_url, token)

    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")

    deploy_option_sets(client, metadata)
    extend_entity(client, metadata["contactExtensions"]["entity"], metadata["contactExtensions"]["fields"])
    extend_entity(client, metadata["accountExtensions"]["entity"], metadata["accountExtensions"]["fields"])

    for entity_key, entity_definition in metadata["entities"].items():
        create_custom_entity(client, entity_key, entity_definition)

    publish_customizations(client)
    deploy_views(client)

    print("\nDeployment complete.")
    print("Next steps:")
    print("  1. Add new fields to Contact, Account, and Property forms in Power Apps")
    print("  2. Configure quick find on designation and classification fields")
    print("  3. Assign security roles for broker users")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
