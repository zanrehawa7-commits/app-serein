from django.urls import path
from . import views

app_name = "candidatures"

urlpatterns = [
    # Candidats
    path("candidatures/candidats/recherche/", views.CandidatRechercheView.as_view(), name="candidat_recherche"),
    path("candidatures/candidats/creer/", views.CandidatCreateView.as_view(), name="candidat_creer"),
    path("candidatures/candidats/<int:pk>/", views.CandidatDetailView.as_view(), name="candidat_detail"),
    path("candidatures/candidats/<int:pk>/modifier/", views.CandidatModifierView.as_view(), name="candidat_modifier"),
    # Candidatures
    path("candidatures/creer/<int:candidat_pk>/", views.CandidatureCreateView.as_view(), name="candidature_creer"),
    path("candidatures/", views.CandidatureListView.as_view(), name="candidature_list"),
    path("candidatures/<int:pk>/", views.CandidatureDetailView.as_view(), name="candidature_detail"),
    path("candidatures/<int:pk>/modifier/", views.CandidatureModifierView.as_view(), name="candidature_modifier"),
    # Pièces jointes
    path("candidatures/pieces/<int:pk>/telecharger/", views.PieceJointeTelechargerView.as_view(), name="piece_telecharger"),
    # Candidats à informer
    path("candidatures/a-informer/", views.CandidatsInformerListView.as_view(), name="candidats_informer"),
    path("candidatures/<int:pk>/informer/", views.CandidatureMarquerInformeView.as_view(), name="candidature_informer"),
]
