
# custom-service
custom service를 위한 connection 생성  
credentials type이 None 또는 Basic만 지원, api-key는 오류

```bash
orchestrate connections add -a custom_service_basic

orchestrate connections configure --app-id custom_service_basic --environment draft -t team -k basic -u http://...:port

connections set-credentials --env draft -u username -p blabla -a custom_service_basic
```

# knowledge-bases
```bash
orchestrate knowledge-bases import -f ibm_knowledge_base.yaml
```