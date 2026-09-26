from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django import forms


class FormulaireConnexion(AuthenticationForm):
    username = forms.EmailField(
        label="Adresse email",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "votre@email.com"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )

    error_messages = {
        "invalid_login": "Email ou mot de passe incorrect.",
        "inactive": "Votre compte est désactivé. Contactez l'administrateur.",
    }

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email and password:
            # Tentative d'authentification normale (rejette is_active=False)
            self.user_cache = authenticate(
                self.request, username=email, password=password
            )
            if self.user_cache is None:
                # Vérifie si le compte existe mais est désactivé (RG33)
                from comptes.models import Utilisateur
                try:
                    user = Utilisateur.objects.get(email=email)
                    if user.check_password(password) and not user.is_active:
                        raise forms.ValidationError(
                            self.error_messages["inactive"],
                            code="inactive",
                        )
                except Utilisateur.DoesNotExist:
                    pass
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
