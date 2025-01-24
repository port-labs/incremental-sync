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

### Port Setup

#### Port Credentials

Next, get your Port client ID and client secret by clicking on the three dots on the top right corner of the Port UI and selecting "Credentials". You will find the client ID and client secret there.

#### Configuring blueprints for Azure resources ingestion

Blueprints representing Azure resources should be created in Port before syncing the Azure resources. The blueprints configuration are for illustrative purposes only. You can create your own blueprints configuration based on your requirements.

Below are the blueprints that should be created in Port:

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
      "additionalProperties": {
        "title": "Tags",
        "type": "object"
      },
      "authorizationSource": {
        "title": "Authorization Source",
        "type": "string"
      },
      "state": {
        "title": "State",
        "type": "string"
      },
      "subscriptionPolicies": {
        "title": "Subscription Policies",
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
      "provisioningState": {
        "title": "Provisioning State",
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
      },
      "changeType": {
        "title": "Change Type",
        "type": "string"
      },
      "changeTime": {
        "title": "Change Time",
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
      "required": true,
      "many": false
    },
    "subscription": {
      "title": "Subscription",
      "target": "azureSubscription",
      "required": true,
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

**Note:** The payload from the application contains a `__typename` field which is used to determine the blueprint to ingest the data into. The `__typename` field is not part of the Azure resource payload and is only present as a discriminator for the webhook.

```json
[
  {
    "blueprint": "azureCloudResources",
    "operation": "create",
    "filter": ".__typename == 'Resources'",
    "entity": {
      "identifier": ".body.resourceId",
      "title": ".body.title",
      "properties": {
        "tags": ".body.tags",
        "type": ".body.type",
        "location": ".body.location",
        "changeType": ".body.changeType",
        "changeTime": ".body.changeTime"
      },
      "relations": {
        "subscription": ".body.subscriptionId",
        "resourceGroup": ".body.resourceGroup"
      }
    }
  },
  {
    "blueprint": "azureCloudResources",
    "operation": "delete",
    "filter": ".__typename == 'Resources'",
    "entity": {
      "identifier": ".body.resourceId"
    }
  },
  {
    "blueprint": "azureResourceGroup",
    "operation": "create",
    "filter": ".__typename == 'ResourceGroup'",
    "entity": {
      "identifier": ".body.name",
      "title": ".body.name",
      "properties": {
        "tags": ".body.tags",
        "provisioningState": ".body.provisioningState",
        "location": ".body.location"
      },
      "relations": {
        "subscription": ".body.subscriptionId"
      }
    }
  },
  {
    "blueprint": "azureResourceGroup",
    "operation": "delete",
    "filter": ".__typename == 'ResourceGroup'",
    "entity": {
      "identifier": ".body.name"
    }
  },
  {
    "blueprint": "azureSubscription",
    "operation": "create",
    "filter": ".__typename == 'Subscription'",
    "entity": {
      "identifier": ".body.id",
      "title": ".body.displayName",
      "properties": {
        "subscriptionId": ".body.subscriptionId",
        "additionalProperties": ".body.additionalProperties",
        "authorizationSource": ".body.authorizationSource",
        "state": ".body.state",
        "subscriptionPolicies": ".body.subscriptionPolicies"
      }
    }
  },
  {
    "blueprint": "azureSubscription",
    "operation": "delete",
    "filter": ".__typename == 'Subscription'",
    "entity": {
      "identifier": ".body.id"
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
  - `PORT_CLIENT_ID` (type: str): The client ID of the Port service principal.
  - `PORT_CLIENT_SECRET` (type: str): The client secret of the Port service principal.
  - `PORT_WEBHOOK_INGEST_URL` (type: str): The webhook URL to ingest the Azure resources into Port.
  - `PORT_API_URL` (type: str): The URL of the Port API. Default is `"https://api.getport.io/v1"`.
  - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is `1000` which is also the maximum size.
  - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is `15` minutes.

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
          python -m pip install --upgrade pip
          pip install poetry
          make install

      - name: Run incremental sync
        run: make run
        env:
          AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          PORT_CLIENT_ID: ${{ secrets.PORT_CLIENT_ID }}
          PORT_CLIENT_SECRET: ${{ secrets.PORT_CLIENT_SECRET }}
          PORT_WEBHOOK_INGEST_URL: ${{ secrets.PORT_WEBHOOK_INGEST_URL }}
          CHANGE_WINDOW_MINUTES: 15
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
  - `PORT_CLIENT_ID` (type: str): The client ID of the Port service principal.
  - `PORT_CLIENT_SECRET` (type: str): The client secret of the Port service principal.
  - `PORT_WEBHOOK_INGEST_URL` (type: str): The webhook URL to ingest the Azure resources into Port.
  - `PORT_API_URL` (type: str): The URL of the Port API. Default is `"https://api.getport.io/v1"`.
  - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is `1000` which is also the maximum size.
  - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is `15` minutes.

- Run the script to sync the Azure resources into Port using `make run`.

## How it works

The application fetches the Azure subscriptions which the Azure app has access to. These subscriptions are then used to query changes in the Azure resources.

The subscriptions are ingested into Port through the webhook. The application then fetches the changes in the Azure resources for each subscription. Resource groups are constructed from the changes and ingested into Port through the webhook. The resources are deleted or ingested into Port depending on the change type received from Azure and the webhook configuration defined by the user.
