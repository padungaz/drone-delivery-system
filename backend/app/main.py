import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.customer_routes import customer_router
from app.api.routes import router
from app.config import settings
from app.database.repository import async_session, init_db
from app.storage.routes import storage_router
from app.storage.repository import StorageRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed 9 storage slots if not already present
    async with async_session() as session:
        storage_repo = StorageRepository(session)
        await storage_repo.init_storage_slots()
    logger.info("Backend started on %s:%d", settings.host, settings.port)
    yield
    logger.info("Backend shutting down")


app = FastAPI(
    title="Drone Delivery System",
    description="LAN-based autonomous drone delivery backend",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(customer_router)
app.include_router(storage_router)

