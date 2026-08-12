# Demo CRM Setup

Cloud Agent development environment for **Microsoft Dynamics 365 CRM** and the **Power Platform**.

## Stack

- **.NET SDK 8** for plugin and integration development
- **Power Platform CLI (`pac`)** for Dataverse, solutions, and deployments
- **Node.js 22** for Power Apps component framework (PCF) development

## Local setup

```bash
./scripts/cloud-agent-install.sh
./scripts/cloud-agent-start.sh
```

## Authentication

The start script authenticates with a service principal when these environment secrets are configured:

| Secret | Description |
| --- | --- |
| `AZURE_TENANT_ID` | Microsoft Entra tenant ID |
| `AZURE_CLIENT_ID` | App registration (service principal) client ID |
| `AZURE_CLIENT_SECRET` | App registration client secret |
| `DATAVERSE_ENVIRONMENT_URL` | Dataverse environment URL, e.g. `https://orgname.crm.dynamics.com` |

The app registration must be added as an application user in your Dataverse environment with appropriate security roles.

## Common commands

```bash
pac auth who
pac env list
pac env who
pac solution list
```

## Cloud Agent

Environment configuration lives in `.cursor/environment.json`. The custom Dockerfile provides .NET and Node; the install script adds the Power Platform CLI; the start script connects to your Dynamics 365 environment when secrets are available.
