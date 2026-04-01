from fastapi import APIRouter

from app.api.v1.endpoints import (
	analytics,
	attendance,
	auth,
	campaigns,
	health,
	inventory,
	members,
	operations,
	secure,
	training,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(secure.router)
router.include_router(members.router)
router.include_router(campaigns.router)
router.include_router(inventory.router)
router.include_router(training.router)
router.include_router(attendance.router)
router.include_router(analytics.router)
router.include_router(operations.router)
