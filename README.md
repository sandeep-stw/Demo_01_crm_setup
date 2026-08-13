# Demo CRM Setup

Cloud Agent development environment and **Commercial Real Estate (CRE) relationship management** solution for Microsoft Dynamics 365 / Dataverse.

## Stack

- **.NET 9 SDK** and **Power Platform CLI (`pac`)**
- **Dataverse Web API** deployment scripts
- **Solution project**: `solutions/CreRelationshipManagement`

## CRE data model

See [docs/cre-relationship-management.md](docs/cre-relationship-management.md) for the full specification:

- **Contact** — multi-select relationship classifications, professional designations, CRE custom fields
- **Account** — CRE classifications, portfolio and industry fields
- **Property** (`cre_property`) — property, building, leasing, and ownership data
- **Property Suite** (`cre_propertysuite`) — multi-tenant suite roster
- **Saved views** — tenant requirements, lease expirations, stale contacts, listings, portfolios, SIOR members
- **Model-driven app** — CRE Relationship Hub with forms and navigation
- **Cloud flow** — email with "new lead" in subject → new Lead record
- **Phase 2 Deal pipeline** — opportunity fields, CRE Opportunity form, pipeline views, stage-change flow
- **Phase 3 Outlook** — App for Outlook rollout, calendar logging flow, unknown-sender alert flow

See [docs/cre-phase2-deal-pipeline.md](docs/cre-phase2-deal-pipeline.md) for deal pipeline setup (issue [#3](https://github.com/sandeep-stw/Demo_01_crm_setup/issues/3)).
See [docs/cre-phase3-outlook.md](docs/cre-phase3-outlook.md) for Outlook-first workflow setup (issue [#4](https://github.com/sandeep-stw/Demo_01_crm_setup/issues/4)).

### Deploy to Dataverse

```bash
./scripts/deploy-cre-solution.sh
```

Requires environment secrets: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `DATAVERSE_ENVIRONMENT_URL`.

## Cloud Agent environment

```bash
./scripts/cloud-agent-install.sh
./scripts/cloud-agent-start.sh
```

Configuration: `.cursor/environment.json`

