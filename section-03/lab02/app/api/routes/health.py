from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.documentation import SERVER_ERROR
from app.db.connection import get_db

router = APIRouter(tags=["Health"])

class HealthResponse(BaseModel):
    """DB SELECT 1에 성공한 경우의 상태 확인 결과."""
    status: str = Field(description="HTTP 요청과 DB 확인을 완료하면 ok를 반환합니다.", examples=["ok"])
    database: str = Field(description="DB에서 SELECT 1을 수행하면 connected를 반환합니다. 구매 테이블의 존재·읽기·쓰기 권한 확인을 뜻하지 않습니다.", examples=["connected"])

@router.get(
    "/health", operation_id="health_check", response_model=HealthResponse,
    summary="API와 MySQL 연결 상태를 SELECT 1로 확인",
    description=(
        "인증 없이 MySQL 연결을 얻어 SELECT 1을 실행합니다. 성공하면 HTTP 200을 반환합니다. "
        "구매 데이터를 생성하거나 변경하지 않으며 요청 파라미터와 본문은 없습니다.\n\n"
        "프로세스 생존 확인만 하는 API와 달리 DB 연결이 가능해야 성공합니다. "
        "단, purchase_requests 테이블의 존재·권한·업무 처리 성공을 보장하지는 않습니다. "
        "DB 접속 실패는 현재 구현에서 처리되지 않은 서버 오류(기본 HTTP 500)로 전달됩니다."
    ),
    responses={200: {"description": "SELECT 1 성공. API와 MySQL 연결이 응답했습니다.", "content": {"application/json": {"example": {"status": "ok", "database": "connected"}}}}, 500: SERVER_ERROR},
)
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
