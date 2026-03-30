from pathlib import Path

from fastapi import FastAPI

from ems.routers.sot_promotion import router as sot_promotion_router


def create_app(repo_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="SSID EMS API", version="0.1.0")
    app.state.repo_root = repo_root or Path(__file__).resolve().parents[3]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ems_api"}

    app.include_router(sot_promotion_router)
    return app


app = create_app()
