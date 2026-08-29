"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.db import connection
from django.http import HttpResponse
from django.urls import path, include


def health_check(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return HttpResponse('ok')


class LoginView(auth_views.LoginView):
    """Falls back to LOGIN_REDIRECT_URL instead of looping back to the login
    page itself - the nav's "Log in" link always passes the current page as
    `next`, which self-references when that current page is the login page."""

    def get_redirect_url(self):
        redirect_to = super().get_redirect_url()
        return '' if redirect_to == self.request.path else redirect_to


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('healthz/', health_check, name='health_check'),
    path('orders/', include('orders.urls')),
    path('', include('organisations.urls')),
    path('<slug:org_slug>/', include('events.urls')),
]

# Whitenoise only serves STATIC assets (collected at build time), not
# runtime-uploaded MEDIA files - at this app's traffic volume, having Django
# itself serve /media/ in production too (backed by a persistent volume at
# MEDIA_ROOT) is simpler and perfectly fine, rather than standing up a
# separate object-storage service.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
