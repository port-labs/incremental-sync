# incremental-sync

This repository contains the code for incremental and periodic sync of Azure resources, subscriptions and resources groups (Azure Resources are prioritized in detail) into Port.

The code is written in Python and uses the Azure SDK for Python to interact with Azure resources. It is designed to be run in a GitHub workflow in periodic intervals to keep the Port data up-to-date.

## Installation

### Azure Setup

Both ways of running this application requires you to set up an Azure application. You can follow the steps in the [Azure documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app) to create an Azure application. You do not need a Redirect URI for this application. In addition, ensure that the Azure application has the required permissions to access the Azure resources.

Keep the following values handy:

- `AZURE_CLIENT_ID`: The client ID of the Azure service principal.
- `AZURE_CLIENT_SECRET`: The client secret of the Azure service principal.
- `AZURE_TENANT_ID`: The tenant ID of the Azure service principal.

### Required Azure Permissions Setup

After creating your Azure App Registration, you need to configure the following permissions and roles:

#### 1. API Permissions
1. Go to Azure Portal → Azure Active Directory → App registrations
2. Find your app registration
3. Click on "API permissions" in the left menu
4. Click "Add a permission"
5. Add the following permissions:
   - **Azure Service Management**
     - Select "user_impersonation"
     - Click "Add permissions"
   - **Azure Resource Graph**
     - Click on "APIs my organization uses" tab
     - Search for "Azure Resource Graph"
     - Select "Read" permission
     - Click "Add permissions"
6. Click "Grant admin consent" for your organization for both permissions

#### 2. Role Assignments
1. Go to your Azure subscription
2. Click on "Access control (IAM)"
3. Click "Add" → "Add role assignment"
4. Assign the following role:
   - Select "Reader" role
   - In the Members tab, search for your app registration
   - Select it and click "Select"
   - Click "Review + assign"

#### 3. Verification
You can verify your setup is working by:
1. Running the integration
2. Checking if it can successfully:
   - List your subscriptions
   - Query Azure Resource Graph
   - Read resource information

If you encounter "Access Denied" errors, double-check that both the API permissions and role assignments are properly configured.

### Port Setup

#### Port Credentials

Next, get your Port client ID and client secret by clicking on the three dots on the top right corner of the Port UI and selecting "Credentials". You will find the client ID and client secret there.

#### Configuring blueprints for Azure resources ingestion

Blueprints representing Azure resources should be created in Port before syncing the Azure resources. The blueprints configuration below are for illustrative purposes only. You can create your own blueprints configuration based on your requirements.

Below are the blueprint examples that should be created in Port:

1. `azureSubscription` blueprint:

```json
{
  "identifier": "azureSubscription",
  "title": "Azure Subscription",
  "icon": "Azure",
  "schema": {
    "properties": {
      "subscriptionId": {
        "title": "Subscription ID",
        "type": "string"
      },
      "tags": {
        "title": "Tags",
        "type": "object"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {}
}
```

2. `azureResourceGroup` blueprint:

```json
{
  "identifier": "azureResourceGroup",
  "description": "This blueprint represents an Azure Resource Group in our software catalog",
  "title": "Azure Resource Group",
  "icon": "Azure",
  "schema": {
    "properties": {
      "location": {
        "title": "Location",
        "type": "string"
      },
      "tags": {
        "title": "Tags",
        "type": "object"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {
    "subscription": {
      "title": "Subscription",
      "target": "azureSubscription",
      "required": false,
      "many": false
    }
  }
}
```

3. `azureCloudResources` blueprint:

```json
{
  "identifier": "azureCloudResources",
  "description": "This blueprint represents an AzureCloud Resource in our software catalog",
  "title": "Azure Cloud Resources",
  "icon": "Git",
  "schema": {
    "properties": {
      "tags": {
        "title": "Tags",
        "type": "object"
      },
      "type": {
        "title": "Type",
        "type": "string"
      },
      "location": {
        "title": "Location",
        "type": "string"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {
    "resourceGroup": {
      "title": "Resource Group",
      "target": "azureResourceGroup",
      "required": false,
      "many": false
    }
  }
}
```

#### Setting up Port webhook

Webhooks on Port are used in this application to allow for flexible schema when ingesting Azure resources. To set up a webhook on Port, follow these steps:

- From the "Builder" page, click on "Data Sources" on the left sidebar.
- Click on "Add Data Source" and select "Webhook".
- Fill in the required fields and click on "Create Data Source".
- Copy the webhook URL and keep it handy.

You can use the webhook mapping below to map the Azure resources to the blueprints in the `"Map the data from the external system into Port"` field. The mapping contains relevant configuration for both upsert and delete operations. The mapping is for illustrative purposes only. You can create your own mapping based on your requirements:

**Note:** 
- The `body.operation` field is not part of the Azure resource payload and is only present as a discriminator for the webhook.
- The `body.type` field contains the type of the Azure resource
  - `resource` for Azure resources
  - `resourceContainer` for Azure resource containers (e.g. resource groups, subscriptions)
- The `body.data` field contains the Azure resource payload.
- The `body.data.type` field contains the type of the Azure resource
  - `microsoft.resources/subscriptions/resourcegroups` for resource groups
  - `microsoft.resources/subscriptions` for subscriptions
  - `microsoft.network/networksecuritygroups` for network security groups


```json
[
  {
    "blueprint": "azureCloudResources",
    "operation": "create",
    "filter": ".body.type == 'resource' and .body.operation == 'upsert'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")",
      "title": ".body.data.name",
      "properties": {
        "tags": ".body.data.tags",
        "type": ".body.data.type",
        "location": ".body.data.location"
      },
      "relations": {
        "resourceGroup": "'/subscriptions/' + .body.data.subscriptionId + '/resourcegroups/' + .body.data.resourceGroup | gsub(\" \";\"_\")"
      }
    }
  },
  {
    "blueprint": "azureCloudResources",
    "operation": "delete",
    "filter": ".body.type == 'resource' and .body.operation == 'delete'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")"
    }
  },
  {
    "blueprint": "azureResourceGroup",
    "operation": "create",
    "filter": ".body.data.type == 'microsoft.resources/subscriptions/resourcegroups' and .body.operation == 'upsert'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")",
      "title": ".body.data.name",
      "properties": {
        "tags": ".body.data.tags",
        "location": ".body.data.location"
      },
      "relations": {
        "subscription": "'/subscriptions/' + .body.data.subscriptionId | gsub(\" \";\"_\")"
      }
    }
  },
  {
    "blueprint": "azureResourceGroup",
    "operation": "delete",
    "filter": ".body.data.type == 'microsoft.resources/subscriptions/resourcegroups' and .body.operation == 'delete'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")"
    }
  },
  {
    "blueprint": "azureSubscription",
    "operation": "create",
    "filter": ".body.data.type == 'microsoft.resources/subscriptions' and .body.operation == 'upsert'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")",
      "title": ".body.data.name",
      "properties": {
        "subscriptionId": ".body.data.subscriptionId",
        "tags": ".body.data.tags"
      }
    }
  },
  {
    "blueprint": "azureSubscription",
    "operation": "delete",
    "filter": ".body.data.type == 'microsoft.resources/subscriptions' and .body.operation == 'delete'",
    "entity": {
      "identifier": ".body.data.resourceId | gsub(\" \";\"_\")"
    }
  }
]
```

### GitHub Actions

To run the application in a GitHub workflow, ensure you do the following in the GitHub workflow:

- Set the following secrets in your GitHub repository:

  - `AZURE_CLIENT_ID` (type: str): The client ID of the Azure service principal.
  - `AZURE_CLIENT_SECRET` (type: str): The client secret of the Azure service principal.
  - `AZURE_TENANT_ID` (type: str): The tenant ID of the Azure service principal.
  - `PORT_WEBHOOK_INGEST_URL` (type: str): The webhook URL to ingest the Azure resources into Port.

Additional environment variables:
  - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is `1000` which is also the maximum size.
  - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is `15` minutes.
  - `RESOURCE_TYPES` (type str): The Azure resource types to sync. Default is All, which means all resource types will be synced. You can specify a comma-separated list of resource types to sync. For example, `export RESOURCE_TYPES='["microsoft.keyvault/vaults","Microsoft.Network/virtualNetworks", "Microsoft.network/networksecuritygroups"]'`
  - `RESOURCE_GROUP_TAG_FILTERS` (type: str): JSON string of key-value pairs for filtering resources based on their resource group tags. For example, `'{"Environment": "Production", "Team": "Platform"}'`
  - `EXCLUDE_RESOURCES_BY_RG_TAGS` (type: bool): Whether to exclude resources that match the resource group tag filters (true) or include only resources that match (false). Default is `false`.

- The GitHub workflow steps should checkout into the repository, install the required packages using Poetry, and run the script to sync the Azure resources into Port with the following command:

```bash
make run
```

An example of a GitHub workflow which runs the sync every 15 minutes is shown below:

```yml
name: "Incremental sync of Azure resources to Port"
on:
  schedule: # run every 15 minutes
    - cron: "*/15 * * * *"

jobs:
  sync:
    name: Incremental sync
    runs-on: ubuntu-latest
    steps:
      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Checkout To Repository
        uses: actions/checkout@v2
        with:
          ref: main
          repository: port-labs/incremental-sync

      - name: Install dependencies with Poetry
        run: |
          cd integrations/azure_incremental
          python -m pip install --upgrade pip
          pip install poetry
          make install

      - name: Run incremental sync
        run: |
          cd integrations/azure_incremental
          make run
        env:
          AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          PORT_WEBHOOK_INGEST_URL: ${{ secrets.PORT_WEBHOOK_INGEST_URL }}
          CHANGE_WINDOW_MINUTES: 15
          # Optional: Filter resources by resource group tags
          # RESOURCE_GROUP_TAG_FILTERS: '{"Environment": "Production"}'
          # EXCLUDE_RESOURCES_BY_RG_TAGS: false
```

An example of a GitHub workflow which runs full sync manually is shown below:

:warning: It is recommended to run the full sync manually as it may take a long time to complete, depending on the number of Azure resources, subscriptions, and resource groups.

```yml

name: "Full sync of Azure resources to Port"

on:
  - workflow_dispatch

jobs:
  - name: Full sync
    runs-on: ubuntu-latest
    steps:
      - name: Checkout To Repository
        uses: actions/checkout@v2
        with:
          ref: main
          repository: port-labs/incremental-sync

      - name: Install dependencies with Poetry
        run: |
          cd integrations/azure_incremental
          python -m pip install --upgrade pip
          pip install poetry
          make install

      - name: Run full sync
        run: |
          cd integrations/azure_incremental
          make run
        env:
          AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          PORT_WEBHOOK_INGEST_URL: ${{ secrets.PORT_WEBHOOK_INGEST_URL }}
          SYNC_MODE: full
```


### Local

- Clone this repository.

- Install the required Python packages (The repository uses Python 3.12). You should have Poetry installed, if not, you can install it by running `pip install poetry`.

```bash
make install
```

- Set the following environment variables:

  - `AZURE_CLIENT_ID` (type: str): The client ID of the Azure service principal.
  - `AZURE_CLIENT_SECRET` (type: str): The client secret of the Azure service principal.
  - `AZURE_TENANT_ID` (type: str): The tenant ID of the Azure service principal.
  - `PORT_WEBHOOK_INGEST_URL` (type: str): The webhook URL to ingest the Azure resources into Port.

Additional environment variables:
  - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is `1000` which is also the maximum size.
  - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is `15` minutes.

- Run the script to sync the Azure resources into Port using `make run`.

## Resource Group Tag Filtering

The integration supports filtering Azure resources based on tags applied to their parent resource groups. This is particularly useful when:

- Individual resources lack the relevant tags
- The resource group has the necessary tags for classification
- You want to avoid tagging every individual resource
- You need a consistent filtering mechanism across all resources in a resource group

### Configuration Examples

**Include only resources from resource groups with specific tags:**
```bash
export RESOURCE_GROUP_TAG_FILTERS='{"Environment": "Production", "Team": "Platform"}'
export EXCLUDE_RESOURCES_BY_RG_TAGS=false
```

**Exclude resources from resource groups with specific tags:**
```bash
export RESOURCE_GROUP_TAG_FILTERS='{"Temporary": "true", "Stage": "development"}'
export EXCLUDE_RESOURCES_BY_RG_TAGS=true
```

**Filter by single tag:**
```bash
export RESOURCE_GROUP_TAG_FILTERS='{"Environment": "Production"}'
export EXCLUDE_RESOURCES_BY_RG_TAGS=false
```

### How it works

1. The integration queries both resources and their parent resource groups
2. It joins the resource data with resource group tag information
3. Filtering is applied at the Azure Resource Graph query level for optimal performance
4. Both resource and resource group tag information is included in the synced data
5. The filtering applies to both incremental and full sync modes

### Tag Matching

- Tag matching is case-insensitive
- All specified tag conditions must match (AND logic)
- If a resource group doesn't have the specified tags, it will be filtered out (when including) or included (when excluding)
- Empty or null tag values are treated as non-matches

## How it works

The application fetches the Azure subscriptions which the Azure app has access to. These subscriptions are then used to query changes in the Azure resources.

The subscriptions are ingested into Port through the webhook. The application then fetches the changes in the Azure resources for each subscription. Resource groups are constructed from the changes and ingested into Port through the webhook. The resources are deleted or ingested into Port depending on the change type received from Azure and the webhook configuration defined by the user.
