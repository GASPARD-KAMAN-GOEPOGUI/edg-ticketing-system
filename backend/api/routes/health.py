from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.dependencies import get_db
from api.configs.Environment import get_environment

router = APIRouter(tags=["health"])

env = get_environment()


@router.get("/")
async def root():
    return {
        "message": f"Bienvenue sur {env.APP_NAME}",
        "version": env.APP_VERSION,
    }


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


