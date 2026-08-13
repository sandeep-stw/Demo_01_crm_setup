#!/usr/bin/env python3
"""Build Dataverse systemform XML for CRE entities."""

from __future__ import annotations

import html
import uuid
from typing import Any

CONTROL_CLASSIDS = {
    "String": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",
    "Url": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",
    "Memo": "{E0DECE4B-6FC8-4a8f-A065-082708572369}",
    "Integer": "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}",
    "Decimal": "{C3EFE0C3-0EC6-42be-8349-CBD9079C5A6F}",
    "Money": "{533B9108-5A8B-42cb-BD37-52D1B8E7C741}",
    "Boolean": "{67FAC785-CD58-4f9f-ABB3-4B7DDC6ED5ED}",
    "DateTime": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}",
    "Picklist": "{3EF39988-22BB-4f0b-BBBE-64B5A3748AEE}",
    "MultiSelectPicklist": "{0D1D45EF-ED88-46BE-B977-A5EC6F2CF9CB}",
    "Lookup": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
}

STANDARD_STRING_FIELDS = {
    "firstname": "First Name",
    "lastname": "Last Name",
    "emailaddress1": "Email",
    "telephone1": "Business Phone",
    "jobtitle": "Job Title",
    "name": "Account Name",
    "telephone1_account": "Main Phone",
}


def new_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def field_classid(field: dict[str, Any]) -> str:
    return CONTROL_CLASSIDS.get(field["type"], CONTROL_CLASSIDS["String"])


def xml_text(value: str) -> str:
    return html.escape(value, quote=True)


def cell_xml(field: dict[str, Any]) -> str:
    schema = field["schemaName"]
    label = xml_text(field["displayName"])
    classid = field_classid(field)
    return (
        f'<row><cell id="{new_guid()}" showlabel="true">'
        f'<labels><label description="{label}" languagecode="1033" /></labels>'
        f'<control id="{schema}" classid="{classid}" datafieldname="{schema}" disabled="false" />'
        f"</cell></row>"
    )


def section_xml(title: str, fields: list[dict[str, Any]], columns: int = 1) -> str:
    rows = "".join(cell_xml(field) for field in fields)
    colspan = "111" if columns == 3 else ("11" if columns == 2 else "1")
    safe_title = xml_text(title)
    return (
        f'<section name="{new_guid()}" showlabel="true" showbar="true" IsUserDefined="1" columns="{colspan}">'
        f'<labels><label description="{safe_title}" languagecode="1033" /></labels>'
        f"<rows>{rows}</rows></section>"
    )


def tab_xml(title: str, sections: list[str]) -> str:
    body = "".join(sections)
    safe_title = xml_text(title)
    return (
        f'<tab name="{new_guid()}" verticallayout="true" id="{new_guid()}" IsUserDefined="1" expanded="true">'
        f'<labels><label description="{safe_title}" languagecode="1033" /></labels>'
        f'<columns><column width="100%"><sections>{body}</sections></column></columns>'
        f"</tab>"
    )


def notes_tab_xml() -> str:
    return (
        f'<tab name="{new_guid()}" verticallayout="true" id="{new_guid()}" IsUserDefined="1" expanded="true">'
        '<labels><label description="Notes" languagecode="1033" /></labels>'
        '<columns><column width="100%"><sections>'
        f'<section name="{new_guid()}" showlabel="false" showbar="false" IsUserDefined="0">'
        '<labels><label description="Notes" languagecode="1033" /></labels>'
        f'<rows><row><cell showlabel="false" rowspan="10" auto="false" id="{new_guid()}">'
        '<labels><label description="Note Text" languagecode="1033" /></labels>'
        '<control id="notescontrol" classid="{06375649-c143-495e-a496-c962e5b4488e}">'
        "<parameters><DefaultTabId>NotesTab</DefaultTabId></parameters>"
        "</control></cell></row></rows></section>"
        "</sections></column></columns></tab>"
    )


def subgrid_tab_xml(
    title: str,
    relationship_name: str,
    target_entity: str,
    view_id: str,
) -> str:
    view_ref = view_id if view_id.startswith("{") else f"{{{view_id}}}"
    safe_title = xml_text(title)
    control_id = "cre_propertysuites_subgrid"
    return (
        f'<tab name="{new_guid()}" verticallayout="true" id="{new_guid()}" IsUserDefined="1" expanded="true">'
        f'<labels><label description="{safe_title}" languagecode="1033" /></labels>'
        '<columns><column width="100%"><sections>'
        f'<section name="{new_guid()}" showlabel="true" showbar="true" IsUserDefined="1">'
        f'<labels><label description="{safe_title}" languagecode="1033" /></labels>'
        f'<rows><row><cell colspan="1" rowspan="6" id="{new_guid()}">'
        f'<labels><label description="{safe_title}" languagecode="1033" /></labels>'
        f'<control id="{control_id}" classid="{{E7A81278-8635-4d9e-8D4D-59480B391C5B}}">'
        "<parameters>"
        f"<TargetEntityType>{target_entity}</TargetEntityType>"
        f"<ViewId>{view_ref}</ViewId>"
        f"<RelationshipName>{relationship_name}</RelationshipName>"
        "</parameters></control></cell></row></rows></section>"
        "</sections></column></columns></tab>"
    )


def build_form(tabs: list[str]) -> str:
    return f"<form><tabs>{''.join(tabs)}</tabs></form>"


def standard_field(schema: str, label: str, field_type: str = "String") -> dict[str, Any]:
    return {"schemaName": schema, "displayName": label, "type": field_type}


def build_property_form(
    fields_by_section: dict[str, list[dict[str, Any]]],
    suite_view_id: str | None = None,
    suite_relationship_name: str | None = None,
) -> str:
    tabs = []
    for title, fields in fields_by_section.items():
        tabs.append(tab_xml(title, [section_xml(title, fields)]))
    if suite_view_id and suite_relationship_name:
        tabs.append(
            subgrid_tab_xml(
                "Property Suites",
                suite_relationship_name,
                "cre_propertysuite",
                suite_view_id,
            )
        )
    tabs.append(notes_tab_xml())
    return build_form(tabs)


def build_simple_form(sections: dict[str, list[dict[str, Any]]], include_notes: bool = True) -> str:
    tabs = [tab_xml(title, [section_xml(title, fields)]) for title, fields in sections.items()]
    if include_notes:
        tabs.append(notes_tab_xml())
    return build_form(tabs)


def field_lookup(metadata_fields: list[dict[str, Any]], schema_name: str) -> dict[str, Any]:
    for field in metadata_fields:
        if field["schemaName"] == schema_name:
            return field
    raise KeyError(schema_name)


def pick_fields(metadata_fields: list[dict[str, Any]], schema_names: list[str]) -> list[dict[str, Any]]:
    return [field_lookup(metadata_fields, name) for name in schema_names]
