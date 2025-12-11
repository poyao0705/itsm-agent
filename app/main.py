from fastapi import FastAPI

from app.routers import home

app = FastAPI()

app.include_router(home.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
