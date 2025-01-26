#!/usr/bin/env bash

LOCATION="eastus"
RG_NAME="resource-group-with-vpcs"
PREFIX="test-vpc"
NUM_NSGS=1000

# Create a resource group
az group create --name "$RG_NAME" --location "$LOCATION"

# Create multiple NSGs
for i in $(seq 1 $NUM_NSGS)
do
  NSG_NAME="${PREFIX}${i}"
  echo "Creating Network Security Group: $NSG_NAME"
  az network nsg create \
    --resource-group "$RG_NAME" \
    --name "$NSG_NAME" \
    --location "$LOCATION"
done
