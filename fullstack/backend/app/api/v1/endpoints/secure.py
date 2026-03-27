from fastapi import APIRouter, Depends

from app.api.deps.auth import (
    require_administrator,
    require_cashier,
    require_employee,
    require_inventory_clerk,
    require_store_manager,
)
from app.schemas.auth import AuthUser

router = APIRouter(prefix="/secure", tags=["secure"])


@router.get("/administrator", response_model=AuthUser)
def administrator_only(current_user: AuthUser = Depends(require_administrator)) -> AuthUser:
    return current_user


@router.get("/store-manager", response_model=AuthUser)
def store_manager_only(current_user: AuthUser = Depends(require_store_manager)) -> AuthUser:
    return current_user


@router.get("/inventory-clerk", response_model=AuthUser)
def inventory_clerk_only(current_user: AuthUser = Depends(require_inventory_clerk)) -> AuthUser:
    return current_user


@router.get("/cashier", response_model=AuthUser)
def cashier_only(current_user: AuthUser = Depends(require_cashier)) -> AuthUser:
    return current_user


@router.get("/employee", response_model=AuthUser)
def employee_only(current_user: AuthUser = Depends(require_employee)) -> AuthUser:
    return current_user
