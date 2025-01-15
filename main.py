import asyncio
import os
from typing import Any, Generator, TypeVar

from azure.mgmt.subscription.models._models_py3 import Subscription
import httpx
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient
from loguru import logger


INITIAL_QUERY = """
resourcechanges 
| extend changeTime=todatetime(properties.changeAttributes.timestamp), targetResourceId=tostring(properties.targetResourceId), changeType=tostring(properties.changeType), correlationId=properties.changeAttributes.correlationId, changedProperties=properties.changes, changeCount=properties.changeAttributes.changesCount 
| project-away tags, name, type 
| where changeTime < ago(15m) and (changeType == 'Delete' or changeType == 'Create' ) 
| extend targetResourceIdCI=tolower(targetResourceId) 
| summarize arg_max(changeTime, *) by targetResourceIdCI 
| join kind=inner ( 
    resources 
    | extend resourceId=tolower(id) 
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup 
) on $left.targetResourceIdCI == $right.resourceId 
| project  subscriptionId, resourceGroup, resourceId, name, tags, type, location, changeType, changeTime
| order by changeTime desc
"""

SUBSEQUENT_QUERY = """
resourcechanges 
| extend changeTime=todatetime(properties.changeAttributes.timestamp), targetResourceId=tostring(properties.targetResourceId), changeType=tostring(properties.changeType), correlationId=properties.changeAttributes.correlationId, changedProperties=properties.changes, changeCount=properties.changeAttributes.changesCount 
| project-away tags, name, type 
| where changeTime > ago(15m)
| extend targetResourceIdCI=tolower(targetResourceId) 
| summarize arg_max(changeTime, *) by targetResourceIdCI 
| join kind=inner ( 
    resources 
    | extend resourceId=tolower(id) 
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup 
) on $left.targetResourceIdCI == $right.resourceId 
| project  subscriptionId, resourceGroup, resourceId, name, tags, type, location, changeType, changeTime
| order by changeTime desc
"""

STATE_BLUEPRINT = {
    "identifier": "workflowState",
    "description": "This blueprint represents a Container Registry Image in our software catalog",
    "title": "Workflow State",
    "icon": "Git",
    "schema": {
        "properties": {
            "value": {
                "title": "Value",
                "type": "string",
                "enum": ["INITIAL", "SUBSEQUENT"],
                "default": "initial"
            }
        }
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "aggregationProperties": {},
    "relations": {}
}

STATE_DATA = {
    "identifier": "azureSubscriptionWorkflowState",
    "title": "Azure Subscription Workflow State",
    "properties": {
        "value": "INITIAL"
    }
}

CLOUD_RESOURCES_BLUEPRINT = {
    "identifier": "cloudResources",
    "description": "This blueprint represents an Azure Cloud Resource in our software catalog",
    "title": "Cloud Resources",
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
        }
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "aggregationProperties": {},
    "relations": {
        "subscription": {
            "title": "Subscription",
            "target": "azureSubscription",
            "many": False,
            "required": True
        },
        "resourceGroup": {
            "title": "Resource Group",
            "target": "azureResourceGroup",
            "many": False,
            "required": True
        },
    }
}

RESOURCES_GROUP_BLUEPRINT = {
    "identifier": "azureResourceGroup",
    "description": "This blueprint represents an Azure Resource Group in our software catalog",
    "title": "Resource Group",
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
        }
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "aggregationProperties": {},
    "relations": {
        "subscription": {
            "target": "azureSubscription",
            "title": "Subscription",
            "required": False,
            "many": False
        }
    }
}

SUBSCRIPTION_BLUEPRINT = {
    "identifier": "azureSubscription",
    "title": "Azure Subscription",
    "icon": "Azure",
    "schema": {
        "properties": {
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

PORT_API_URL = "https://api.getport.io/v1"
PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET")
PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID")


client = SubscriptionClient(DefaultAzureCredential())

T = TypeVar("T")

def turn_sequence_to_chunks(
    sequence: list[Subscription], chunk_size: int
) -> Generator[list[Subscription], None, None]:
    if chunk_size >= len(sequence):
        yield sequence
        return
    start, end = 0, chunk_size

    while start <= len(sequence) and sequence[start:end]:
        yield sequence[start:end]
        start += chunk_size
        end += chunk_size

    return

def get_all_subscriptions() -> os.Iterable[Subscription]:
    return client.subscriptions.list()

async def get_port_token(client: httpx.AsyncClient, client_id: str, client_secret: str) -> str:
    response = await client.post(
        f"{PORT_API_URL}/auth/access_token",
        data={
            "clientId": client_id,
            "clientSecret": client_secret
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]

async def run_query(query: str, subscriptions: list[str]) -> list[dict[str, Any]]: ...

async def upsert_blueprint(client: httpx.AsyncClient, data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Upserting blueprint {data['identifier']}")
    response = await client.post(
        f"{PORT_API_URL}/blueprints",
        json=data
    )
    response.raise_for_status()
    return response.json()

async def upsert_data(client: httpx.AsyncClient, blueprint: str, data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Upserting data for blueprint {blueprint}")
    response = await client.post(
        (
            f"{PORT_API_URL}/blueprints/{blueprint}/entities"
            "?upsert=true&merge=true&create_missing_related_entities=true"
        ),
        json=data
    )
    response.raise_for_status()
    return response.json()

async def retrieve_data(client: httpx.AsyncClient, blueprint: str, id: str) -> dict[str, Any] | None:
    response = await client.get(
        f"{PORT_API_URL}/blueprints/{blueprint}/entities/{id}"
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

async def delete_data(client: httpx.AsyncClient, blueprint: str, data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Deleting data for blueprint {blueprint}")
    response = await client.post(
        (
            f"{PORT_API_URL}/blueprints/{blueprint}/entities"
            "?delete_dependents=false"
        ),
        json=data
    )
    response.raise_for_status()
    return response.json()


def construct_resources_entity(data: dict[str, Any]) -> dict[str, Any]: ...

def construct_subscription_entity(data: Subscription) -> dict[str, Any]:
    return {
        "identifier": data.subscription_id,
        "title": data.display_name,
        "properties": {
            "tags": data.additional_properties
        }
    }

def construct_resource_group_entity(name: str, subscription_id: str) -> dict[str, Any]:
    return {
        "identifier": name,
        "title": name,
        "relations": {
            "subscription": subscription_id
        }
    }


async def main():
    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        token = await get_port_token(
            client,
            PORT_CLIENT_ID,
            PORT_CLIENT_SECRET
        )
        client.headers.update({"Authorization": f"Bearer {token}"})

        tasks = [
            upsert_blueprint(client, STATE_BLUEPRINT),
            upsert_blueprint(client, CLOUD_RESOURCES_BLUEPRINT),
            upsert_blueprint(client, RESOURCES_GROUP_BLUEPRINT),
            upsert_blueprint(client, SUBSCRIPTION_BLUEPRINT),
        ]
        await asyncio.gather(*tasks)

        state = await retrieve_data(
            client,
            STATE_BLUEPRINT["identifier"],
            STATE_DATA["identifier"]
        )
        if not state:
            state = await upsert_data(
                client,
                STATE_BLUEPRINT["identifier"],
                STATE_DATA
            )
        
        subscriptions_batches = turn_sequence_to_chunks(
            get_all_subscriptions(),
            1000
        )

        query = (
            INITIAL_QUERY
            if state["properties"]["value"] == "INITIAL"
            else SUBSEQUENT_QUERY
        )
        
        for subscriptions in subscriptions_batches:
            data = await run_query(query, subscriptions)
            delete_tasks = []
            upsert_tasks = []
            for item in data:
                entity = construct_resources_entity(item)
                if item["action"] == "delete":
                    delete_tasks.append(
                        delete_data(
                            client,
                            CLOUD_RESOURCES_BLUEPRINT["identifier"],
                            entity
                        )
                    )
                else:
                    upsert_tasks.append(
                        upsert_data(
                            client,
                            CLOUD_RESOURCES_BLUEPRINT["identifier"],
                            entity
                        )
                    )
            
            await asyncio.gather(*delete_tasks)
            await asyncio.gather(*upsert_tasks)

        await upsert_data(
            client,
            STATE_BLUEPRINT["identifier"],
            {**state, "properties": {"value": "SUBSEQUENT"}}
        )
