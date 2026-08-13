# Phase 2 — Deal Pipeline

**Status: Complete** (GitHub issue [#3](https://github.com/sandeep-stw/Demo_01_crm_setup/issues/3))

Deal pipeline configuration for CRE opportunities: custom fields, forms, views, stage automation, and business-process-flow specifications for all seven business lines.

## Deploy

```bash
python3 ./scripts/deploy-cre-deal-pipeline.py
python3 ./scripts/deploy-cre-pipeline-stage-flow.py
python3 ./scripts/register-cre-solution-components.py
```

Or run the full pipeline: `./scripts/deploy-cre-solution.sh`

## Opportunity custom fields

| Field | Type | Purpose |
| --- | --- | --- |
| `cre_businessline` | Choice | One of seven CRE business lines |
| `cre_propertyid` | Lookup | Related property |
| `cre_dealsizesf` | Integer | Deal size in square feet |
| `cre_leasetermmonths` | Integer | Lease term |
| `cre_saleprice` | Money | Sale price |
| `cre_caprate` | Decimal | Cap rate |
| `cre_loaninformation` | Memo | Loan details |
| `cre_loiofferdate` | Date | LOI / offer date |
| `cre_targetclosedate` | Date | Target close date |
| `cre_pipelinestage` | Choice | Pipeline stage |
| `cre_grosscommission` / `cre_netcommission` | Money | Commission totals |
| `cre_expectedcommission` / `cre_actualcommission` | Money | Forecast vs actual |
| `cre_commissionmethod` | Choice | % lease, % sale, flat fee, custom |
| `cre_referralfees` / `cre_outsidebrokerfees` / `cre_cobrokerfees` | Money | Fee breakdown |
| `cre_houseportion` / `cre_brokerportion` | Money | Split amounts |
| `cre_commissionadjustments` | Money | Adjustments |
| `cre_cobrokerid` | Lookup (Account) | Co-broker |
| `cre_dealreferralsource` | Text | Referral source |
| `cre_dealnotes` | Memo | Deal notes |

Standard opportunity fields used: `name`, `customerid`, `estimatedvalue`, `closeprobability`, `estimatedclosedate`, `ownerid`.

Configuration source: `config/cre-deal-pipeline.json`

## Business process flows (7 business lines)

Stage definitions are in `config/cre-deal-pipeline.json` under `businessProcessFlows`. Create each BPF in **Power Apps → Solutions → CRE Relationship Management → New → Automation → Business process flow**:

| BPF | Business line | Stages |
| --- | --- | --- |
| CRE - Tenant Representation Deal Process | Tenant Representation | Qualify Requirement → Site Tour → LOI Negotiation → Lease Execution → Close |
| CRE - Landlord Representation Deal Process | Landlord Representation | Listing Setup → Marketing → Tenant Prospects → LOI → Lease Signed → Close |
| CRE - Investment Sales Deal Process | Investment Sales | Qualify → Underwriting → Marketing → LOI / Offer → Due Diligence → Close |
| CRE - Property Management Deal Process | Property Management | Intake → Proposal → Negotiation → Award → Onboarding → Close |
| CRE - Development Deal Process | Development | Site Selection → Feasibility → Entitlements → Financing → Construction → Close |
| CRE - Capital Markets Deal Process | Capital Markets | Qualify → Package Loan → Lender Outreach → Term Sheet → Closing → Funded |
| CRE - Retail Site Selection Deal Process | Retail Site Selection & Consulting | Criteria → Market Survey → Site Tours → LOI → Lease → Close |

For each BPF:

1. Entity: **Opportunity**
2. Add stages from the table above
3. Add **Business Line** (`cre_businessline`) to the first stage
4. Add required deal/commission fields per stage in the designer
5. Activate the BPF and add it to **CRE Relationship Hub**

## Stage automation

Cloud flow **CRE - Deal Stage Change Task** creates a follow-up task when `cre_pipelinestage` changes on an opportunity.

Deploy: `python3 ./scripts/deploy-cre-pipeline-stage-flow.py`

Activate in Power Automate (sign in Dataverse connection, turn On).

## Saved views

- **CRE - Open Deals by Business Line**
- **CRE - Deals Closing This Quarter**

## CRE Opportunity form

Form **CRE Opportunity** includes **Deal** and **Commission** tabs with all custom fields. Added to the **CRE Relationship Hub** app navigation.

## Issue coverage

| Requirement | Status |
| --- | --- |
| Opportunity custom fields | Deployed via `deploy-cre-deal-pipeline.py` |
| Seven business-line BPFs | Stage specs in config; create in BPF designer (see table) |
| Stage-level automation | **CRE - Deal Stage Change Task** flow |
| Pipeline views & form | Deployed |
