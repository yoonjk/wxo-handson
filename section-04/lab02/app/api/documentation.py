"""Reusable OpenAPI response examples for the purchase API."""

from copy import deepcopy

from app.schemas.purchase import CREATE_EXAMPLE, RESPONSE_EXAMPLE

REQUEST_ID_DESCRIPTION = (
    "POST /api/purchase-requests 응답에서 받은 정수 id입니다. DB가 생성한 구매 요청 번호이며 "
    "요청자 ID나 watsonx Orchestrate 실행 ID가 아닙니다. 예를 들어 생성 응답이 id=1이면 "
    "경로에 1을 사용합니다. 정수가 아니면 422, 해당 요청이 없으면 404를 반환합니다."
)

VALIDATION_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {
        "detail": {
            "type": "array",
            "description": "각 항목은 검증에 실패한 위치와 이유를 나타냅니다.",
            "items": {
                "type": "object",
                "required": ["loc", "msg", "type"],
                "properties": {
                    "loc": {
                        "type": "array",
                        "description": "오류 위치. 예: ['body', 'total_amount'] 또는 ['path', 'request_id'].",
                        "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                    },
                    "msg": {"type": "string", "description": "사람이 읽을 수 있는 검증 오류 설명."},
                    "type": {"type": "string", "description": "Pydantic 검증 오류 유형 코드."},
                },
            },
        }
    },
}


def validation_response(location: list, message: str, error_type: str) -> dict:
    """FastAPI/Pydantic 422 응답의 실제 구조와 작업별 예시."""
    return {
        "description": (
            "경로 파라미터 또는 요청 본문이 검증 규칙을 만족하지 않습니다. "
            "detail[].loc에서 오류 필드를 확인하고 msg에 따라 값을 수정한 뒤 다시 호출합니다."
        ),
        "content": {
            "application/json": {
                "schema": VALIDATION_SCHEMA,
                "examples": {
                    "invalidInput": {
                        "summary": "이 작업의 입력 검증 오류 예시",
                        "value": {
                            "detail": [
                                {"loc": location, "msg": message, "type": error_type}
                            ]
                        },
                    }
                },
            }
        },
    }


def detail_response(description: str, detail: str) -> dict:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["detail"],
                    "properties": {
                        "detail": {
                            "type": "string",
                            "description": "요청을 완료하지 못한 구체적인 이유.",
                        }
                    },
                },
                "example": {"detail": detail},
            }
        },
    }


NOT_FOUND = detail_response(
    "구매 요청이 없습니다. 생성 응답의 id와 현재 연결된 DB를 확인합니다. 조회와 상태 변경은 요청을 자동 생성하지 않습니다.",
    "구매 요청 999을(를) 찾을 수 없습니다.",
)
CONFLICT = detail_response(
    "이미 승인 또는 반려로 확정된 요청을 반대 결과로 변경할 수 없습니다. GET으로 현재 상태를 확인합니다.",
    "APPROVED 상태의 요청은 REJECTED(으)로 변경할 수 없습니다.",
)
SERVER_ERROR = {
    "description": (
        "처리되지 않은 서버 오류입니다. 예를 들어 DB 접속 또는 SQL 실행 실패가 발생할 수 있습니다. "
        "현재 애플리케이션은 DB 오류를 별도 JSON 응답으로 변환하지 않습니다. "
        "생성 요청의 응답이 불명확할 때는 재호출 전에 GET 또는 DB에서 중복 생성 여부를 확인합니다."
    ),
    "content": {
        "text/plain": {
            "schema": {"type": "string", "description": "서버 오류 텍스트."},
            "example": "Internal Server Error",
        }
    },
}

CREATE_EXAMPLES = {
    "itEquipment": {
        "summary": "IT 장비 구매 요청",
        "description": "노트북 구매 요청을 PENDING 상태로 저장합니다. purchase_type은 활성 상품 카탈로그의 SKU여야 합니다.",
        "value": CREATE_EXAMPLE,
    },
    "officeSupplies": {
        "summary": "사유 없이 구매 요청 생성",
        "description": "reason은 선택 필드이므로 생략할 수 있습니다.",
        "value": {
            "purchase_type": "OFFICE_SUPPLIES",
            "requester": "kim.minji",
            "total_amount": "85000.00",
        },
    },
}
STATUS_EXAMPLES = {
    "approve": {
        "summary": "구매 요청 승인",
        "description": "PENDING 요청을 APPROVED로 변경합니다.",
        "value": {"status": "APPROVED", "comment": "예산 확인 완료", "approver_role": "IT_MANAGER"},
    },
    "reject": {
        "summary": "구매 요청 반려",
        "description": "PENDING 요청을 REJECTED로 변경합니다.",
        "value": {"status": "REJECTED", "comment": "구매 사유 보완 필요", "approver_role": "IT_MANAGER"},
    },
    "noComment": {
        "summary": "의견 없이 승인",
        "description": "comment는 선택 필드입니다.",
        "value": {"status": "APPROVED", "approver_role": "IT_MANAGER"},
    },
}


def result_examples(*states: str) -> dict:
    examples = {}
    for state in states:
        value = deepcopy(RESPONSE_EXAMPLE)
        value["status"] = state
        if state != "PENDING":
            value.update(
                approver_role="IT_MANAGER",
                approval_comment="예산 확인 완료" if state == "APPROVED" else "구매 사유 보완 필요",
                updated_at="2026-09-18T09:05:00",
            )
        if state == "APPROVED":
            value["approved_at"] = "2026-09-18T09:05:00"
        examples[state] = {"summary": state + " 상태 응답", "value": value}
    return {"application/json": {"examples": examples}}
