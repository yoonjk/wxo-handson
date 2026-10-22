"""등록용 OpenAPI 3.0.3 YAML 생성. 실행 전에 PUBLIC_BASE_URL을 지정하세요."""
from copy import deepcopy
from pathlib import Path
import yaml
from app import PUBLIC_BASE_URL, app


def build_spec():
    # 등록용 계약은 IBM 문서와 동일한 inline object schema로 단순화합니다.
    paths = {}
    for path, item in app.openapi()["paths"].items():
        operation = deepcopy(item["post"])
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": {
                "type": "object", "required": ["payload", "context"],
                "properties": {"payload": {"type": "object", "additionalProperties": True},
                               "context": {"type": "object", "additionalProperties": True}},
            }}},
        }
        operation["responses"] = {
            "200": {"description": "Plugin result", "content": {"application/json": {
                "schema": {"type": "object", "required": ["continue_processing"],
                           "properties": {"continue_processing": {"type": "boolean"},
                                          "modified_payload": {"type": "object", "additionalProperties": True}}}
            }}},
            "422": {"description": "Invalid request body"},
        }
        paths[path] = {"post": operation}
    return {"openapi": "3.0.3", "info": {"title": app.title, "version": app.version},
            "servers": [{"url": PUBLIC_BASE_URL}], "paths": paths}


if __name__ == "__main__":
    output = Path(__file__).with_name("openapi-plugin.yaml")
    output.write_text(yaml.safe_dump(build_spec(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(output)
