from aiogram import Router

from .agent import router as agent_router
from .settings import router as settings_router
from .user_account import router as user_account_router

router = Router()

router.include_routers(agent_router, settings_router, user_account_router)

__all__ = ["router"]
