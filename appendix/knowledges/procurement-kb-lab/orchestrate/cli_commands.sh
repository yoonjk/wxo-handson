#!/usr/bin/env bash
# Reference ADK CLI commands for this lab. The lab guide uses the Orchestrate UI;
# run these only if you prefer the CLI. Review each command before running it.
#
# Known limits found while building this lab:
#   - A connection used by a knowledge base cannot change its auth type
#     ("Switching auth type not allowed for the Knowledge component") or be removed
#     while a knowledge base uses it. Create a new connection instead.
#   - The UI warns that a connection cannot be renamed or deleted once added.
#   - API Key knowledge connections fail at search time with KeyError: 'apikey'. Use Basic.
#   - Whether "connections add" needs --component knowledge / --category for a custom
#     service was not confirmed; check "orchestrate connections add --help".
set -euo pipefail

APP_ID=custom_service_basic
SERVER_URL=http://nexweb.ddnsgeek.com:3464     # your public URL (nginx listen port)
USERNAME=orchestrate                            # = AUTH_USERNAME in .env
PASSWORD='change-me-to-a-random-string'         # = AUTH_PASSWORD in .env

# 1) Connection (draft environment)
orchestrate connections add -a "$APP_ID"
orchestrate connections configure -a "$APP_ID" --env draft -t team -k basic --server-url "$SERVER_URL"
orchestrate connections set-credentials -a "$APP_ID" --env draft -u "$USERNAME" -p "$PASSWORD"

# 2) Knowledge base using that connection
orchestrate knowledge-bases import -f orchestrate/purchase_knowledge_basic.yaml -a "$APP_ID"

# 3) Live environment (when you deploy the agent)
# orchestrate connections configure -a "$APP_ID" --env live -t team -k basic --server-url "$SERVER_URL"
# orchestrate connections set-credentials -a "$APP_ID" --env live -u "$USERNAME" -p "$PASSWORD"

# Rotate the password later (update .env and restart the server too):
# orchestrate connections set-credentials -a "$APP_ID" --env draft -u "$USERNAME" -p '<new password>'
