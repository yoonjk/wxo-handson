# wxo-handson
Hi Bob! For this project, create a directory ~/project/python/wxo-handson/section-05/lab01

 Use a specific exists folder  for Python virtual environment : ~/project/python/wxo-handson/.venv


 Activate the python virtual environment

Step 2. Build the MCP server with two tools, create unit tests, and documentation

 이 단계에서는 Bob에게 두 가지 수학 도구가 포함된 MCP 서버를 구축하고, 단위 테스트를 통해 도구를 검증하며, 문서를 생성하도록 요청할 것입니다. Bob은 FastMCP를 사용하여 서버를 구축하고, 공유 헬퍼 함수를 통해 도구를 구현하며, 테스트 스크립트를 작성하고, 문제를 자동으로 수정하고, 문서를 작성할 것입니다. Bob은 다음 단계로 넘어가기 전에 모든 사항이 모범 사례를 충족하는지 확인합니다.

 1. Bob에게 자연어로 두 가지 도구를 사용하여 MCP 서버를 생성해 달라고 요청하세요. 각 도구의 용도를 명확하게 명시하세요.

FastMCP를 사용하여 두 가지 수학 도구를 갖춘 MCP 서버를 생성합니다. 첫 번째 도구인 "factorial_value"는 주어진 음수가 아닌 정수의 팩토리얼(n!) 값을 정확하게 계산하여 반환합니다. 두 번째 도구인 "factorial_digits"는 n!의 소수점 이하 자릿수만 반환하는데, 이는 팩토리얼 값이 너무 커서 전체를 표시할 수 없을 때 유용합니다. 두 도구가 팩토리얼을 계산하는 공통 헬퍼 함수를 ​​공유하도록 하여 코드 중복을 방지할 수 있습니다.


Bob은 구현을 검증합니다. Bob은 MCP 서버와 도구를 확인하기 위한 테스트 스크립트를 작성합니다.

Bob은 ~/project/python/wxo-handson/section-05/lab01 에 대한 문서를  한국어로 작성하고, 기술용어는 영어를 유지합니다.

Step 3. Start the MCP server and validate it with an MCP client

Bob starts the MCP client to connect with the MCP server.

Bob은 MCP 클라이언트에서 MCP 서버로 테스트 케이스를 실행합니다. Bob은 두 도구가 MCP 프로토콜을 통해 올바르게 작동하고 오류 처리도 제대로 되는지 확인합니다.

Step 4. Add the MCP tools to watsonx Orchestrate
이 단계에서는 Bob에게 두 가지 MCP 도구를 watsonx Orchestrate에 추가해 달라고 요청합니다. Bob은 watsonx Orchestrate 명령줄 인터페이스를 사용하여 도구를 가져오고, 오류나 누락된 종속성을 해결한 다음, 도구가 watsonx Orchestrate에 통합되어 사용 준비가 되었는지 확인합니다.

Bob에게 watsonx Orchestrate 명령줄 도구를 사용하여 MCP 도구를 watsonx Orchestrate로 가져오도록 지시하십시오. Bob의 계획을 검토한 후 ‘승인’을 클릭하십시오.


WatsonX Orchestrate에 이러한 MCP 도구를 추가해야 하는 경우 명령줄에서 "orchestrate toolkits"를 사용하여 추가할 수 있습니다.

Bob은 MCP 도구(–import)를 가져오기 위해 필요한 정확한 명령어를 파악하기 위해 watsonx Orchestrate 명령줄 도움말을 실행합니다.
```bash
orchestrate toolkits add \
  --kind mcp \
  --name factorial_mcp \
  --description "Factorial MCP Server: compute n! value and digit count" \
  --package-root "$(pwd)" \
  --command '["python3", "server.py"]'  \
  --tools "factorial_value,factorial_digits"
```

Bob confirms that the MCP server and the two MCP tools are fully integrated with watsonx Orchestrate and ready to use.