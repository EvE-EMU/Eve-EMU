#!/bin/sh
# CCP removed esi-search.search_structures.v1 from SSO (invalid_scope). Wanderer CE 1.100.x
# still requests it in runtime.exs — strip before boot so EVE login works.
for f in /app/releases/1.0.0/runtime.exs /app/releases/1.0.0/sys.config; do
  if [ -f "$f" ]; then
    sed -i 's/ esi-search\.search_structures\.v1//g' "$f"
  fi
done
