#!/usr/bin/env python3
"""Deploy CRE model-driven app, forms, and sitemap into the solution."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
APP_CONFIG_PATH = ROOT / "config" / "cre-app.json"
VIEWS_PATH = ROOT / "config" / "cre-views.json"

COMPONENT_FORM = 60
COMPONENT_SITEMAP = 62
COMPONENT_APP = 80
DEFAULT_APP_ICON = "953b9fac-1e5e-e611-80d6-00155ded156f"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AppClient:
    def __init__(self, base_client: Any, solution_name: str | None = None) -> None:
        self._client = base_client
        self.base_url = base_client.base_url
        self.headers = dict(base_client.headers)
        if solution_name:
            self.headers["MSCRM.SolutionUniqueName"] = solution_name

    def get(self, path: str) -> Any:
        return self._client.get(path)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
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
    def parse_entity_id(result: Any, key: str) -> str:
        if isinstance(result, dict) and "_entity_id" in result:
            match = re.search(rf"{key}\(([^)]+)\)", result["_entity_id"])
            if match:
                return match.group(1).strip("'")
        raise RuntimeError(f"Could not parse entity id for {key} from response: {result}")


def add_solution_component(client: AppClient, solution_name: str, component_id: str, component_type: int, label: str) -> None:
    payload: dict[str, Any] = {
        "ComponentId": component_id,
        "ComponentType": component_type,
        "SolutionUniqueName": solution_name,
        "AddRequiredComponents": False,
    }
    try:
        client.post("AddSolutionComponent", payload)
        print(f"  Added to solution: {label}")
    except RuntimeError as error:
        if "0x80071151" in str(error) or "already a member" in str(error).lower():
            print(f"  Already in solution: {label}")
            return
        raise


def find_form(client: AppClient, entity: str, name: str) -> str | None:
    result = client.get(
        "systemforms?"
        + urllib.parse.urlencode(
            {
                "$filter": f"objecttypecode eq '{entity}' and name eq '{name.replace(chr(39), chr(39)+chr(39))}'",
                "$select": "formid,name",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0]["formid"] if rows else None


def find_information_form(client: AppClient, entity: str) -> str | None:
    return find_form(client, entity, "Information")


def upsert_form(
    client: AppClient,
    solution_name: str,
    entity: str,
    form_name: str,
    form_xml: str,
    *,
    update_information: bool = False,
) -> str:
    existing_id = find_form(client, entity, form_name)
    if existing_id:
        client.patch(f"systemforms({existing_id})", {"formxml": form_xml})
        print(f"  Updated form: {form_name}")
        form_id = existing_id
    elif update_information:
        info_id = find_information_form(client, entity)
        if info_id:
            client.patch(
                f"systemforms({info_id})",
                {"name": form_name, "formxml": form_xml},
            )
            print(f"  Updated Information form as: {form_name}")
            form_id = info_id
        else:
            form_id = create_form(client, entity, form_name, form_xml)
    else:
        form_id = create_form(client, entity, form_name, form_xml)

    add_solution_component(client, solution_name, form_id, COMPONENT_FORM, f"Form {form_name}")
    return form_id


def create_form(client: AppClient, entity: str, form_name: str, form_xml: str) -> str:
    payload = {
        "name": form_name,
        "objecttypecode": entity,
        "type": 2,
        "formxml": form_xml,
        "iscustomizable": {"Value": True},
    }
    result = client.post("systemforms", payload)
    form_id = AppClient.parse_entity_id(result, "systemforms")
    print(f"  Created form: {form_name} ({form_id})")
    return form_id


def saved_query_id(client: AppClient, name: str) -> str:
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


def entity_metadata_id(client: AppClient, logical_name: str) -> str:
    return client.get(f"EntityDefinitions(LogicalName='{logical_name}')?$select=MetadataId")["MetadataId"]


def property_suite_relationship_name(client: AppClient) -> str:
    rels = client.get(
        "EntityDefinitions(LogicalName='cre_property')/OneToManyRelationships?$select=SchemaName,ReferencingEntity"
    )
    for rel in rels.get("value", []):
        if rel.get("ReferencingEntity") == "cre_propertysuite":
            return rel["SchemaName"]
    raise RuntimeError("Property to suite relationship not found")


def build_forms(metadata: dict[str, Any], client: AppClient, app_config: dict[str, Any], solution_name: str) -> dict[str, str]:
    fb = load_module("cre_form_builder", ROOT / "scripts" / "cre_form_builder.py")
    form_ids: dict[str, str] = {}

    property_fields = metadata["entities"]["cre_property"]["fields"]
    suite_fields = metadata["entities"]["cre_propertysuite"]["fields"]
    contact_fields = metadata["contactExtensions"]["fields"]
    account_fields = metadata["accountExtensions"]["fields"]

    suite_view_id = saved_query_id(client, "Active Property Suites")
    suite_relationship = property_suite_relationship_name(client)

    property_form_xml = fb.build_property_form(
        {
            "Summary": fb.pick_fields(
                property_fields,
                [
                    "cre_name",
                    "cre_propertystatus",
                    "cre_propertytype",
                    "cre_leasingstatus",
                    "cre_assignedbrokerid",
                    "cre_market",
                    "cre_submarket",
                ],
            ),
            "Location": fb.pick_fields(
                property_fields,
                [
                    "cre_addressline1",
                    "cre_addressline2",
                    "cre_city",
                    "cre_state",
                    "cre_postalcode",
                    "cre_county",
                ],
            ),
            "Building": fb.pick_fields(
                property_fields,
                [
                    "cre_buildingsf",
                    "cre_landareaacres",
                    "cre_occupancypct",
                    "cre_parkingratio",
                    "cre_constructionyear",
                    "cre_zoning",
                ],
            ),
            "Leasing": fb.pick_fields(
                property_fields,
                [
                    "cre_leaserate",
                    "cre_operatingexpenses",
                    "cre_availablesuites",
                    "cre_tenantimprovements",
                ],
            ),
            "Ownership": fb.pick_fields(
                property_fields,
                [
                    "cre_primaryownerid",
                    "cre_propertymanagerid",
                    "cre_assetmanagerid",
                    "cre_ownershipnotes",
                ],
            ),
        },
        suite_view_id=suite_view_id,
        suite_relationship_name=suite_relationship,
    )

    suite_form_xml = fb.build_simple_form(
        {
            "Suite Details": fb.pick_fields(
                suite_fields,
                [
                    "cre_name",
                    "cre_propertyid",
                    "cre_suitenumber",
                    "cre_floor",
                    "cre_suitearea",
                    "cre_isvacant",
                ],
            ),
            "Tenant & Lease": fb.pick_fields(
                suite_fields,
                [
                    "cre_tenantcontactid",
                    "cre_tenantaccountid",
                    "cre_leasestartdate",
                    "cre_leaseexpirationdate",
                    "cre_renewaloptions",
                ],
            ),
        }
    )

    contact_form_xml = fb.build_simple_form(
        {
            "Contact": [
                fb.standard_field("firstname", "First Name"),
                fb.standard_field("lastname", "Last Name"),
                fb.standard_field("emailaddress1", "Email"),
                fb.standard_field("telephone1", "Business Phone"),
                fb.standard_field("jobtitle", "Job Title"),
            ],
            "CRE Relationship": fb.pick_fields(
                contact_fields,
                [
                    "cre_relationshipclassifications",
                    "cre_professionaldesignations",
                    "cre_relationshiptier",
                    "cre_assignedbrokerid",
                    "cre_businessline",
                    "cre_lastmeaningfulcontact",
                    "cre_preferredcommunicationmethod",
                ],
            ),
            "Markets & Requirements": fb.pick_fields(
                contact_fields,
                [
                    "cre_marketsserved",
                    "cre_geographiccoverage",
                    "cre_targetmarkets",
                    "cre_propertypreferences",
                    "cre_minsf",
                    "cre_maxsf",
                    "cre_leaseexpirationdate",
                    "cre_renewaltimeline",
                ],
            ),
            "Social & Tags": fb.pick_fields(
                contact_fields,
                ["cre_sociallinkedin", "cre_socialtwitter", "cre_referralsource", "cre_tags"],
            ),
        }
    )

    account_form_xml = fb.build_simple_form(
        {
            "Account": [
                fb.standard_field("name", "Account Name"),
                fb.standard_field("telephone1", "Main Phone"),
            ],
            "CRE Portfolio": fb.pick_fields(
                account_fields,
                [
                    "cre_accountclassifications",
                    "cre_portfoliosf",
                    "cre_markets",
                    "cre_industries",
                    "cre_naicscode",
                    "cre_multipleofficelocations",
                ],
            ),
        }
    )

    print("Deploying forms...")
    form_ids["cre_property"] = upsert_form(
        client,
        solution_name,
        "cre_property",
        app_config["forms"]["cre_property"]["name"],
        property_form_xml,
        update_information=app_config["forms"]["cre_property"].get("updateInformationForm", False),
    )
    form_ids["cre_propertysuite"] = upsert_form(
        client,
        solution_name,
        "cre_propertysuite",
        app_config["forms"]["cre_propertysuite"]["name"],
        suite_form_xml,
        update_information=app_config["forms"]["cre_propertysuite"].get("updateInformationForm", False),
    )
    form_ids["contact"] = upsert_form(
        client,
        solution_name,
        "contact",
        app_config["forms"]["contact"]["name"],
        contact_form_xml,
    )
    form_ids["account"] = upsert_form(
        client,
        solution_name,
        "account",
        app_config["forms"]["account"]["name"],
        account_form_xml,
    )
    return form_ids


def build_sitemap_xml() -> str:
    return """<SiteMap IntroducedVersion="9.0.0.0">
  <Area Id="cre_area" ResourceId="SitemapDesigner.NewArea" DescriptionResourceId="SitemapDesigner.NewArea" ShowGroups="true" IntroducedVersion="9.0.0.0">
    <Titles><Title LCID="1033" Title="CRE" /></Titles>
    <Group Id="cre_relationships" ResourceId="SitemapDesigner.NewGroup" DescriptionResourceId="SitemapDesigner.NewGroup" IntroducedVersion="9.0.0.0" IsProfile="false" ToolTipResourseId="SitemapDesigner.Unknown">
      <Titles><Title LCID="1033" Title="Relationships" /></Titles>
      <SubArea Id="cre_contacts" Entity="contact" IntroducedVersion="9.0.0.0" />
      <SubArea Id="cre_accounts" Entity="account" IntroducedVersion="9.0.0.0" />
      <SubArea Id="cre_properties" Entity="cre_property" IntroducedVersion="9.0.0.0" />
      <SubArea Id="cre_suites" Entity="cre_propertysuite" IntroducedVersion="9.0.0.0" />
      <SubArea Id="cre_opportunities" Entity="opportunity" IntroducedVersion="9.0.0.0" />
    </Group>
  </Area>
</SiteMap>"""


def find_sitemap(client: AppClient, name_or_unique: str) -> str | None:
    escaped = name_or_unique.replace("'", "''")
    for field in ("sitemapname", "sitemapnameunique"):
        result = client.get(
            "sitemaps?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"{field} eq '{escaped}'",
                    "$select": "sitemapid,sitemapname,sitemapnameunique",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if rows:
            return rows[0]["sitemapid"]
    return None


def upsert_sitemap(client: AppClient, solution_name: str, name: str, unique_name: str, sitemap_xml: str) -> str:
    existing = find_sitemap(client, unique_name) or find_sitemap(client, name)
    if existing:
        client.patch(
            f"sitemaps({existing})",
            {"sitemapxml": sitemap_xml, "sitemapnameunique": unique_name},
        )
        sitemap_id = existing
        print(f"  Updated sitemap: {name}")
    else:
        payload = {
            "sitemapname": name,
            "sitemapnameunique": unique_name,
            "sitemapxml": sitemap_xml,
            "isappaware": True,
            "showhome": True,
            "showrecents": True,
            "showpinned": True,
        }
        result = client.post("sitemaps", payload)
        sitemap_id = AppClient.parse_entity_id(result, "sitemaps")
        print(f"  Created sitemap: {name}")
    add_solution_component(client, solution_name, sitemap_id, COMPONENT_SITEMAP, f"Sitemap {name}")
    return sitemap_id


def find_app(client: AppClient, unique_name: str) -> str | None:
    candidates = {unique_name, f"cre_{unique_name}"}
    for candidate in candidates:
        result = client.get(
            "appmodules?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"uniquename eq '{candidate}'",
                    "$select": "appmoduleid,uniquename",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if rows:
            return rows[0]["appmoduleid"]

    unpublished = client.get(
        "appmodules/Microsoft.Dynamics.CRM.RetrieveUnpublishedMultiple()?$select=appmoduleid,uniquename"
    )
    for row in unpublished.get("value", []):
        if row.get("uniquename") in candidates:
            return row["appmoduleid"]
    return None


def upsert_app(client: AppClient, solution_name: str, app_config: dict[str, Any]) -> str:
    app = app_config["app"]
    existing = find_app(client, app["uniqueName"])
    if existing:
        print(f"  Using existing app: {app['name']} ({existing})")
        app_id = existing
    else:
        payload = {
            "name": app["name"],
            "uniquename": app["uniqueName"],
            "description": app.get("description", app["name"]),
            "webresourceid": app.get("iconWebResourceId", DEFAULT_APP_ICON),
        }
        result = client.post("appmodules", payload)
        app_id = AppClient.parse_entity_id(result, "appmodules")
        print(f"  Created app: {app['name']}")
    add_solution_component(client, solution_name, app_id, COMPONENT_APP, f"App {app['name']}")
    return app_id


def collect_view_ids(client: AppClient) -> list[str]:
    views_config = json.loads(VIEWS_PATH.read_text(encoding="utf-8"))
    view_ids = []
    for view in views_config.get("views", []):
        view_ids.append(saved_query_id(client, view["name"]))
    for name in ("Active Properties", "Active Property Suites"):
        try:
            view_ids.append(saved_query_id(client, name))
        except RuntimeError:
            pass
    return view_ids


def add_app_components(client: AppClient, app_id: str, components: list[dict[str, Any]]) -> None:
    chunk_size = 20
    for index in range(0, len(components), chunk_size):
        chunk = components[index : index + chunk_size]
        client.post("AddAppComponents", {"AppId": app_id, "Components": chunk})
        time.sleep(0.5)


def associate_roles(client: AppClient, app_id: str, role_names: list[str]) -> None:
    for role_name in role_names:
        result = client.get(
            "roles?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"name eq '{role_name.replace(chr(39), chr(39)+chr(39))}'",
                    "$select": "roleid,name",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if not rows:
            print(f"  Skipped role (not found): {role_name}")
            continue
        role_id = rows[0]["roleid"]
        url = f"{client.base_url}/appmodules({app_id})/appmoduleroles_association/$ref"
        payload = json.dumps({"@odata.id": f"{client.base_url}/roles({role_id})"}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, headers=client.headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60):
                print(f"  Associated role: {role_name}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if "0x80040237" in detail or "duplicate" in detail.lower():
                print(f"  Role already associated: {role_name}")
            else:
                print(f"  Warning: could not associate role {role_name}: {detail}")


def publish_app(client: AppClient, app_id: str) -> None:
    client.post(
        "PublishXml",
        {"ParameterXml": f"<importexportxml><appmodules><appmodule>{app_id}</appmodule></appmodules></importexportxml>"},
    )
    print("  Published app")


def deploy_cre_app(client: AppClient, metadata: dict[str, Any], app_config: dict[str, Any]) -> None:
    solution_name = metadata["solution"]["name"]
    print(f"Deploying CRE app into solution '{solution_name}'...")

    form_ids = build_forms(metadata, client, app_config, solution_name)
    sitemap_id = upsert_sitemap(
        client,
        solution_name,
        app_config["app"]["name"],
        f"{metadata['solution']['prefix']}_{app_config['app']['uniqueName']}",
        build_sitemap_xml(),
    )
    app_id = upsert_app(client, solution_name, app_config)

    components: list[dict[str, Any]] = [
        {"sitemapid": sitemap_id, "@odata.type": "Microsoft.Dynamics.CRM.sitemap"},
    ]
    for form_id in form_ids.values():
        components.append({"formid": form_id, "@odata.type": "Microsoft.Dynamics.CRM.systemform"})
    for view_id in collect_view_ids(client):
        components.append({"savedqueryid": view_id, "@odata.type": "Microsoft.Dynamics.CRM.savedquery"})

    print("Adding components to app...")
    add_app_components(client, app_id, components)
    associate_roles(client, app_id, app_config.get("securityRoles", []))
    publish_app(client, app_id)
    client.post("PublishAllXml", {})
    print(f"\nApp '{app_config['app']['name']}' is ready in Power Apps > Apps.")


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    app_config = json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    base_client = deploy.DataverseClient(environment_url, token)
    client = AppClient(base_client, metadata["solution"]["name"])
    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")
    deploy_cre_app(client, metadata, app_config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
