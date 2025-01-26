#!/usr/bin/env bash

# Change the location as needed
LOCATION="eastus"
PREFIX="resource-group"

# Loop to create 1,000 resource groups
for i in {1..50}
do
  RG_NAME="${PREFIX}${i}"
  echo "Creating Resource Group: $RG_NAME in $LOCATION"
  az group create --name "$RG_NAME" --location "$LOCATION"
done