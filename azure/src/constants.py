from settings import app_settings

QUERY: str = f"""
resourcechanges 
| extend changeTime=todatetime(properties.changeAttributes.timestamp), targetResourceId=tostring(properties.targetResourceId), changeType=tostring(properties.changeType), correlationId=properties.changeAttributes.correlationId, changedProperties=properties.changes, changeCount=properties.changeAttributes.changesCount 
| project-away tags, name, type 
| where changeTime > ago({app_settings.CHANGE_WINDOW_MINUTES}m)
| extend targetResourceIdCI=tolower(targetResourceId) 
| summarize arg_max(changeTime, *) by targetResourceIdCI 
| join kind=inner ( 
    resources 
    | extend resourceId=tolower(id) 
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup 
) on $left.targetResourceIdCI == $right.resourceId 
| project  subscriptionId, resourceGroup, resourceId, name, tags, type, location, changeType, changeTime, changedProperties
| order by changeTime desc
"""  # noqa E501
