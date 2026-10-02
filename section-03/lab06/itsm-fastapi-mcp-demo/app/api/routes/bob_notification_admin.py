"""Bob 관리자 전용 사용자/그룹 관리와 공지 발행 API."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.models.bob_notification import (
    BobGroup,
    BobUser,
    BobUserGroup,
    BobUserToken,
    NotificationReceipt,
)
from app.services.bob_notification_service import persist_notification
from app.schemas.bob_notification_admin import (
    BobGroupCreate,
    BobIdentity,
    BobNotificationCreate,
    BobUserCreate,
    BobUserUpdate,
    NotificationReadRequest,
)

router = APIRouter(prefix="/service-request-events", tags=["Bob Users & Groups"])
AdminSession = Depends(get_db)


def _token_hash(token: str) -> str:
    """원문 Bearer token은 저장하지 않고 SHA-256 digest만 DB에서 조회합니다."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bearer_value(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bob Bearer token이 필요합니다.")
    return authorization.removeprefix("Bearer ").strip()


def current_bob_user(
    authorization: str | None = Header(default=None),
    db: Session = AdminSession,
) -> BobUser:
    """토큰 해시와 활성 계정을 확인해 요청자의 employee_no를 결정합니다."""
    token = _bearer_value(authorization)
    token_row = db.scalar(
        select(BobUserToken).where(
            BobUserToken.token_hash == _token_hash(token),
            BobUserToken.revoked_at.is_(None),
        )
    )
    if not token_row:
        raise HTTPException(status_code=401, detail="유효하지 않거나 폐기된 Bob token입니다.")
    user = db.get(BobUser, token_row.employee_no)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="비활성 Bob 사용자입니다.")
    # Digest equality is checked again in constant time after indexed lookup.
    if not hmac.compare_digest(token_row.token_hash, _token_hash(token)):
        raise HTTPException(status_code=401, detail="유효하지 않은 Bob token입니다.")
    return user


def require_admin(user: BobUser = Depends(current_bob_user)) -> BobUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="알림 관리자 권한이 필요합니다.")
    return user


def _group_names(db: Session, employee_no: str) -> list[str]:
    return list(
        db.scalars(
            select(BobUserGroup.group_name)
            .where(BobUserGroup.employee_no == employee_no)
            .order_by(BobUserGroup.group_name)
        ).all()
    )


@router.get("/identity", response_model=BobIdentity, summary="Bob token identity 확인")
def get_identity(user: BobUser = Depends(current_bob_user), db: Session = AdminSession):
    """Event MCP SSE relay가 인증된 사용자와 그룹 정보를 조회합니다."""
    return BobIdentity(
        employee_no=user.employee_no,
        is_admin=user.is_admin,
        status="active",
        group_names=_group_names(db, user.employee_no),
    )


@router.post("/receipts/read", summary="사용자 공지 읽음 상태 저장")
def mark_notifications_read(
    request: NotificationReadRequest,
    user: BobUser = Depends(current_bob_user),
    db: Session = AdminSession,
):
    """현재 사용자에게 발급된 receipt만 읽음 처리합니다."""
    result = db.execute(
        update(NotificationReceipt)
        .where(
            NotificationReceipt.employee_no == user.employee_no,
            NotificationReceipt.notification_id.in_(set(request.notification_ids)),
            NotificationReceipt.read_at.is_(None),
        )
        .values(read_at=func.now())
    )
    db.commit()
    return {"updated_count": result.rowcount or 0}


@router.get("/admin/targets", summary="공지 수신 대상 목록")
def get_targets(user: BobUser = Depends(require_admin), db: Session = AdminSession):
    groups = list(db.scalars(select(BobGroup.group_name).order_by(BobGroup.group_name)).all())
    employees = list(
        db.scalars(
            select(BobUser.employee_no)
            .where(BobUser.status == "active")
            .order_by(BobUser.employee_no)
        ).all()
    )
    employee_groups = {employee: _group_names(db, employee) for employee in employees}
    group_counts = {
        group: sum(group in memberships for memberships in employee_groups.values())
        for group in groups
    }
    return {
        "groups": groups,
        "group_counts": group_counts,
        "employees": employees,
        "employee_groups": employee_groups,
    }


@router.get("/admin/users", summary="Bob 사용자 목록")
def list_users(user: BobUser = Depends(require_admin), db: Session = AdminSession):
    users = list(
        db.scalars(
            select(BobUser)
            .where(BobUser.employee_no != "SYSTEM")
            .order_by(BobUser.employee_no)
        ).all()
    )
    result = []
    for bob_user in users:
        token_row = db.scalar(
            select(BobUserToken)
            .where(
                BobUserToken.employee_no == bob_user.employee_no,
                BobUserToken.revoked_at.is_(None),
            )
            .order_by(BobUserToken.issued_at.desc())
            .limit(1)
        )
        any_token = token_row or db.scalar(
            select(BobUserToken.token_id)
            .where(BobUserToken.employee_no == bob_user.employee_no)
            .limit(1)
        )
        result.append({
            "employee_no": bob_user.employee_no,
            "is_admin": bob_user.is_admin,
            "status": bob_user.status,
            "group_names": _group_names(db, bob_user.employee_no),
            "token_status": "issued" if token_row else "revoked" if any_token else "not issued",
            "token_masked": f"••••{token_row.token_last_four}" if token_row else None,
        })
    return {"users": result}


@router.post("/admin/users", status_code=status.HTTP_201_CREATED, summary="Bob 사용자 등록 및 token 발급")
def create_user(
    request: BobUserCreate,
    response: Response,
    actor: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    employee_no = request.employee_no.strip()
    if db.get(BobUser, employee_no):
        raise HTTPException(status_code=409, detail="이미 등록된 employee_no입니다.")
    groups = list(dict.fromkeys(request.group_names))
    unknown = [name for name in groups if not db.get(BobGroup, name)]
    if unknown:
        raise HTTPException(status_code=422, detail=f"등록되지 않은 그룹: {', '.join(unknown)}")
    token = secrets.token_urlsafe(32)
    user = BobUser(employee_no=employee_no, is_admin=request.is_admin, status="active")
    token_row = BobUserToken(
        token_id=str(uuid4()),
        employee_no=employee_no,
        token_hash=_token_hash(token),
        token_last_four=token[-4:],
    )
    db.add(user)
    db.add(token_row)
    db.add_all(BobUserGroup(employee_no=employee_no, group_name=name) for name in groups)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="사용자 또는 그룹 매핑을 저장하지 못했습니다.") from exc
    response.headers["Cache-Control"] = "no-store"
    return {
        "employee_no": employee_no,
        "is_admin": user.is_admin,
        "status": user.status,
        "group_names": groups,
        "token": token,
        "token_masked": f"••••{token[-4:]}",
    }


@router.put("/admin/users/{employee_no}", summary="Bob 사용자와 그룹 매핑 수정")
def update_user(
    employee_no: str,
    request: BobUserUpdate,
    actor: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    user = db.get(BobUser, employee_no)
    if not user:
        raise HTTPException(status_code=404, detail="Bob 사용자를 찾을 수 없습니다.")
    groups = list(dict.fromkeys(request.group_names))
    unknown = [name for name in groups if not db.get(BobGroup, name)]
    if unknown:
        raise HTTPException(status_code=422, detail=f"등록되지 않은 그룹: {', '.join(unknown)}")
    if user.is_admin and (not request.is_admin or request.status != "active"):
        active_admin_count = db.scalar(
            select(func.count()).select_from(BobUser).where(
                BobUser.is_admin.is_(True), BobUser.status == "active"
            )
        ) or 0
        if active_admin_count <= 1:
            raise HTTPException(status_code=409, detail="마지막 활성 관리자는 비활성화하거나 권한을 해제할 수 없습니다.")
    user.is_admin = request.is_admin
    user.status = request.status
    existing = list(
        db.scalars(select(BobUserGroup).where(BobUserGroup.employee_no == employee_no)).all()
    )
    for mapping in existing:
        db.delete(mapping)
    db.add_all(BobUserGroup(employee_no=employee_no, group_name=name) for name in groups)
    if request.status == "inactive":
        tokens = list(
            db.scalars(
                select(BobUserToken).where(
                    BobUserToken.employee_no == employee_no,
                    BobUserToken.revoked_at.is_(None),
                )
            ).all()
        )
        for token in tokens:
            token.revoked_at = datetime.utcnow()
    db.commit()
    return {"employee_no": employee_no, "is_admin": user.is_admin, "status": user.status, "group_names": groups}


@router.delete("/admin/users/{employee_no}", summary="Bob 사용자 비활성화")
def deactivate_user(
    employee_no: str,
    actor: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    user = db.get(BobUser, employee_no)
    if not user:
        raise HTTPException(status_code=404, detail="Bob 사용자를 찾을 수 없습니다.")
    if user.is_admin:
        active_admin_count = db.scalar(
            select(func.count()).select_from(BobUser).where(
                BobUser.is_admin.is_(True), BobUser.status == "active"
            )
        ) or 0
        if active_admin_count <= 1:
            raise HTTPException(status_code=409, detail="마지막 활성 관리자는 비활성화할 수 없습니다.")
    user.status = "inactive"
    for token in db.scalars(
        select(BobUserToken).where(
            BobUserToken.employee_no == employee_no,
            BobUserToken.revoked_at.is_(None),
        )
    ).all():
        token.revoked_at = datetime.utcnow()
    db.commit()
    return {"employee_no": employee_no, "status": user.status}


@router.post("/admin/users/{employee_no}/token", summary="Bob 사용자 token 재발급")
def rotate_token(
    employee_no: str,
    response: Response,
    actor: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    user = db.get(BobUser, employee_no)
    if not user or user.status != "active":
        raise HTTPException(status_code=404, detail="활성 Bob 사용자를 찾을 수 없습니다.")
    old_tokens = list(
        db.scalars(
            select(BobUserToken).where(
                BobUserToken.employee_no == employee_no,
                BobUserToken.revoked_at.is_(None),
            )
        ).all()
    )
    now = datetime.utcnow()
    for old in old_tokens:
        old.revoked_at = now
    token = secrets.token_urlsafe(32)
    db.add(BobUserToken(
        token_id=str(uuid4()),
        employee_no=employee_no,
        token_hash=_token_hash(token),
        token_last_four=token[-4:],
    ))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"employee_no": employee_no, "token": token, "token_masked": f"••••{token[-4:]}"}


@router.post("/admin/groups", status_code=status.HTTP_201_CREATED, summary="그룹 생성")
def create_group(request: BobGroupCreate, user: BobUser = Depends(require_admin), db: Session = AdminSession):
    name = request.group_name.strip()
    if db.get(BobGroup, name):
        raise HTTPException(status_code=409, detail="이미 등록된 그룹입니다.")
    db.add(BobGroup(group_name=name, description=request.description))
    db.commit()
    return {"group_name": name, "description": request.description, "member_count": 0}


@router.get("/admin/groups", summary="그룹과 구성원 목록")
def list_groups(user: BobUser = Depends(require_admin), db: Session = AdminSession):
    groups = list(db.scalars(select(BobGroup).order_by(BobGroup.group_name)).all())
    result = []
    for group in groups:
        members = list(
            db.scalars(
                select(BobUser.employee_no)
                .join(BobUserGroup, BobUser.employee_no == BobUserGroup.employee_no)
                .where(
                    BobUserGroup.group_name == group.group_name,
                    BobUser.status == "active",
                )
                .order_by(BobUser.employee_no)
            ).all()
        )
        result.append({
            "group_name": group.group_name,
            "description": group.description,
            "members": members,
            "member_count": len(members),
        })
    return {"groups": result}


@router.put("/admin/groups/{group_name}/members/{employee_no}", status_code=status.HTTP_204_NO_CONTENT)
def add_group_member(
    group_name: str,
    employee_no: str,
    user: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    group = db.get(BobGroup, group_name)
    member = db.get(BobUser, employee_no)
    if not group or not member or member.status != "active":
        raise HTTPException(status_code=404, detail="그룹 또는 사용자를 찾을 수 없습니다.")
    mapping = db.get(BobUserGroup, (employee_no, group_name))
    if not mapping:
        db.add(BobUserGroup(employee_no=employee_no, group_name=group_name))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/admin/groups/{group_name}/members/{employee_no}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member(
    group_name: str,
    employee_no: str,
    user: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    mapping = db.get(BobUserGroup, (employee_no, group_name))
    if mapping:
        db.delete(mapping)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/admin/groups/{group_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_name: str, user: BobUser = Depends(require_admin), db: Session = AdminSession):
    group = db.get(BobGroup, group_name)
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    for mapping in db.scalars(select(BobUserGroup).where(BobUserGroup.group_name == group_name)).all():
        db.delete(mapping)
    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/messages", status_code=status.HTTP_201_CREATED, summary="관리자 공지 발행")
def publish_admin_notification(
    request: BobNotificationCreate,
    actor: BobUser = Depends(require_admin),
    db: Session = AdminSession,
):
    return persist_notification(db, request, actor.employee_no)
