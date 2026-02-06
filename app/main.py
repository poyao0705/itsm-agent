from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.session import lifespan
from app.api.api_v1 import router as api_v1
from app.web import web_router

load_dotenv()  # Load .env variables into os.environ for libraries (LangSmith, etc.)


app = FastAPI(lifespan=lifespan)

# Setup Static Files
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Mount Routers
app.include_router(web_router)  # HTMX / Template routes (no prefix)
app.include_router(api_v1, prefix="/api/v1")  # JSON API routes


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
