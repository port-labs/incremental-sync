#!/usr/bin/env bash

# ------------------------------------------------------------------------------
# 1. Define the Kusto query you want to run (one line or escaped carefully)
# ------------------------------------------------------------------------------
QUERY="resourcechanges \
| extend changeTime=todatetime(properties.changeAttributes.timestamp), targetResourceId=tostring(properties.targetResourceId), changeType=tostring(properties.changeType), correlationId=properties.changeAttributes.correlationId, changedProperties=properties.changes, changeCount=properties.changeAttributes.changesCount \
| project-away tags, name, type \
| where changeTime > ago(15min) \
| extend targetResourceIdCI=tolower(targetResourceId) \
| summarize arg_max(changeTime, *) by targetResourceIdCI \
| join kind=inner ( \
    resources \
    | extend resourceIdCI=tolower(id) \
    | project resourceIdCI, type, name, location, tags, subscriptionId, resourceGroup \
) on \$left.targetResourceIdCI == \$right.resourceIdCI \
| project  subscriptionId, resourceGroup, targetResourceId, name, tags, type, location, changeType, changeTime \
| order by changeTime desc"


# ------------------------------------------------------------------------------
# 2. Fetch all subscription IDs (without using mapfile)
# ------------------------------------------------------------------------------
echo "Fetching all subscriptions..."
SUBSCRIPTION_IDS=()
while IFS= read -r line; do
    # If the line begins with /subscriptions/, remove that prefix
    if [[ "$line" == /subscriptions/* ]]; then
        line="${line#/subscriptions/}"
    fi
    SUBSCRIPTION_IDS+=( "$line" )
done < <(az account list --query "[].id" -o tsv)

# If no subscriptions were found, exit
if [ ${#SUBSCRIPTION_IDS[@]} -eq 0 ]; then
    echo "No subscriptions found. Exiting."
    exit 1
fi

echo "Total subscriptions found: ${#SUBSCRIPTION_IDS[@]}"

# ------------------------------------------------------------------------------
# 3. Prepare batching variables
# ------------------------------------------------------------------------------
CHUNK_SIZE=1000
COUNTER=0

# Optionally create a folder for results
mkdir -p results

# ------------------------------------------------------------------------------
# 4. Loop over subscriptions in chunks of up to 1000
# ------------------------------------------------------------------------------
for (( i=0; i<${#SUBSCRIPTION_IDS[@]}; i+=CHUNK_SIZE )); do
    # Slice the array for this batch
    chunk=("${SUBSCRIPTION_IDS[@]:i:CHUNK_SIZE}")

    # Build a space-separated list of subscription IDs
    chunk_arg="${chunk[@]}"

    echo "Querying chunk starting at index $i..."

    # Run the Resource Graph query on the current chunk
    az graph query \
        -q "$QUERY" \
        --subscriptions $chunk_arg \
        --output json \
        > "results/results_$i.json"

    COUNTER=$((COUNTER+1))
    echo "Chunk $COUNTER done. Wrote results to results/results_$i.json"
done

echo "All chunks processed."
