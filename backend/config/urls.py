from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="comptes:tableau_de_bord", permanent=False)),
    path("", include("comptes.urls")),
    path("referentiels/", include("referentiels.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
