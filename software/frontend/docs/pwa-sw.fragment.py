# Servir el service worker en la raíz (scope "/") — copiar a la app FastAPI.
# from pathlib import Path
# from fastapi.responses import FileResponse
#
# STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
#
# @app.get("/sw.js", include_in_schema=False)
# def service_worker() -> FileResponse:
#     return FileResponse(
#         STATIC_DIR / "sw.js",
#         media_type="application/javascript; charset=utf-8",
#         headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
#     )
