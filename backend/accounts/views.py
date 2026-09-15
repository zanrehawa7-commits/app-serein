from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.
class HomeView(LoginRequiredMixin, TemplateView):
    """
    Page d'accueil de l'application, accessible uniquement aux utilisateurs connectés. Redirige"""
    template_name = 'accounts/home.html'
