"""
URL configuration for tasonaliz_backend project.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for Render/Railway and frontend connectivity verification."""
    return Response(
        {
            "status": "ok",
            "project": "Tasonaliz API",
            "simulation_notice": (
                "Tasonaliz, öğrenci projesi kapsamında geliştirilmiş bir bilgilendirme ve "
                "simülasyon uygulamasıdır. Alım-satım işlemi gerçekleştirmez ve yatırım tavsiyesi sunmaz."
            ),
        }
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="api-health"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("market.urls")),
]
