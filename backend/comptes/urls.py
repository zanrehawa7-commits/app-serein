from django.urls import path
from . import views

app_name = "comptes"

urlpatterns = [
    path("login/", views.ConnexionView.as_view(), name="connexion"),
    path("logout/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("mot-de-passe/changer/", views.ChangerMotDePasseView.as_view(), name="password_change"),
    path("mot-de-passe/change-ok/", views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("tableau-de-bord/", views.tableau_de_bord, name="tableau_de_bord"),
    path("tableau-de-bord/admin/", views.TableauBordAdminView.as_view(), name="tableau_bord_admin"),
    path("tableau-de-bord/secretaire/", views.TableauBordSecretaireView.as_view(), name="tableau_bord_secretaire"),
    path("tableau-de-bord/responsable/", views.TableauBordResponsableView.as_view(), name="tableau_bord_responsable"),
    path("en-developpement/", views.EnDeveloppementView.as_view(), name="en_developpement"),
]
