from aiogram import Router

from .agent import router as agent_router
from .settings import router as settings_router

router = Router()

router.include_routers(agent_router, settings_router)

__all__ = ["router"]
