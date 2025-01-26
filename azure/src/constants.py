from settings import app_settings

QUERY: str = f"""
resourcechanges 
| extend changeTime=todatetime(properties.changeAttributes.timestamp), targetResourceId=tostring(properties.targetResourceId), changeType=tostring(properties.changeType), correlationId=properties.changeAttributes.correlationId, changedProperties=properties.changes, changeCount=properties.changeAttributes.changesCount 
| project-away tags, name, type 
| where changeTime > ago({app_settings.CHANGE_WINDOW_MINUTES}m)
| extend resourceId=tolower(targetResourceId) 
| summarize arg_max(changeTime, *) by resourceId 
| join kind=leftouter ( 
    resources 
    | extend sourceResourceId=tolower(id) 
    | project sourceResourceId, type, name, location, tags, subscriptionId, resourceGroup 
) on $left.resourceId == $right.sourceResourceId 
| project  subscriptionId, resourceGroup, resourceId , sourceResourceId, name, tags, type, location, changeType, changeTime, changedProperties
| order by changeTime desc
"""  # noqa E501
