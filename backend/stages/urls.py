from django.urls import path
from . import views

app_name = "stages"

urlpatterns = [
    path("stages/", views.StageListView.as_view(), name="stage_list"),
    path("stages/<int:pk>/", views.StageDetailView.as_view(), name="stage_detail"),
    path("stages/constituer/<int:candidature_pk>/", views.ConstituerStageView.as_view(), name="stage_constituer"),
    path("stages/<int:pk>/modifier/", views.ModifierStageView.as_view(), name="stage_modifier"),
    path("stages/<int:pk>/terminer/", views.TerminerStageView.as_view(), name="stage_terminer"),
    path("stages/<int:pk>/interrompre/", views.InterrompreStageView.as_view(), name="stage_interrompre"),
]
