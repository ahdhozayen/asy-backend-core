from django.middleware.csrf import get_token
from django.utils.deprecation import MiddlewareMixin

class EnsureCSRFMiddleware(MiddlewareMixin):
    """
    Middleware to ensure CSRF token is set for API requests.
    This is needed for session-based authentication with the API.
    """
    def process_request(self, request):
        # Skip CSRF for safe methods or if already has CSRF token
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return
            
        # Skip if it's an API request with token auth
        if request.META.get('HTTP_AUTHORIZATION', '').startswith('Token '):
            return
            
        # Ensure CSRF token is set for session-based auth
        get_token(request)
