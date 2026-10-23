

# Create key connection for mcp server
## my_mcpserver
```bash
orchestrate connections add -a my_mcpserver
```


```bash
orchestrate connections configure \
  -a my_mcpserver \
  --env draft \
  --type team \
  --kind bearer

orchestrate connections configure \
  -a my_mcpserver \
  --env live \
  --type team \
  --kind bearer  
```  

```bash
orchestrate connections set-credentials \
  -a my_mcpserver \
  --env draft \
  --token "${MCP_TOKEN}"
```

## itsm-api
```bash
orchestrate connections add -a itsm_api
```


```bash
orchestrate connections configure \
  -a itsm_api \
  --env draft \
  --type team \
  --kind bearer

orchestrate connections configure \
  -a itsm_api \
  --env live \
  --type team \
  --kind bearer  
```  

- draft
```bash
orchestrate connections set-credentials \
  -a itsm_api \
  --env draft \
  --token "${MCP_ITSM_TOKEN}"
```
- live
```bash
orchestrate connections set-credentials \
  -a itsm_api \
  --env live \
  --token "${MCP_ITSM_TOKEN}"
```

# UI 
All tools > Create tool
![alt text](create_tool.png)

Add a tool > MCP server
![alt text](add-a-tool.png)

Add tools and manage MCP servers > Add MCP server
![alt text](add-mcpserver.png)

Add an MCP server > Remote MCP server 
![alt text](remote-mcp-server.png)

![alt text](imset-remote-mcp-server.png)

![alt text](create-mcpgateway-token.png)


![alt text](token-created-successfully.png)

![alt text](mcp-server-is-ready.png)


# MCPGateway toolkit
## Add tool
- Add all tool
```bash
orchestrate toolkits add \
  --kind mcp \
  --name mcpgateway \
  --description "원격 MCP 서버" \
  --url "http://nexweb.ddnsgeek.com:14444/servers/f50b2bab745f4e19a6396f578a390f58/mcp" \
  --transport "streamable_http" \
  --tools "*" \
  --app-id "my_mcpserver"
  ```

- Add selected tool
```bash
  orchestrate toolkits add \
  --kind mcp \
  --name itsm_mcp \
  --description "ITSM MCP 서버" \
  --url "http://nexweb.ddnsgeek.com:14444/servers/cc293cb1dfdd4f3c97f1f140ccad81c7/mcp" \
  --transport "streamable_http" \
  --tools "*" \
  --app-id "itsm_api"
  ```

## Remove tools
```bash
orchestrate toolkits remove -n itsm_mcp
```