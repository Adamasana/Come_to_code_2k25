from django.urls import path
from assist.views import *

urlpatterns = [
    path('', index, name="index"),
    path('connect_user', connect_user, name="connect_user"),
    path('add_user', add_user, name="add_user"),
    path('logout', deconnexion, name="logout"),
    path('accueil', accueil, name="accueil"),
    path('comptes', comptes, name="comptes"),
    path('create_individual', create_individual, name='create_individual'),
    path('individual/<uuid:unique_id>/', individual_public_view, name='individual_public'),
    path('delete/<uuid:unique_id>/', delete_individual, name='delete_individual'),
    path('update_user/<int:user_id>/', update_user, name='update_user'),
    path('modifier/<uuid:unique_id>/', modifier_individual, name='modifier_individual'),
]