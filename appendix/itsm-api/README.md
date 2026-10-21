
# itsm api server
```bash
orchestrate connections add -a itsm_api
orchestrate connections configure -a itsm_api --env draft --kind bearer --type team --url https://<ITSM_API_도메인>
orchestrate connections configure -a itsm_api --env live  --kind bearer --type team --url https://<ITSM_API_도메인>
orchestrate connections set-credentials -a itsm_api --env draft --token <ITSM_API_TOKEN>
orchestrate connections set-credentials -a itsm_api --env live  --token <ITSM_API_TOKEN>
orchestrate tools import -k openapi -f itsm_sr_openapi.json --app-id itsm_api
`