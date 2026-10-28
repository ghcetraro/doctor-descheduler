# Fragmento para app/web.py — página GET /perfil
#
# Copiar la ruta en el router web.
#
# from fastapi.responses import HTMLResponse
# from app.web_context import require_web_auth, web_context
#
# @router.get("/perfil", response_class=HTMLResponse, include_in_schema=False)
# def profile_page(request: Request) -> Any:
#     if redirect := require_web_auth(request):
#         return redirect
#     return render(
#         request,
#         "profile.html",
#         {"page": "profile", **web_context(request)},
#     )
