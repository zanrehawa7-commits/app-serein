from django.urls import path
from . import views

app_name = "stages"

urlpatterns = [
    path("stages/", views.StageListView.as_view(), name="stage_list"),
    path("stages/a-evaluer/", views.StagesAEvaluerListView.as_view(), name="stages_a_evaluer"),
    path("stages/vivier/", views.VivierListView.as_view(), name="vivier"),
    path("stages/vivier/export/", views.VivierExportCsvView.as_view(), name="vivier_export_csv"),
    path("stages/<int:pk>/", views.StageDetailView.as_view(), name="stage_detail"),
    path("stages/constituer/<int:candidature_pk>/", views.ConstituerStageView.as_view(), name="stage_constituer"),
    path("stages/<int:pk>/modifier/", views.ModifierStageView.as_view(), name="stage_modifier"),
    path("stages/<int:pk>/demarrer/", views.DemarrerStageView.as_view(), name="stage_demarrer"),
    path("stages/<int:pk>/terminer/", views.TerminerStageView.as_view(), name="stage_terminer"),
    path("stages/<int:pk>/interrompre/", views.InterrompreStageView.as_view(), name="stage_interrompre"),
    path("stages/<int:pk>/reprendre/", views.ReprendreStageView.as_view(), name="stage_reprendre"),
    path("stages/<int:pk>/evaluer/", views.EvaluerStageView.as_view(), name="stage_evaluer"),
    path("stages/<int:pk>/rapport/", views.RapportTelechargerView.as_view(), name="rapport_telecharger"),
]
