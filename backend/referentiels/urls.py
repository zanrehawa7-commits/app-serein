from django.urls import path
from . import views

app_name = "referentiels"

urlpatterns = [
    # ── Départements ──────────────────────────────────────────────────────────
    path("departements/", views.DepartementListView.as_view(), name="departement_list"),
    path("departements/nouveau/", views.DepartementCreateView.as_view(), name="departement_creer"),
    path("departements/<int:pk>/", views.DepartementDetailView.as_view(), name="departement_detail"),
    path("departements/<int:pk>/modifier/", views.DepartementUpdateView.as_view(), name="departement_modifier"),
    path("departements/<int:pk>/supprimer/", views.DepartementDeleteView.as_view(), name="departement_supprimer"),

    # ── Personnel ─────────────────────────────────────────────────────────────
    path("personnels/", views.PersonnelListView.as_view(), name="personnel_list"),
    path("personnels/nouveau/", views.PersonnelCreateView.as_view(), name="personnel_creer"),
    path("personnels/<int:pk>/", views.PersonnelDetailView.as_view(), name="personnel_detail"),
    path("personnels/<int:pk>/modifier/", views.PersonnelUpdateView.as_view(), name="personnel_modifier"),
    path("personnels/<int:pk>/desactiver/", views.PersonnelDesactiverView.as_view(), name="personnel_desactiver"),

    # ── Établissements ────────────────────────────────────────────────────────
    path("etablissements/", views.EtablissementListView.as_view(), name="etablissement_list"),
    path("etablissements/nouveau/", views.EtablissementCreateView.as_view(), name="etablissement_creer"),
    path("etablissements/<int:pk>/modifier/", views.EtablissementUpdateView.as_view(), name="etablissement_modifier"),
    path("etablissements/<int:pk>/supprimer/", views.EtablissementDeleteView.as_view(), name="etablissement_supprimer"),
    path("etablissements/<int:pk>/partenaire/", views.EtablissementTogglePartenaireView.as_view(), name="etablissement_partenaire"),

    # ── Types de stage ────────────────────────────────────────────────────────
    path("types-de-stage/", views.TypeStageListView.as_view(), name="typestage_list"),
    path("types-de-stage/nouveau/", views.TypeStageCreateView.as_view(), name="typestage_creer"),
    path("types-de-stage/<int:pk>/modifier/", views.TypeStageUpdateView.as_view(), name="typestage_modifier"),
    path("types-de-stage/<int:pk>/supprimer/", views.TypeStageDeleteView.as_view(), name="typestage_supprimer"),

    # ── Canaux de publication ─────────────────────────────────────────────────
    path("canaux/", views.CanalPublicationListView.as_view(), name="canalpublication_list"),
    path("canaux/nouveau/", views.CanalPublicationCreateView.as_view(), name="canalpublication_creer"),
    path("canaux/<int:pk>/modifier/", views.CanalPublicationUpdateView.as_view(), name="canalpublication_modifier"),
    path("canaux/<int:pk>/supprimer/", views.CanalPublicationDeleteView.as_view(), name="canalpublication_supprimer"),
]
