from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Membre


class MembreForm(forms.ModelForm):
    """Formulaire de Membre avec création de compte optionnelle."""

    creer_compte = forms.BooleanField(
        required=False,
        label="Créer un compte utilisateur",
    )
    username = forms.CharField(
        required=False,
        max_length=150,
        label="Nom d'utilisateur",
    )
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Mot de passe",
    )
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Confirmation du mot de passe",
    )

    class Meta:
        model = Membre
        fields = ["nom", "prenom", "email", "actif"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.a_un_compte:
            self.fields["creer_compte"].initial = True
            self.fields["username"].initial = (
                self.instance.user_account.username
            )
            self.fields["creer_compte"].help_text = (
                "Ce membre possède déjà un compte."
            )
            self.fields["password1"].help_text = (
                "Laissez vide pour ne pas changer."
            )

    def clean(self):
        cleaned = super().clean()

        creer = cleaned.get("creer_compte")
        has_account = self.instance.pk and self.instance.a_un_compte
        username = (cleaned.get("username") or "").strip()
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        email = (cleaned.get("email") or "").strip()

        if creer and not has_account:
            if not username:
                self.add_error(
                    "username",
                    "Requis pour créer un compte.",
                )

            if not email:
                self.add_error(
                    "email",
                    "Requis pour créer un compte.",
                )

            if not password1:
                self.add_error(
                    "password1",
                    "Requis pour créer un compte.",
                )
            elif password1 != password2:
                self.add_error(
                    "password2",
                    "Les mots de passe ne correspondent pas.",
                )
            else:
                try:
                    validate_password(password1)
                except forms.ValidationError as error:
                    self.add_error("password1", error)

        if has_account and password1 and password1 != password2:
            self.add_error(
                "password2",
                "Les mots de passe ne correspondent pas.",
            )

        return cleaned

    def save(self, commit=True):
        from accounts.models import Role, User

        membre = super().save(commit=False)
        creer = self.cleaned_data.get("creer_compte")

        # Détecter si un compte existait avant la modification.
        ancien_compte = None

        if self.instance.pk:
            try:
                ancien_compte = self.instance.user_account
            except User.DoesNotExist:
                ancien_compte = None

        # Pas de compte : le membre est automatiquement désactivé.
        if not creer and ancien_compte is None:
            membre.actif = False

        if commit:
            membre.save()

            if creer and ancien_compte is None:
                # Créer un nouveau compte.
                role_maitre = Role.objects.filter(
                    code="maitre_stage",
                ).first()

                User.objects.create_user(
                    username=self.cleaned_data["username"].strip(),
                    email=self.cleaned_data["email"].strip(),
                    password=self.cleaned_data["password1"],
                    first_name=membre.prenom,
                    last_name=membre.nom,
                    role=role_maitre,
                    membre=membre,
                    is_active=False,
                )

            elif ancien_compte is not None:
                # Mettre à jour le compte existant.
                ancien_compte.email = self.cleaned_data["email"].strip()
                ancien_compte.first_name = membre.prenom
                ancien_compte.last_name = membre.nom

                if self.cleaned_data.get("password1"):
                    ancien_compte.set_password(
                        self.cleaned_data["password1"],
                    )

                ancien_compte.is_active = membre.actif
                ancien_compte.save()

        return membre