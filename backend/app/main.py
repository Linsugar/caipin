import logging
from pathlib import Path

import redis
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.analysis_service import AnalysisService
from app.config import load_config
from app.db import AnalysisRecord, UploadedImage, make_session_factory
from app.logging_utils import log_json, logger, truncate_for_log
from app.poi_service import PoiService
from app.providers import ProviderHTTPError, ProviderTimeoutError
from app.schemas import AnalysisRequest, AnalysisResult, ImageUploadResponse, NearbyPoiRequest, PoiCandidate
from app.security import SecurityService, get_client_identity
from app.storage import LocalImageStorage, StorageError


def _setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Avoid duplicate logs if create_app gets called multiple times
    logger.propagate = False


def create_app(
    testing: bool = False,
    storage_root: str | Path | None = None,
    rate_limit_per_minute: int | None = None,
    analysis_service: AnalysisService | None = None,
) -> FastAPI:
    config = load_config()
    _setup_logging()
    if testing:
        config.providers.use_mock_models = True
        config.security.client_keys = ["dev-client-key"]
    if storage_root is not None:
        config.storage.root_dir = str(storage_root)
    if rate_limit_per_minute is not None:
        config.security.rate_limit_per_minute = rate_limit_per_minute

    app = FastAPI(title=config.app_name)
    if config.logging.print_request_response:
        app.add_middleware(RequestResponseLoggingMiddleware, max_body_chars=config.logging.max_body_chars)
    storage = LocalImageStorage(config.storage.root_dir, config.storage.max_bytes)
    analysis_service = analysis_service or (AnalysisService.mocked() if testing else AnalysisService.from_config(config.providers))
    poi_service = PoiService(config.providers)
    session_factory: sessionmaker[Session] | None = None if testing else make_session_factory(config.database)
    redis_client = None if testing else redis.Redis.from_url(config.redis.url, decode_responses=True)
    security_service = SecurityService(config.security, redis_client=redis_client)
    image_index: dict[str, ImageUploadResponse] = {}

    def get_db() -> Session | None:
        if session_factory is None:
            yield None
            return
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def protect(route_name: str, count_daily_analysis: bool = False):
        async def dependency(
            request: Request,
            client_key_header: str | None = Header(default=None, alias=config.security.header_name),
        ) -> str:
            client_key = security_service.require_api_key(client_key_header)
            identity = get_client_identity(request, client_key)
            security_service.check_minute_limit(identity, route_name)
            if count_daily_analysis:
                security_service.check_daily_analysis_limit(identity)
            return client_key

        return dependency

    def _resolve_image_path(image_id: str, db: Session | None) -> str | None:
        if image_id in image_index:
            return str(storage.absolute_path(image_index[image_id].relative_path))
        if db is not None:
            record = db.query(UploadedImage).filter_by(image_id=image_id).first()
            if record is not None:
                return str(storage.absolute_path(record.relative_path))
        return None

    @app.get("/health")
    def health() -> dict:
        dependencies = {"mysql": "skipped" if testing else "ok", "redis": "skipped" if testing else "ok"}
        if redis_client is not None:
            try:
                redis_client.ping()
            except Exception:
                dependencies["redis"] = "error"
        return {"status": "ok", "dependencies": dependencies}

    @app.post("/api/v1/images", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
    async def upload_image(
        file: UploadFile = File(...),
        _: str = Depends(protect("upload_image")),
        db: Session | None = Depends(get_db),
    ):
        data = await file.read()
        try:
            saved = storage.save_upload(file.filename or "upload", file.content_type or "", data)
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        response = ImageUploadResponse(**saved.__dict__)
        image_index[response.image_id] = response
        if db is not None:
            db.add(
                UploadedImage(
                    image_id=response.image_id,
                    relative_path=response.relative_path,
                    content_type=response.content_type,
                    size_bytes=response.size_bytes,
                )
            )
            db.commit()
        return response

    @app.post("/api/v1/analyses", response_model=AnalysisResult)
    async def analyze(
        request: AnalysisRequest,
        _: str = Depends(protect("analyze", count_daily_analysis=True)),
        db: Session | None = Depends(get_db),
    ):
        image_path = _resolve_image_path(request.image_id, db)
        if image_path is None:
            raise HTTPException(status_code=404, detail="image not found")

        try:
            result = await analysis_service.analyze(request, image_path)
        except ProviderTimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except ProviderHTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            log_json("ANALYZE_ERROR", {"error": str(exc), "type": type(exc).__name__})
            raise HTTPException(status_code=500, detail=f"analysis failed: {exc}") from exc
        if db is not None:
            db.add(
                AnalysisRecord(
                    image_id=request.image_id,
                    request_json=request.model_dump_json(),
                    result_json=result.model_dump_json(),
                )
            )
            db.commit()
        return result

    @app.post("/api/v1/locations/nearby", response_model=list[PoiCandidate])
    async def nearby_pois(
        request: NearbyPoiRequest,
        _: str = Depends(protect("nearby_pois")),
    ):
        return await poi_service.nearby(request)

    @app.post("/api/v1/storage/cleanup")
    def cleanup_storage(_: str = Depends(protect("cleanup_storage"))) -> dict:
        removed = storage.cleanup_expired(config.storage.keep_days)
        return {"removed": removed, "keep_days": config.storage.keep_days}

    return app


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_chars: int = 4000) -> None:
        super().__init__(app)
        self.max_body_chars = max_body_chars

    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        request_preview = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "headers": {
                key: value
                for key, value in request.headers.items()
                if key.lower() in {"content-type", "content-length", "x-client-key", "user-agent"}
            },
            "body": f"<multipart:{len(body)} bytes>" if "multipart/form-data" in content_type else truncate_for_log(body.decode("utf-8", errors="replace"), self.max_body_chars),
        }
        log_json("HTTP_REQUEST", request_preview, self.max_body_chars)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        response = await call_next(Request(request.scope, receive))
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        response_preview = {
            "status_code": response.status_code,
            "headers": {
                key: value
                for key, value in response.headers.items()
                if key.lower() in {"content-type", "content-length"}
            },
            "body": truncate_for_log(response_body.decode("utf-8", errors="replace"), self.max_body_chars),
        }
        log_json("HTTP_RESPONSE", response_preview, self.max_body_chars)
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
