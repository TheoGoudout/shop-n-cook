#! /usr/bin/env bash

set -e
set -x

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
cp openapi.json frontend/openapi.json
cp openapi.json extension/openapi.json
rm openapi.json
bun run --filter frontend generate-client
bun run --filter extension generate-client
bun run lint
