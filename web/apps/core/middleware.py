import re
from django.conf import settings
from django.shortcuts import redirect

class LoginRequiredMiddleware:
    """
    Middleware that requires a user to be authenticated to view any page other
    than the landing page and authentication-related pages.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            re.compile(r'^$'),             # Root landing page
            re.compile(r'^auth/'),         # Login, register, logout
            re.compile(r'^static/'),       # Static files
            re.compile(r'^media/'),        # Media files
        ]

    def __call__(self, request):
        path = request.path_info.lstrip('/')
        
        exempt = any(m.match(path) for m in self.exempt_urls)
        
        if not request.user.is_authenticated and not exempt:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            
        return self.get_response(request)
