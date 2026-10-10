## MCP 설치 Troubleshooting

### 1. `watsonx-orchestrate-adk-docs` — Disconnected

**증상**

Bob MCP 패널에서 `watsonx-orchestrate-adk-docs` 서버가 Disconnected 상태이며, 아래 오류가 발생합니다.

```
ImportError: cannot import name 'request_ctx' from 'mcp.server.lowlevel.server'
```

**원인**

`mcp-proxy`가 `mcp.server.lowlevel.server.request_ctx`를 import하는데, 이 심볼은 `mcp` 라이브러리 최신 버전에서 제거되어 버전 충돌이 발생합니다.

**해결**

`.bob/mcp.json`에서 `uvx` 실행 시 `--with "mcp==1.9.4"` 옵션을 추가해 호환 버전을 강제 지정합니다.

```json
"watsonx-orchestrate-adk-docs": {
  "command": "uvx",
  "args": ["--with", "mcp==1.9.4", "mcp-proxy", "--transport", "streamablehttp",
           "https://developer.watson-orchestrate.ibm.com/mcp"]
}
```

---

### 2. `watsonx-orchestrate-adk` — Disconnected

**증상**

Bob MCP 패널에서 `watsonx-orchestrate-adk` 서버가 Disconnected 상태이며, 아래 오류가 발생합니다.

```
ModuleNotFoundError: No module named 'ibm_watsonx_orchestrate_mcp_server'
```

**원인**

두 가지 문제가 복합적으로 발생합니다.

1. `ibm-watsonx-orchestrate-mcp-server` 패키지가 설치되지 않음 (`ibm-watsonx-orchestrate`와 별도 패키지)
2. `.bob/mcp.json`의 `command`가 `"python"`으로 설정되어 있으나, macOS에는 `python` 명령이 없고 `python3`만 존재

**해결**

패키지를 설치합니다.

```bash
pip3 install ibm-watsonx-orchestrate-mcp-server
```

`.bob/mcp.json`에서 `command`를 `"python3"`으로 수정합니다.

```json
"watsonx-orchestrate-adk": {
  "command": "python3",
  "args": ["-m", "ibm_watsonx_orchestrate_mcp_server.server"],
  "env": { "WXO_MCP_WORKING_DIRECTORY": "/Users/nexweb/project/python/wxo-handson/section-05/lab03" },
  "timeout": 300000
}
```

수정 후 Bob을 재시작하거나 MCP 패널에서 새로고침 버튼을 클릭합니다.