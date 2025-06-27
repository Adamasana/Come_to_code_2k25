from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password

# Create your views here.
def index(request):
    if request.user.is_authenticated:
        return redirect('accueil')
    
    if request.method == 'POST':
        cnib = request.POST.get('cnib')
        password = request.POST.get('password')

        try:
            individual = Individual.objects.get(cnib=cnib)
            # Vérifie si le mot de passe fourni correspond à la clé hachée
            if check_password(password, individual.key):
                return render(request, 'trouver.html', {'individual': individual})
            else:
                return render(request, 'index.html', {'error': "Identifiants incorrects"})
        except Individual.DoesNotExist:
            return render(request, 'index.html', {'error': "Identifiants incorrects"})

    return render(request, "index.html")


def deconnexion(request):
    logout(request)
    return redirect('connect_user')


def connect_user(request):
    if request.method == "GET":
        return render(request, "connect_user.html")

    elif request.method == "POST":
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')

        try:
            utilisateur = (
                User.objects.filter(email=username_or_email).first()
                or User.objects.get(username=username_or_email)
            )

            if not utilisateur.is_active:
                messages.error(request, "Votre compte n'est pas activé.")
                return render(request, "connect_user.html", {"utilisateur": utilisateur})

            username = utilisateur.username

        except User.DoesNotExist:
            messages.error(request, "Nous n'avons pas trouvé de compte correspondant à ces identifiants.")
            return render(request, "connect_user.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            
            login(request, user)
            return redirect('accueil')

        else:
            messages.error(request, "Mot de passe incorrect !")
            return render(request, "connect_user.html")
        

@login_required(login_url='connect_user')
def add_user(request):
    # Empêcher un agent d'accéder à la page
    if hasattr(request.user, 'profile') and request.user.profile.is_agent:
        messages.error(request, "Vous n'avez pas la permission de créer un compte administrateur.")
        return redirect('accueil')

    if request.method == 'POST':
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        statut = request.POST.get('statut')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur est déjà pris.")
            return render(request, "adduser.html")

        # Empêcher un agent de créer un compte admin (encore une fois pour sécurité)
        if statut == 'admin' and request.user.profile.user_type != 'admin':
            messages.error(request, "Vous n'avez pas la permission de créer un administrateur.")
            return render(request, "adduser.html")

        # Créer l'utilisateur selon le type
        user = User.objects.create(
            username=username,
            first_name=prenom,
            last_name=nom,
            email=email,
            password=make_password(password),
            is_staff=(statut == 'admin'),
            is_superuser=(statut == 'admin'),
            is_active=True
        )

        # Créer le profil lié
        Profile.objects.create(
            user=user,
            user_type=statut
        )

        messages.success(request, "Utilisateur créé avec succès.")
        return redirect('comptes')  # Redirection vers la liste des utilisateurs

    return render(request, "adduser.html")


@login_required(login_url='connect_user')
def accueil(request):
    fiches = Individual.objects.filter(is_active = True)
    context = {"fiches": fiches}
    return render(request, "accueil.html", context = context)


@login_required(login_url='connect_user')
def comptes(request):
    users = User.objects.all()
    context = {"users": users}
    return render(request, "comptes.html", context = context)


@login_required(login_url='connect_user')
def update_user(request, user_id):
    user_to_update = get_object_or_404(User, pk=user_id)

    # Empêcher un utilisateur de désactiver ou modifier son propre compte
    if request.user == user_to_update:
        messages.error(request, "Vous ne pouvez pas modifier votre propre compte.")
        return redirect('comptes')

    user_to_update.is_active = not user_to_update.is_active
    user_to_update.save()

    if user_to_update.is_active:
        messages.success(request, f"L'utilisateur {user_to_update.username} a été débloqué.")
    else:
        messages.warning(request, f"L'utilisateur {user_to_update.username} a été bloqué.")

    return redirect('comptes')

def get_client_ip(request):
    """Récupère l'adresse IP du client (même derrière un proxy)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def individual_public_view(request, unique_id):
    individual = get_object_or_404(Individual, unique_id=unique_id)

    # Création du log d'accès
    AccessLog.objects.create(
        individual=individual,
        accessed_by=request.user if request.user.is_authenticated else None,
        access_type='private' if request.user.is_authenticated else 'public',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    context = {'individual': individual}
    return render(request, 'individual_public.html', context)


@login_required(login_url='connect_user')
def delete_individual(request, unique_id):
    individual = get_object_or_404(Individual, unique_id=unique_id)
    individual.delete()
    messages.success(request, "Fiche supprimée avec succès.")
    return redirect('accueil')


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Individual
from django.contrib.auth.decorators import login_required

@login_required(login_url='connect_user')
def create_individual(request):
    if request.method == 'POST':
        data = request.POST
        
        individual = Individual(
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            cnib=data.get('cnib'),
            key=make_password(data.get('key')),  # Hachage de la clé
            date_of_birth=data.get('date_of_birth'),
            gender=data.get('gender'),
            blood_type=data.get('blood_type'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            critical_allergies=data.get('critical_allergies', ''),
            current_medications=data.get('current_medications', ''),
            medical_conditions=data.get('medical_conditions', ''),
            past_surgeries=data.get('past_surgeries', ''),
            medical_history=data.get('medical_history', ''),
            attending_physician=data.get('attending_physician', ''),
            physician_phone=data.get('physician_phone', ''),
            insurance_info=data.get('insurance_info', ''),
            additional_emergency_contacts=data.get('additional_emergency_contacts', ''),
            created_by=request.user
        )
        individual.generate_qr_code(request)
        individual.save()
        messages.success(request, "Individu créé avec succès.")
        return redirect('accueil')
    
    return render(request, 'add_induvidual.html')


def modifier_individual(request, unique_id):
    individual = get_object_or_404(Individual, unique_id=unique_id)

    blood_types = [bt[0] for bt in Individual.BLOOD_TYPE_CHOICES]
    genders = [g[0] for g in Individual.GENDER_CHOICES]

    if request.method == 'POST':
        # Récupérer les données du formulaire
        individual.emergency_contact_name = request.POST.get('emergency_contact_name', individual.emergency_contact_name)
        individual.emergency_contact_phone = request.POST.get('emergency_contact_phone', individual.emergency_contact_phone)
        individual.insurance_info = request.POST.get('insurance_info', individual.insurance_info)
        individual.critical_allergies = request.POST.get('critical_allergies', individual.critical_allergies)
        individual.current_medications = request.POST.get('current_medications', individual.current_medications)
        individual.attending_physician = request.POST.get('attending_physician', individual.attending_physician)
        individual.physician_phone = request.POST.get('physician_phone', individual.physician_phone)
        individual.medical_conditions = request.POST.get('medical_conditions', individual.medical_conditions)
        individual.past_surgeries = request.POST.get('past_surgeries', individual.past_surgeries)
        individual.medical_history = request.POST.get('medical_history', individual.medical_history)
        individual.additional_emergency_contacts = request.POST.get('additional_emergency_contacts', individual.additional_emergency_contacts)
        
        individual.save()
        messages.success(request, "Fiche mise à jour avec succès.")
        if request.user.is_authenticated:
            return redirect('accueil')
        else:
            return redirect('/')

    context = {
        'individual': individual,
        'blood_types': blood_types,
        'genders': genders,
    }
    return render(request, 'modifier_individual.html', context)