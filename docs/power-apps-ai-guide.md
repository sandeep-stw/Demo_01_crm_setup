# Step-by-step guide: connect and create a Power App using AI

This guide walks through connecting to Microsoft Power Apps and creating a working app with Copilot and related AI tools. It covers the current maker experiences:

- **Plans** in Power Apps (recommended for canvas and model-driven apps, flows, and agents)
- **Start with data** (Copilot generates Dataverse tables, then an app)
- **Power Apps vibe** at [vibe.powerapps.com](https://vibe.powerapps.com) (preview: plan, data, and a modern web app in one workspace)

Use the path that matches the kind of app you need. Canvas and model-driven apps still come from **make.powerapps.com**. The vibe experience generates a different app type and is not a replacement for classic canvas or model-driven apps.

---

## What you need before you start

| Requirement | Why it matters |
| --- | --- |
| Work or school Microsoft account | Power Apps is tied to a Microsoft Entra tenant, not a personal Microsoft account for most business features. |
| Power Apps license or trial, or a Dynamics 365 / Power Platform environment you can use | You cannot create apps without an environment and maker rights. |
| Environment with a **Dataverse** database | Copilot table generation, Plans, and most AI app creation require Dataverse. |
| **System Customizer** or **System Administrator** (or equivalent table-create privileges) | Copilot cannot create tables if you cannot create Dataverse tables. |
| Environment in a supported region / language | Copilot availability varies by geography. See [Copilot by geography](https://learn.microsoft.com/en-us/power-platform/admin/geographical-availability-copilot). |
| Cross-region data movement (if your environment is not in a generative-AI region) | Admins enable this in the Power Platform admin center when Copilot is blocked. |

Optional but useful:

- A **developer environment** (free for eligible users) if you cannot create tables in a shared production environment.
- **Power Platform CLI (`pac`)** if you work from this repo or need to confirm which Dataverse environment you are connected to.

---

## Part 1 — Connect to Power Apps

### Step 1. Sign in to the maker portal

1. Open [https://make.powerapps.com](https://make.powerapps.com).
2. Sign in with your work or school account.
3. If you are prompted for a tenant or organization, choose the one that contains your Dynamics 365 / Dataverse environment.

### Step 2. Select the correct environment

1. In the top-right of the Power Apps home page, open the **environment picker**.
2. Select the environment that has Dataverse (for this CRM setup, that is usually your Dynamics 365 org).
3. Confirm you can see **Tables**, **Apps**, and **Solutions** in the left navigation. If those are missing, you are probably in an environment without Dataverse or without maker access.

### Step 3. Confirm Dataverse and Copilot (admin or maker)

**Maker check**

1. Go to **Tables**. If you can create a table, Dataverse is available.
2. On the home page, look for **Start with a plan** and **Start with data**. Those are the AI entry points.

**Admin check** (if Copilot is missing)

1. Sign in to [https://admin.powerplatform.microsoft.com](https://admin.powerplatform.microsoft.com).
2. Open **Environments** and select your environment.
3. Confirm a Dataverse database exists. If not, add one (**Settings** / environment setup).
4. Open **Settings** → **Features** and confirm Copilot-related toggles are on (preview Copilot features can be turned off per environment).
5. If Copilot still does not appear, a tenant admin may need **Settings** → **Copilot in Power Apps (preview)** turned **On**.
6. If the environment is outside a generative-AI region, enable **Move data across regions** for Copilot (tenant / environment generative AI settings).

### Step 4. Confirm the connection from this development environment (optional)

This repository installs **Power Platform CLI**. After secrets are configured (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `DATAVERSE_ENVIRONMENT_URL`), the start script authenticates a service principal.

```bash
pac auth who
pac env list
pac env who
```

You should see the Dataverse environment URL you expect (for example `https://orgname.crm.dynamics.com`). CLI auth is for solutions, tables, and deployments. **Creating an app with Copilot is still done in the browser** as the signed-in maker.

---

## Part 2 — Create an app with AI (Plans)

Use this path when you want Copilot to design **user roles, a data model, and the right Power Platform pieces** (canvas app, model-driven app, flow, Copilot Studio agent, and so on) from a business description.

Official reference: [Create a plan](https://learn.microsoft.com/en-us/power-apps/maker/plan-designer/create-plan).

### Step 5. Start a plan

1. Sign in at [https://make.powerapps.com](https://make.powerapps.com).
2. Confirm the environment in the top-right picker.
3. On **Home**, select **Start with a plan**.
4. Select **Create a plan**.
5. Describe the business problem in plain language. Attach process diagrams or screenshots if you have them.
6. Select **Generate**.

**Example prompt (CRM / field work)**

```text
Sales reps need to log customer visits, capture next steps, and request manager
approval when a discount is over 15%. Managers need a queue of pending approvals
and a simple view of visit history by account. Use our Dynamics 365 accounts
where possible.
```

**Example prompt (internal operations)**

```text
Employees submit paid-time-off requests with start date, end date, type
(vacation, sick, personal), and a comment. Managers approve or reject.
HR needs a read-only view of all requests for payroll.
```

If you lack table-create rights in the current environment, Power Apps may route you to a **developer environment**. Continue there, or switch to an environment where you can create Dataverse tables.

### Step 6. Review user requirements

The **Requirements agent** proposes user roles and needs.

1. Read each role (for example Employee, Manager, HR).
2. Select **Edit** to add, rename, or delete roles and needs, or ask Copilot in the plan chat:
   - `Add a user role for HR admin to monitor PTO across teams.`
   - `Add a need for employees to see blackout dates.`
   - `Remove the need for managers to view vacation history.`
3. Select **Looks good** when the roles match the real process.

### Step 7. Review the data model

The **Data agent** proposes tables, columns, types, and relationships.

1. Open **Show details** to inspect the diagram and sample data.
2. Ask Copilot to adjust the model, for example:
   - `Add a choice column Priority with Low, Medium, High.`
   - `Relate Visit to Account with a many-to-one lookup.`
   - `Add Start Time and End Time columns.`
3. Prefer **lookups and choice columns** over free text when the field is a status, type, or related record.
4. Select **Looks good** to continue.

### Step 8. Review the technology proposal

The **Solution agent** suggests apps, flows, sites, or Copilot Studio agents.

1. Hover the information icon on each proposed technology to see which roles and tables it serves.
2. Ask Copilot to change the mix if needed (`Use a model-driven app for managers instead of a canvas app`).
3. Select **Looks good**.

### Step 9. Save tables into a solution

1. Select **Save tables**.
2. Enter a solution name (letters, numbers, and underscores only).
3. Choose a publisher, or pick an existing solution.
4. Select **Save**.

The plan and tables now live in a solution. From the plan you can create the proposed canvas app, model-driven app, flow, or agent.

### Step 10. Create the app from the plan

1. In the plan’s technology / objects view, create the proposed **canvas** or **model-driven** app.
2. Wait until Power Apps Studio (or the model-driven designer) opens with screens bound to the new tables.
3. Do not skip a play-test: add a sample record, edit it, and confirm the list refreshes.

---

## Part 3 — Create an app with AI (Start with data)

Use this path when you already know the data you want to collect and want Copilot to generate **Dataverse tables** and a **canvas app** quickly.

Official reference: [Build apps through conversation with Copilot](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/ai-conversations-create-app).

### Step 11. Open the Copilot table workspace

1. Sign in at [https://make.powerapps.com](https://make.powerapps.com).
2. On **Home**, select **Start with data**.
3. Select **Create new data**.
4. The **Create new tables** workspace opens with a Copilot panel on the right.

### Step 12. Describe the data (and the app)

In the Copilot panel, describe what to track. Be specific about fields, choices, and relationships.

```text
Create tables to track hotel housekeeping tasks including room numbers,
task types, staff assignments, and task status.
```

```text
Create an IT help desk app. Employees submit tickets with requester name,
department, issue description, priority (Low, Medium, High), and status
(New, In progress, Resolved). Managers update status and add resolution notes.
```

Select **Submit** or press Enter. Copilot creates one or more Dataverse tables with sample rows.

### Step 13. Refine tables with Copilot

Use short change requests:

| Goal | Example prompt |
| --- | --- |
| Add columns | `Add columns to track start and end time.` |
| Change types | `Make Priority a choice: Low, Medium, High.` |
| Add related tables | `Add a Staff table and assign each task to a staff member.` |
| Import | Use **Import data** in Copilot to build tables from Excel, CSV, or a SharePoint list. |
| Use existing CRM data | **Existing table** → add Account, Contact, or other Dataverse tables. |

Workspace actions you will use:

- **New table** / **Existing table**
- **View data**
- **Create relationships**
- **Remove** (drops a table from the workspace)

### Step 14. Create the app

1. When the model looks right, select **Save and open app** (wording may be **Save and exit** depending on the build).
2. Copilot creates draft tables and opens a canvas app (typically a list/browse screen plus a form to create and edit records).
3. Save the app with a clear name, for example `Help Desk Tickets`.

---

## Part 4 — Create an app with AI (Power Apps vibe, preview)

Use this path for a **single modern web app** generated with a plan and data model in one surface. It is a preview experience.

Official reference: [Create apps, data, and plans with Power Apps vibe](https://learn.microsoft.com/en-us/power-apps/vibe/create-app-data-plan).

**Limits to know up front**

- Canvas and model-driven apps are **not** authored in vibe.
- One app per plan.
- Sharing typically lets others **play** the app, not edit it.
- Apps created here are not edited in classic Power Apps Studio.

### Step 15. Open vibe and describe the app

1. Go to [https://vibe.powerapps.com](https://vibe.powerapps.com) and sign in  
   **or** on make.powerapps.com select **Try new experience (Preview)**.
2. Confirm the environment.
3. Leave **Plan** mode on (default) so the agent asks clarifying questions before it builds.
4. Type a prompt. Optionally **+ Add work content** (Word, Excel, email, chat) if you have a Copilot license.
5. Optionally use **Start dictation** to speak the prompt.

```text
Create a field inspection app where technicians log site visits, attach photos,
and route findings to a manager for approval.
```

6. Answer follow-up questions. When the plan is correct, select **Accept this plan and create app** → **Submit**.
7. Wait until the workspace shows the generated **app**, **data model**, and **plan**.

### Step 16. Refine in chat, then publish

1. Use the unified chat to change the app or data (`Change the theme to blue`, `Add a Status choice column`).
2. Switch **Data** to review tables. They stay **in memory** until you publish them.
3. Add an existing **Dataverse** table or SharePoint list if you need to connect to data you already have.
4. Select **Publish draft tables** when the schema is ready (target: Dataverse).
5. Select **Publish** on the app command bar. If draft tables remain, you are prompted to publish them too.
6. Select **Share** and add users or security-enabled Microsoft Entra groups (group sharing works in production environments, not developer environments).

New apps created after 9 April 2026 autosave. Older vibe apps may still need **Save** on the command bar.

---

## Part 5 — Connect additional data to an existing canvas app

Copilot often starts you on **new Dataverse tables**. To connect SharePoint, Excel, SQL, Dynamics tables, or other connectors, add connections in Power Apps Studio.

Official reference: [Add data connections](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/add-data-connection).

### Step 17. Add a connection

1. Open the canvas app in **Power Apps Studio** (make.powerapps.com → **Apps** → app → **Edit**).
2. On the left authoring menu, select **Data**.
3. Select **Add data**.
4. Search for the connector (`Dataverse`, `SharePoint`, `Excel`, `SQL Server`, `Office 365 Users`).
5. Select an existing connection, or **Add a connection** and complete sign-in.

**Dataverse (including Dynamics 365 tables)**

1. Search **Dataverse**.
2. Pick the environment if it is not the current one.
3. Select tables (for example **Account**, **Contact**, **Opportunity**).
4. Bind a gallery `Items` property to the table, for example `Accounts`.

**SharePoint list**

1. Search **SharePoint**.
2. Sign in if prompted.
3. Enter the site URL (or pick a recent site).
4. Select the list.
5. Set a gallery `Items` to that list.

**Excel on OneDrive or SharePoint**

1. Format the sheet as a **table** in Excel first.
2. Add the **Excel** connector and pick the file and table.

**SQL Server**

1. Add **SQL Server**.
2. Provide server, database, and authentication.
3. If SQL is on-premises, use an **on-premises data gateway** that is online.

### Step 18. Point screens at the new source

1. Select the gallery or form.
2. On the **Properties** pane, change **Data source** / **Items**.
3. For forms, set **DataSource**, then **Item** (for example `Gallery1.Selected`), and regenerate fields if the schema changed.

If a connection vanished, it likely expired. **Add data** again and re-authenticate.

---

## Part 6 — Improve the app with Copilot after it exists

In Power Apps Studio, open **Copilot** (upper-right) and describe UI changes. Microsoft has been shifting **new** Copilot-first creation toward **Plans** (and vibe). Studio Copilot, when available in your tenant, can still help with screens and control properties.

Useful prompts:

```text
Add a new screen with header, body, and footer
Add a submit button and a cancel button to the form
When the user selects Button1, show Screen2
Change all buttons to gray
Change my app to deep forest green
```

If Copilot cannot apply a change, it often returns manual steps. Prefer **Plans** for data-model and multi-object solution changes.

---

## Part 7 — Test, save, publish, and share

### Step 19. Play-test like a user

1. In Studio, select **Play** (preview).
2. Create a record, edit it, and delete it if that is in scope.
3. Sign in as (or use **App checker** / test accounts for) each role: requester vs manager.
4. Confirm lookups to Dynamics tables (Account, and so on) return the records you expect.
5. On a phone or tablet, use Power Apps mobile or a QR / browser preview if the app is for field users.

### Step 20. Save and publish

1. **File** → **Save** (or Ctrl+S). Use a name and description that match the solution.
2. **Publish** so users get the latest version. Saving alone does not always update the live app.
3. Run **App checker** and fix errors and accessibility issues.

### Step 21. Share

1. From the app, select **Share**.
2. Add users or security groups.
3. Grant **User** (run) or **Co-owner** (edit) as appropriate.
4. If the app uses Dataverse, also share **table permissions** via security roles. Sharing the app without table rights shows empty galleries or create failures.
5. For model-driven apps, users need a Dynamics / Power Apps license and a security role on those tables.

---

## Prompt patterns that produce better apps

**Include**

- Who uses the app (roles)
- What they must do (create, approve, search, attach files)
- Fields and allowed values
- Relationships (ticket belongs to requester, visit belongs to account)
- What must **not** happen (employees cannot approve their own request)

**Avoid**

- One-line prompts with no fields (`make a CRM app`)
- Mixing unrelated processes in one prompt
- Asking Copilot to “connect to everything” without naming the system (SharePoint site, Dataverse table, SQL database)

**Copy-paste starter for this CRM tenant**

```text
Build a canvas app for sales visit notes.

Roles:
- Seller: create a visit against an existing Account, set visit date, purpose
  (choice: Discovery, Demo, Negotiation, Support), notes, and next step date.
- Manager: see team visits this week and mark a visit as Reviewed.

Data:
- Use the existing Dataverse Account table.
- Create a Visit table with lookup to Account, VisitDate, Purpose, Notes,
  NextStepDate, Status (New, Reviewed).

Do not create a new Account table.
```

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| No Copilot / Start with a plan | Confirm environment region, Dataverse, maker role, and tenant Copilot settings. Try a **developer environment**. |
| Alert that you cannot create tables | You lack Dataverse create privileges. Switch environment or use a personal developer environment. |
| Copilot generates the wrong tables | Name existing tables explicitly (`Do not create Account; use existing Account`). Add **Existing table** before you save. |
| Empty gallery after connecting Dataverse | Wrong environment, missing security role, or `Items` still points at the old sample table. |
| SharePoint connection fails | Site URL, list permissions, or a list accessed only through an environment variable (some Copilot features ignore that pattern). |
| SQL / on-prem data fails | Gateway offline, or credentials not valid for the gateway. |
| Vibe app not visible in Studio | Expected. Vibe apps are edited in the vibe workspace, not classic canvas Studio. |
| Users can open the app but cannot save records | App is shared; **table privileges** are not. Update the Dataverse security role. |

---

## How this maps to this repository

This repo (`demo_01_crm_setup`) prepares a Cloud Agent environment with .NET, Node, and **pac** against your Dataverse / Dynamics 365 org. Typical split of work:

1. **Browser (you as maker):** connect at make.powerapps.com, run Copilot / Plans, create and publish the app.
2. **CLI (this environment):** `pac auth who`, `pac env who`, `pac solution list` to confirm the same environment and to export/import the solution that contains the plan, tables, and app.

Keep AI-generated tables and apps **inside a solution** so you can move them between environments with `pac solution` commands.

---

## Official documentation

- [Copilot in Power Apps overview](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/ai-overview)
- [Build apps through conversation with Copilot](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/ai-conversations-create-app)
- [Use plans to create AI-powered solutions](https://learn.microsoft.com/en-us/power-apps/maker/plan-designer/plan-designer)
- [Create a plan](https://learn.microsoft.com/en-us/power-apps/maker/plan-designer/create-plan)
- [Power Apps vibe overview](https://learn.microsoft.com/en-us/power-apps/vibe/overview)
- [Create apps, data, and plans with vibe](https://learn.microsoft.com/en-us/power-apps/vibe/create-app-data-plan)
- [Add data connections](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/add-data-connection)
- [Add and manage connections](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/add-manage-connections)
- [Copilot geography and languages](https://learn.microsoft.com/en-us/power-platform/admin/geographical-availability-copilot)
