import uvicorn
from fastapi import FastAPI

from routes.process import router as process_router
from utils.config import get_setting

app = FastAPI(title="AIAgent", description="PDF -> markdown pipeline")
app.include_router(process_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def main():
    settings = get_setting()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
