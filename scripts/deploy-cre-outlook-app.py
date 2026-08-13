#!/usr/bin/env python3
"""Configure App for Outlook prerequisites and broker mailbox settings."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "cre-metadata.json"
APP_CONFIG_PATH = ROOT / "config" / "cre-app.json"
OUTLOOK_APP_PATH = ROOT / "config" / "cre-outlook-app.json"
OUTLOOK_WORKFLOWS_PATH = ROOT / "config" / "cre-outlook-workflows.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_app(client: Any, unique_name: str) -> dict[str, Any] | None:
    for candidate in (unique_name, f"cre_{unique_name}"):
        result = client.get(
            "appmodules?"
            + urllib.parse.urlencode(
                {
                    "$filter": f"uniquename eq '{candidate}'",
                    "$select": "appmoduleid,uniquename,name,statecode,statuscode",
                    "$top": "1",
                }
            )
        )
        rows = result.get("value", [])
        if rows:
            return rows[0]
    return None


def get_organization(client: Any) -> dict[str, Any]:
    result = client.get(
        "organizations?"
        + urllib.parse.urlencode(
            {
                "$select": "organizationid,name,isemailmonitoringallowed,trackingprefix",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    if not rows:
        raise RuntimeError("Organization record not found.")
    return rows[0]


def find_user_by_email(client: Any, email: str) -> dict[str, Any] | None:
    escaped = email.replace("'", "''")
    result = client.get(
        "systemusers?"
        + urllib.parse.urlencode(
            {
                "$filter": f"internalemailaddress eq '{escaped}' and isdisabled eq false",
                "$select": "systemuserid,fullname,internalemailaddress",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0] if rows else None


def find_mailbox(client: Any, email: str) -> dict[str, Any] | None:
    escaped = email.replace("'", "''")
    result = client.get(
        "mailboxes?"
        + urllib.parse.urlencode(
            {
                "$filter": f"emailaddress eq '{escaped}'",
                "$select": "mailboxid,emailaddress,incomingemaildeliverymethod,outgoingemaildeliverymethod,emailrouteraccessapproval",
                "$top": "1",
            }
        )
    )
    rows = result.get("value", [])
    return rows[0] if rows else None


def configure_mailbox(client: Any, email: str, defaults: dict[str, Any]) -> None:
    mailbox = find_mailbox(client, email)
    if not mailbox:
        print(f"  Mailbox not found for {email} (approve email in admin center first)")
        return
    payload = {
        "incomingemaildeliverymethod": defaults.get("incomingEmailDeliveryMethod", 2),
        "outgoingemaildeliverymethod": defaults.get("outgoingEmailDeliveryMethod", 2),
        "emailrouteraccessapproval": defaults.get("emailRouterAccessApproval", 1),
    }
    try:
        client.request("PATCH", f"mailboxes({mailbox['mailboxid']})", payload)
        print(f"  Configured mailbox for server-side sync: {email}")
    except RuntimeError as error:
        print(f"  Skipped mailbox configuration for {email}: {error}")


def configure_organization_tracking(client: Any, tracking: dict[str, Any]) -> None:
    org = get_organization(client)
    org_id = org["organizationid"]
    payload: dict[str, Any] = {}
    if tracking.get("allowTrackingToken") and not org.get("trackingprefix"):
        payload["trackingprefix"] = "CRE:"
    if tracking.get("allowCorrelation"):
        payload["isemailmonitoringallowed"] = True
    if not payload:
        print("  Organization email tracking already configured.")
        return
    try:
        client.request("PATCH", f"organizations({org_id})", payload)
        print("  Updated organization email tracking settings.")
    except RuntimeError as error:
        print(f"  Skipped organization tracking update: {error}")


def deploy_outlook_app(client: Any, metadata: dict[str, Any], outlook_config: dict[str, Any]) -> None:
    solution_name = metadata["solution"]["name"]
    app_unique = outlook_config["modelDrivenApp"]["uniqueName"]
    app = find_app(client, app_unique)
    if not app:
        raise RuntimeError(
            f"Model-driven app '{app_unique}' not found. Run scripts/deploy-cre-app.py first."
        )
    print(f"Model-driven app ready for App for Outlook: {app['name']} ({app['appmoduleid']})")
    if app.get("statecode") != 0:
        print("  Warning: app is not in active state; publish via deploy-cre-app.py")

    configure_organization_tracking(client, outlook_config.get("emailTracking", {}))

    workflows = json.loads(OUTLOOK_WORKFLOWS_PATH.read_text(encoding="utf-8"))
    broker_email = workflows["mailbox"]["address"]
    user = find_user_by_email(client, broker_email)
    if user:
        print(f"Broker user found: {user['fullname']} ({broker_email})")
    else:
        print(f"Broker user not found for {broker_email}; mailbox sync may require manual user setup")

    configure_mailbox(client, broker_email, outlook_config.get("mailboxDefaults", {}))

    entities = ", ".join(outlook_config.get("outlookEntities", []))
    print(f"\nApp for Outlook entity set: {entities}")
    print(f"Solution: {solution_name}")
    print("\nManual rollout (required for App for Outlook add-in):")
    print("  1. Power Platform admin center > Settings > Email > Dynamics 365 App for Outlook")
    print(f"  2. Add model-driven app: {outlook_config['modelDrivenApp']['displayName']}")
    print("  3. Deploy add-in via Microsoft 365 admin center > Integrated apps (or user install from AppSource)")
    print("  4. Each broker signs in once; use Track/Capture in Outlook to link email to CRM records")


def main() -> int:
    deploy = load_module("deploy_cre_model", ROOT / "scripts" / "deploy-cre-model.py")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    outlook_config = json.loads(OUTLOOK_APP_PATH.read_text(encoding="utf-8"))
    environment_url, token = deploy.get_access_token()
    client = deploy.DataverseClient(environment_url, token)
    who = client.get("WhoAmI")
    print(f"Connected to organization: {who.get('OrganizationId')}")
    deploy_outlook_app(client, metadata, outlook_config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
