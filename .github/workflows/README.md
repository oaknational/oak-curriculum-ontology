# GitHub Actions Workflows

## Export to Neo4j Workflow

This workflow allows manual exports of curriculum data to Neo4j AuraDB.

### Setup

This workflow uses **GitHub Environment protection** to ensure only authorized admins can run exports.

**Important**: The GitHub Environment (called "production") is just a GitHub Actions security feature - it's **NOT** related to your Neo4j database environment. Your actual Neo4j database is a **development** environment. The GitHub Environment name is simply used for access control.

#### Step 1: Create Protected Environment

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Environments**
3. Click **New environment**
4. Name it: `production` (this is just a GitHub Actions label, not your database environment)
5. Click **Configure environment**
6. Under **Environment protection rules**:
   - Check **Required reviewers**
   - Add admin users who should approve exports (at least one)
   - Click **Save protection rules**

#### Step 2: Add Environment Secrets

Still in the `production` GitHub Environment settings:

1. Scroll down to **Environment secrets**
2. Click **Add secret** for each of the following:
   - `NEO4J_URI` - Your **development** Neo4j AuraDB connection URI (e.g., `neo4j+s://xxxxx.databases.neo4j.io`)
   - `NEO4J_USERNAME` - Your Neo4j username (typically `neo4j`)
   - `NEO4J_PASSWORD` - Your Neo4j password

**Note**:
- These secrets point to your **development Neo4j database**
- They're stored in the GitHub "production" environment (just a name for access control)
- Only accessible when the workflow runs with admin approval

### Usage

1. Go to **Actions** tab in GitHub
2. Select **Export Curriculum Data to Neo4j** workflow
3. Click **Run workflow** button
4. Choose options:
   - **What to export**:
     - `Oak Curriculum only` - Export only Oak data
     - `Both DfE and Oak Curriculum` - Export DfE data first, then Oak data
   - **Clear existing data before import**:
     - `true` - Clear data before importing (fresh import)
     - `false` - Append to existing data (incremental update)
5. Click **Run workflow**

#### Approval Process

Because this workflow uses the `production` GitHub Environment with required reviewers:

1. After clicking **Run workflow**, the workflow will start but **pause** before executing
2. GitHub will show: **"Waiting for review"** and notify the required reviewers
3. A required reviewer must:
   - Go to the workflow run
   - Click **Review deployments**
   - Approve or reject the deployment
4. Only after approval will the export run and modify your **development Neo4j database**
5. If rejected, the workflow is cancelled and no changes are made

This ensures **admin-only control** over Neo4j database modifications.

### Export Options

#### Oak Curriculum only
- Exports data from `data/oak-curriculum/` directory
- Creates/updates nodes labeled `Oak`
- Creates relationships to existing DfE nodes
- Faster (only one export)

#### Both DfE and Oak Curriculum
- First exports DfE National Curriculum data from `uk-curriculum-ontology` repo
- Then exports Oak data and links to DfE nodes
- Use this when:
  - Setting up from scratch
  - DfE curriculum has been updated
  - You want to ensure DfE nodes exist before Oak export

### Clear Data Option

- **false** (default): Appends to existing data. Use for incremental updates when only TTL files have changed.
- **true**: Clears all data of the specified scope before importing. Use when:
  - You want a fresh import
  - Data structure has changed significantly
  - You're troubleshooting data issues

### Security Notes

**Clarification**: The GitHub "production" environment is just an access control mechanism. The workflow actually exports to your **development Neo4j database**.

**Who can trigger the workflow:**
- Any repository collaborator with **write access** can trigger the workflow
- Public users cannot trigger workflows (even in public repos)

**Who can approve the workflow:**
- Only users designated as **required reviewers** in the `production` environment
- Typically repository admins only
- At least one required reviewer must approve before the export runs

**Secrets protection:**
- GitHub Secrets are encrypted and never exposed in logs (even in public repos)
- Environment secrets are only accessible during approved deployments
- Secret values are automatically redacted from workflow logs

### Technical Notes

- The workflow requires access to the `oaknational/uk-curriculum-ontology` repository when exporting DfE data
- Export duration depends on data size (typically 1-5 minutes)
- Check workflow logs for detailed progress and any errors
- The workflow uses Python 3.12 and installs dependencies from `pyproject.toml`
