from dotenv import load_dotenv


from fastapi import FastAPI

from app.routers import home

load_dotenv()  # Load .env variables into os.environ for libraries (LangSmith, etc.)


app = FastAPI()

app.include_router(home.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
