from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth.models import Group
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import Utilisateur


def _helper(label="Enregistrer"):
    h = FormHelper()
    h.add_input(Submit("submit", label, css_class="btn-primary"))
    return h


ROLE_CHOICES = [
    ("", "--- Choisir un rôle ---"),
    ("Administrateur", "Administrateur"),
    ("Secrétaire", "Secrétaire"),
    ("Responsable", "Responsable"),
]


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
            self.user_cache = authenticate(
                self.request, username=email, password=password
            )
            if self.user_cache is None:
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


class UtilisateurCreerForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Rôle", required=True)
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "email", "telephone", "membre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from referentiels.models import Membre
        self.fields["membre"].queryset = Membre.objects.filter(
            actif=True, compte__isnull=True
        ).order_by("nom", "prenom")
        self.fields["membre"].required = False
        self.fields["membre"].label = "Membre lié (obligatoire si rôle = Responsable)"
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.helper = _helper("Créer le compte")

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        membre = cleaned.get("membre")
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if role == "Responsable" and not membre:
            self.add_error("membre", "Obligatoire pour le rôle Responsable.")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            groupe = Group.objects.get(name=self.cleaned_data["role"])
            user.groups.set([groupe])
        return user


class UtilisateurModifierForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Rôle", required=True)

    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "email", "telephone", "membre", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from referentiels.models import Membre
        instance = self.instance
        if instance and instance.pk and instance.membre_id:
            qs = Membre.objects.filter(actif=True).filter(
                Q(compte__isnull=True) | Q(pk=instance.membre_id)
            )
        else:
            qs = Membre.objects.filter(actif=True, utilisateur__isnull=True)
        self.fields["membre"].queryset = qs.order_by("nom", "prenom")
        self.fields["membre"].required = False
        self.fields["membre"].label = "Membre lié (obligatoire si rôle = Responsable)"
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        if instance and instance.pk:
            self.fields["role"].initial = instance.role or ""
        self.helper = _helper()

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        membre = cleaned.get("membre")
        if role == "Responsable" and not membre:
            self.add_error("membre", "Obligatoire pour le rôle Responsable.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            groupe = Group.objects.get(name=self.cleaned_data["role"])
            user.groups.set([groupe])
        return user


class ReinitMotDePasseForm(forms.Form):
    nouveau_mdp1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    nouveau_mdp2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper("Enregistrer le nouveau mot de passe")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("nouveau_mdp1")
        p2 = cleaned.get("nouveau_mdp2")
        if p1 and p2 and p1 != p2:
            self.add_error("nouveau_mdp2", "Les mots de passe ne correspondent pas.")
        return cleaned
