from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.pace_calculator import (
    ApplyPaceProfileResponse,
    PaceCalculationRequest,
    PaceCalculationResponse,
    PaceProfileCreate,
    PaceProfileDetail,
    PaceProfileRead,
    PaceZoneRead,
)
from server.services import pace_calculator_service

router = APIRouter(tags=["pace calculator"])


@router.post("/pace-calculator/calculate", response_model=PaceCalculationResponse)
def calculate_paces(
    payload: PaceCalculationRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> PaceCalculationResponse:
    result = pace_calculator_service.calculate_from_race(payload.race_distance, payload.race_result)
    age_grading = pace_calculator_service.calculate_age_reference(
        payload.age,
        payload.sex,
        result["race_distance"],
        result["race_result_seconds"],
    )
    return PaceCalculationResponse(
        race_distance=result["race_distance"],
        race_result_seconds=result["race_result_seconds"],
        vdot=result["vdot"],
        zones=[PaceZoneRead.model_validate(zone) for zone in result["zones"]],
        age_reference=pace_calculator_service.build_age_reference(
            payload.age,
            payload.sex,
            result["race_distance"],
            result["race_result_seconds"],
        ),
        age_grading=age_grading.__dict__ if age_grading else None,
    )


@router.post("/pace-profiles", response_model=PaceProfileDetail, status_code=status.HTTP_201_CREATED)
def create_pace_profile(
    payload: PaceProfileCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_calculator_service.create_pace_profile(
        db,
        user_id=current_user.id,
        name=payload.name,
        race_distance=payload.race_distance,
        race_result=str(payload.race_result),
    )


@router.get("/pace-profiles", response_model=list[PaceProfileRead])
def list_pace_profiles(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_calculator_service.list_pace_profiles(db, current_user.id)


@router.get("/pace-profiles/{profile_id}", response_model=PaceProfileDetail)
def get_pace_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return pace_calculator_service.get_pace_profile(db, profile_id, current_user.id)


@router.delete("/pace-profiles/{profile_id}", response_model=MessageResponse)
def delete_pace_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    pace_calculator_service.delete_pace_profile(db, profile_id, current_user.id)
    return MessageResponse(message="Pace profile deleted.")


@router.post("/pace-profiles/{profile_id}/apply-to-pace-rules", response_model=ApplyPaceProfileResponse)
def apply_profile_to_pace_rules(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    updated_count = pace_calculator_service.apply_profile_to_pace_rules(db, profile_id, current_user.id)
    return ApplyPaceProfileResponse(message="已更新配速规则", updated_count=updated_count)
