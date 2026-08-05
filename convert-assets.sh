#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
printf "Asset name: "
read -r ASSET_NAME
python3 tools/convert_assets.py --name "$ASSET_NAME"
