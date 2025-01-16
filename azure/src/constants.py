from typing import Any

INITIAL_QUERY: str = """
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
"""  # noqa E501

SUBSEQUENT_QUERY: str = """
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
"""  # noqa E501

STATE_BLUEPRINT: dict[str, Any] = {
    "identifier": "workflowState",
    "description": (
        "This blueprint represents a Container Registry"
        " Image in our software catalog"
    ),
    "title": "Workflow State",
    "icon": "Git",
    "schema": {
        "properties": {
            "value": {
                "title": "Value",
                "type": "string",
                "enum": ["INITIAL", "SUBSEQUENT"],
                "default": "INITIAL",
            }
        }
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "aggregationProperties": {},
    "relations": {},
}

STATE_DATA: dict[str, Any] = {
    "identifier": "azureSubscriptionWorkflowState",
    "title": "Azure Subscription Workflow State",
    "properties": {"value": "INITIAL"},
}

CLOUD_RESOURCES_BLUEPRINT: dict[str, Any] = {
    "identifier": "cloudResources",
    "description": (
        "This blueprint represents an Azure"
        "Cloud Resource in our software catalog"
    ),
    "title": "Cloud Resources",
    "icon": "Git",
    "schema": {
        "properties": {
            "tags": {"title": "Tags", "type": "object"},
            "type": {"title": "Type", "type": "string"},
            "location": {"title": "Location", "type": "string"},
            "changeType": {"title": "Change Type", "type": "string"},
            "changeTime": {"title": "Change Time", "type": "string"},
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
            "required": True,
        },
        "resourceGroup": {
            "title": "Resource Group",
            "target": "azureResourceGroup",
            "many": False,
            "required": True,
        },
    },
}

RESOURCES_GROUP_BLUEPRINT: dict[str, Any] = {
    "identifier": "azureResourceGroup",
    "description": (
        "This blueprint represents an Azure "
        "Resource Group in our software catalog"
    ),
    "title": "Resource Group",
    "icon": "Azure",
    "schema": {
        "properties": {
            "location": {"title": "Location", "type": "string"},
            "provisioningState": {
                "title": "Provisioning State",
                "type": "string",
            },
            "tags": {"title": "Tags", "type": "object"},
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
            "many": False,
        }
    },
}

SUBSCRIPTION_BLUEPRINT: dict[str, Any] = {
    "identifier": "azureSubscription",
    "title": "Azure Subscription",
    "icon": "Azure",
    "schema": {
        "properties": {"tags": {"title": "Tags", "type": "object"}},
        "required": [],
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "aggregationProperties": {},
    "relations": {},
}
