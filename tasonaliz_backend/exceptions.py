"""
Safe DRF Exception Handler preventing internal stacktrace or configuration leaks (CWE-209).
"""

import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def safe_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response

    logger.error("Unhandled API exception: %s", exc, exc_info=True)
    return Response(
        {
            "detail": "Sunucu tarafında beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
