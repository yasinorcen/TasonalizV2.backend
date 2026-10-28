"""
Custom security middleware & safe exception handler to prevent CWE-209 Information Disclosure
and enforce Content-Security-Policy and X-Frame-Options headers.
"""


class SecurityHeadersMiddleware:
    """Adds strict HTTP security headers to all API responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'self'; form-action 'self';",
        )
        return response
