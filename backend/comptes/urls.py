from django.urls import path
from . import views

app_name = "comptes"

urlpatterns = [
    # ── Authentification ──────────────────────────────────────────────────────
    path("login/", views.ConnexionView.as_view(), name="connexion"),
    path("logout/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("mot-de-passe/changer/", views.ChangerMotDePasseView.as_view(), name="password_change"),
    path("mot-de-passe/change-ok/", views.PasswordChangeDoneView.as_view(), name="password_change_done"),

    # ── Tableaux de bord ──────────────────────────────────────────────────────
    path("tableau-de-bord/", views.tableau_de_bord, name="tableau_de_bord"),
    path("tableau-de-bord/admin/", views.TableauBordAdminView.as_view(), name="tableau_bord_admin"),
    path("tableau-de-bord/secretaire/", views.TableauBordSecretaireView.as_view(), name="tableau_bord_secretaire"),
    path("tableau-de-bord/responsable/", views.TableauBordResponsableView.as_view(), name="tableau_bord_responsable"),
    path("tableau-de-bord/consultation/", views.TableauBordConsultationView.as_view(), name="tableau_bord_consultation"),
    path("en-developpement/", views.EnDeveloppementView.as_view(), name="en_developpement"),

    # ── F03 — Utilisateurs (Administrateur) ───────────────────────────────────
    path("utilisateurs/", views.UtilisateurListView.as_view(), name="utilisateur_list"),
    path("utilisateurs/nouveau/", views.UtilisateurCreateView.as_view(), name="utilisateur_creer"),
    path("utilisateurs/<int:pk>/modifier/", views.UtilisateurUpdateView.as_view(), name="utilisateur_modifier"),
    path("utilisateurs/<int:pk>/activer/", views.UtilisateurActiverView.as_view(), name="utilisateur_activer"),
    path("utilisateurs/<int:pk>/reinit-mdp/", views.UtilisateurReinitMdpView.as_view(), name="utilisateur_reinit_mdp"),

    # ── F02 — Rôles & permissions ─────────────────────────────────────────────
    path("roles/", views.RolesListView.as_view(), name="roles_list"),
    path("roles/consultation/nouveau/", views.RoleConsultationCreateView.as_view(), name="role_consultation_creer"),
    path("roles/consultation/<int:pk>/modifier/", views.RoleConsultationModifierView.as_view(), name="role_consultation_modifier"),
    path("roles/consultation/<int:pk>/activer/", views.RoleConsultationActiverView.as_view(), name="role_consultation_activer"),
    path("roles/<str:role_nom>/permissions/", views.PermissionsRoleView.as_view(), name="permissions_role"),
]
