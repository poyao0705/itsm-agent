from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import lifespan
from app.api.api_v1 import router as api_v1
from app.dependencies.database import get_db
from app.services.change_management.evaluations import EvaluationService

load_dotenv()  # Load .env variables into os.environ for libraries (LangSmith, etc.)


app = FastAPI(lifespan=lifespan)

# Setup Templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Mount API Router
app.include_router(api_v1, prefix="/api/v1")


@app.get("/")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    service = EvaluationService(db)
    evals = await service.get_evaluations(limit=5)

    # If HTMX request, return the dashboard partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/dashboard.html", {"request": request, "evaluations": evals}
        )

    # Full page load
    return templates.TemplateResponse(
        "index.html", {"request": request, "evaluations": evals}
    )


@app.get("/evaluations")
async def evaluations_page(request: Request, db: AsyncSession = Depends(get_db)):
    service = EvaluationService(db)
    evals = await service.get_evaluations(limit=20)

    # If HTMX request, return the evaluations list partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/evaluations_list.html", {"request": request, "evaluations": evals}
        )

    # Full page load
    return templates.TemplateResponse(
        "evaluations.html", {"request": request, "evaluations": evals}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
