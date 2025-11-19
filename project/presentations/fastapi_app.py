import time
import logging
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel
from services.link_service import LinkService
from urllib.parse import urlparse


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI()
    short_link_service = LinkService()

    class PutLink(BaseModel):
        link: str

    @app.middleware("http")
    async def add_latency_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        latency = (time.time() - start_time) * 1000
        response.headers["X-Latency"] = f"{latency:.2f}ms"
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Exception: {exc}")
        logger.error(f"Request URL: {request.url}")
        try:
            body = await request.body()
            logger.error(f"Request body: {body.decode('utf-8')}")
        except Exception:
            logger.error("Could not read request body.")
        return Response(
            content="Internal Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def _validate_and_prepare_link(link: str) -> str:
        if not link.startswith(("http://", "https://")):
            link = "https://" + link

        parsed = urlparse(link)
        if not parsed.netloc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid link: {link}"
            )
        return link

    def _service_link_to_real(short_link: str) -> str:
        return f"http://localhost:8000/{short_link}"

    @app.post("/link")
    def create_link(put_link_request: PutLink) -> PutLink:
        valid_link = _validate_and_prepare_link(put_link_request.link)
        short_link = short_link_service.create_link(valid_link)
        return PutLink(link=_service_link_to_real(short_link))

    @app.get("/{link}")
    def get_link(link: str) -> Response:
        real_link = short_link_service.get_real_link(link)

        if real_link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short link not found :("
            )

        return Response(
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
            headers={"Location": real_link}
        )

    return app
