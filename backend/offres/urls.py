from django.urls import path

from . import views

app_name = "offres"

urlpatterns = [
    # Besoins
    path("besoins/", views.BesoinListView.as_view(), name="besoin_list"),
    path("besoins/nouveau/", views.BesoinCreateView.as_view(), name="besoin_creer"),
    path("besoins/<int:pk>/", views.BesoinDetailView.as_view(), name="besoin_detail"),
    path("besoins/<int:pk>/modifier/", views.BesoinModifierView.as_view(), name="besoin_modifier"),
    path("besoins/<int:pk>/annuler/", views.BesoinAnnulerView.as_view(), name="besoin_annuler"),
    # Offres
    path("offres/", views.OffreListView.as_view(), name="offre_list"),
    path("offres/nouveau/", views.OffreCreateView.as_view(), name="offre_creer"),
    path("offres/depuis-besoin/<int:besoin_pk>/", views.OffreCreateFromBesoinView.as_view(), name="offre_creer_depuis_besoin"),
    path("offres/<int:pk>/", views.OffreDetailView.as_view(), name="offre_detail"),
    path("offres/<int:pk>/modifier/", views.OffreModifierView.as_view(), name="offre_modifier"),
    path("offres/<int:pk>/ouvrir/", views.OffreOuvrirView.as_view(), name="offre_ouvrir"),
    path("offres/<int:pk>/suspendre/", views.OffreSuspendreView.as_view(), name="offre_suspendre"),
    path("offres/<int:pk>/rouvrir/", views.OffreRouvrirView.as_view(), name="offre_rouvrir"),
    path("offres/<int:pk>/fermer/", views.OffreFermerView.as_view(), name="offre_fermer"),
    path("offres/<int:pk>/supprimer/", views.OffreSupprimerView.as_view(), name="offre_supprimer"),
    # Publications
    path("offres/<int:offre_pk>/publications/ajouter/", views.PublicationCreateView.as_view(), name="publication_creer"),
    path("publications/<int:pk>/modifier/", views.PublicationModifierView.as_view(), name="publication_modifier"),
    path("publications/<int:pk>/supprimer/", views.PublicationSupprimerView.as_view(), name="publication_supprimer"),
    # Paramètre du modèle de texte d'offre
    path("offres/parametres/", views.ParametreOffreView.as_view(), name="parametre_offre"),
]
