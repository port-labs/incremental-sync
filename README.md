# incremental-sync

This repository contains the code for incremental and periodic sync of Azure resources, subscriptions and resources groups (Azure Resources are prioritized in detail) into Port.

The code is written in Python and uses the Azure SDK for Python to interact with Azure resources. It is designed to be run in a GitHub workflow in periodic intervals to keep the Port data up-to-date.


## Installation
Both ways of running this application requires you to set up an Azure application. You can follow the steps in the [Azure documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app) to create an Azure application. You do not need a Redirect URI for this application. In addition, ensure that the Azure application has the required permissions to access the Azure resources.

Keep the following values handy:
- `AZURE_CLIENT_ID`: The client ID of the Azure service principal.
- `AZURE_CLIENT_SECRET`: The client secret of the Azure service principal.
- `AZURE_TENANT_ID`: The tenant ID of the Azure service principal.


Next, get your Port client ID and client secret by clicking on the three dots on the top right corner of the Port UI and selecting "Credentials". You will find the client ID and client secret there.

### GitHub Actions
- Clone this repository.

- Set the following secrets in your GitHub repository:
    - `AZURE_CLIENT_ID` (type: str): The client ID of the Azure service principal.
    - `AZURE_CLIENT_SECRET` (type: str): The client secret of the Azure service principal.
    - `AZURE_TENANT_ID` (type: str): The tenant ID of the Azure service principal.
    - `PORT_CLIENT_ID` (type: str): The client ID of the Port service principal.
    - `PORT_CLIENT_SECRET` (type: str): The client secret of the Port service principal.
    - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is 1000.
    - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is 15 minutes.

- The GitHub workflow is defined in `.github/workflows/sync.yml`. You can modify the schedule of the workflow by changing the `cron` value.

- Push the changes to your GitHub repository.

- The GitHub workflow will run in the specified intervals and sync the Azure resources into Port.

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
    - `SUBSCRIPTION_BATCH_SIZE` (type: int): The number of subscriptions to sync in each batch. Default is 1000.
    - `CHANGE_WINDOW_MINUTES` (type: int): The number of minutes to consider for changes in Azure resources. Default is 15 minutes.

- Run the script to sync the Azure resources into Port using `make run`.


## How it works
The application starts by upserting the needed blueprints into Port. These blueprints are:
- `azureWorkflowState`: The state of the workflow.
- `azureSubscription`: The Azure subscription.
- `azureResourceGroup`: The Azure resource group.
- `azureCloudResources`: The Azure resource.

It then checks for the existence of the state of the workflow in Port. If the state does not exist, it creates the state with the initial values. The state tells whether this is the first run of the workflow or not. This is important to determine whether to sync all the resources or only the changes.

The application then fetches the Azure subscriptions which the Azure app has access to. These subscriptions are then used to query changes in the Azure resources.

The subscriptions are ingested into Port as `azureSubscription` blueprints. The application then fetches the changes in the Azure resources for each subscription. Resource groups are constructed from the changes and ingested into Port as `azureResourceGroup` blueprints. The resources are deleted or ingested into Port as `azureCloudResources` blueprints depending on the change type received from Azure.

The application then updates the state of the workflow in Port with the latest values.
