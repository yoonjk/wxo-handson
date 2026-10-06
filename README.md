# wxo-handson
Hi Bob! For this project, create a directory ~/project/python/wxo-handson/section-05/lab01

 Use a specific exists folder  for Python virtual environment : ~/project/python/wxo-handson/.venv


 Activate the python virtual environment

Step 2. Build the MCP server with two tools, create unit tests, and documentation

 이 단계에서는 Bob에게 두 가지 수학 도구가 포함된 MCP 서버를 구축하고, 단위 테스트를 통해 도구를 검증하며, 문서를 생성하도록 요청할 것입니다. Bob은 FastMCP를 사용하여 서버를 구축하고, 공유 헬퍼 함수를 통해 도구를 구현하며, 테스트 스크립트를 작성하고, 문제를 자동으로 수정하고, 문서를 작성할 것입니다. Bob은 다음 단계로 넘어가기 전에 모든 사항이 모범 사례를 충족하는지 확인합니다.

 1. Bob에게 자연어로 두 가지 도구를 사용하여 MCP 서버를 생성해 달라고 요청하세요. 각 도구의 용도를 명확하게 명시하세요.

 Create MCP Server using FastMCP with two mathematical tools. The first tool “factorial_value” calculates and returns the exact value of n! (the factorial of a given non-negative integer). The second tool “factorial_digits” returns only the number of decimal digits in n!, which is useful when the factorial is too large to display in full. You can have both tools share a common helper function to compute the factorial and avoid duplication of code.
 