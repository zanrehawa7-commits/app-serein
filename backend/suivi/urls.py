from django.urls import path

from . import views

app_name = "suivi"

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="notification_list"),
    path("notifications/tout-lire/", views.NotificationToutLireView.as_view(), name="notification_tout_lire"),
    path("notifications/<int:pk>/lire/", views.NotificationLireView.as_view(), name="notification_lire"),
]
