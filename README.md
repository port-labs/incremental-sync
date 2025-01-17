# incremental-sync

This repository contains the code for incremental and periodic sync of Azure resources, subscriptions and resources groups (Azure Resources are prioritized in detail) into Port.

The code is written in Python and uses the Azure SDK for Python to interact with Azure resources. It is designed to be run in a GitHub workflow in periodic intervals to keep the Port data up-to-date.


## Installation

### GitHub Actions
- Clone this repository.

- Set the following secrets in your GitHub repository:
    - `AZURE_CLIENT_ID`: The client ID of the Azure service principal.
    - `AZURE_CLIENT_SECRET`: The client secret of the Azure service principal.
    - `AZURE_TENANT_ID`: The tenant ID of the Azure service principal.
    - `PORT_CLIENT_ID`: The client ID of the Port service principal.
    - `PORT_CLIENT_SECRET`: The client secret of the Port service principal.

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
    - `AZURE_CLIENT_ID`: The client ID of the Azure service principal.
    - `AZURE_CLIENT_SECRET`: The client secret of the Azure service principal.
    - `AZURE_TENANT_ID`: The tenant ID of the Azure service principal.
    - `PORT_CLIENT_ID`: The client ID of the Port service principal.
    - `PORT_CLIENT_SECRET`: The client secret of the Port service principal.

- Run the script to sync the Azure resources into Port using `make run`.