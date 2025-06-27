from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail

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


def historique_individual(request, uuid):
    individual = get_object_or_404(Individual, unique_id=uuid)
    logs = individual.access_logs.select_related('accessed_by').all()
    return render(request, 'historiques.html', {'individual': individual, 'logs': logs})


def trouver_individual(request, uuid):
    individual = get_object_or_404(Individual, unique_id=uuid)
    return render(request, 'trouver.html', {'individual': individual})


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

    email = individual.email  # On garde l’e-mail avant suppression
    full_name = individual.full_name

    try:
        individual.delete()

        if email:
            protocol = "https" if request.is_secure() else "http"
            domain = request.get_host()

            message = (
                f"Bonjour {full_name},\n\n"
                "Nous vous informons que votre fiche médicale personnelle a été supprimée de notre système.\n"
                "Si vous n'êtes pas à l’origine de cette suppression ou si vous avez des préoccupations, "
                "nous vous recommandons de nous contacter immédiatement.\n\n"
                "Cordialement,\n"
                "L’équipe de gestion des dossiers médicaux."
            )

            send_mail(
                subject="Suppression de votre fiche médicale",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(request, f"Fiche supprimée avec succès et notification envoyée à {email}.")
        else:
            messages.success(request, "Fiche supprimée avec succès.")

    except Exception as e:
        messages.warning(request, f"Fiche supprimée, mais l’e-mail n’a pas pu être envoyé : {e}")

    return redirect('accueil')


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Individual
from django.contrib.auth.decorators import login_required

from django.core.mail import EmailMessage
from django.core.files.base import ContentFile

@login_required(login_url='connect_user')
def create_individual(request):
    if request.method == 'POST':
        data = request.POST
        
        individual = Individual(
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            cnib=data.get('cnib'),
            email=data.get('email'),
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

        # Envoi de mail avec pièce jointe
        if individual.email:
            try:
                # Lire le contenu du QR code généré
                qr_content = individual.qr_code.read()

                # Générer le lien de consultation
                protocol = "https" if request.is_secure() else "http"
                domain = request.get_host()
                public_url = f"{protocol}://{domain}{individual.get_public_url()}"

                # Contenu HTML de l'e-mail
                html_content = format_html(
                    """
                    <p>Bonjour <strong>{first_name}</strong>,</p>
                    <p>Votre fiche médicale a été créée avec succès.</p>
                    <p>Vous pouvez la consulter ici : <br>
                    <a href="{url}" style="color:#5fbff2;">{url}</a></p>
                    <p>Vous trouverez également en pièce jointe votre code QR à conserver soigneusement.</p>
                    <p>Cordialement,<br><em>L’équipe médicale</em>.</p>
                    """,
                    first_name=individual.first_name,
                    url=public_url
                )

                # Création de l'e-mail
                email = EmailMessage(
                    subject="Création de votre fiche médicale",
                    body=html_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[individual.email]
                )
                email.content_subtype = "html"  # Précise que le contenu est HTML

                # Joindre le QR code
                email.attach(f'qr_{individual.unique_id}.png', qr_content, 'image/png')

                # Envoi
                email.send()
                messages.success(request, "Fiche créée et e-mail envoyé avec succès.")
            except Exception as e:
                messages.warning(request, f"Fiche créée mais l'e-mail n’a pas pu être envoyé : {e}")

        messages.success(request, "Individu créé avec succès.")
        return redirect('accueil')
    
    return render(request, 'add_induvidual.html')

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import format_html

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
        try:
            if individual.email:
                protocol = "https" if request.is_secure() else "http"
                domain = request.get_host()
                public_url = f"{protocol}://{domain}{individual.get_public_url()}"

                subject = "Mise à jour de votre fiche médicale"
                from_email = settings.DEFAULT_FROM_EMAIL
                to = [individual.email]

                text_content = (
                    f"Bonjour {individual.full_name},\n\n"
                    "Nous vous informons que votre fiche médicale personnelle a été mise à jour dans notre système.\n"
                    f"Consultez votre fiche ici : {public_url}\n\n"
                    "Si vous n’êtes pas à l’origine de cette modification, contactez-nous immédiatement.\n\n"
                    "Cordialement,\nL’équipe de gestion des dossiers médicaux."
                )

                html_content = format_html(
                    """
                    <p>Bonjour <strong>{name}</strong>,</p>
                    <p>Nous vous informons que votre fiche médicale personnelle a été mise à jour dans notre système.</p>
                    <p>Vous pouvez la consulter en toute sécurité en cliquant ici :<br>
                    <a href="{url}" style="color: #5fbff2;">{url}</a></p>
                    <p>Si vous n’êtes pas à l’origine de cette modification ou si vous avez des doutes,<br>
                    merci de nous contacter immédiatement afin de sécuriser vos informations.</p>
                    <p>Cordialement,<br><em>L’équipe de gestion des dossiers médicaux.</em></p>
                    """,
                    name=individual.full_name,
                    url=public_url,
                )

                email = EmailMultiAlternatives(subject, text_content, from_email, to)
                email.attach_alternative(html_content, "text/html")
                email.send()

                messages.success(request, "Fiche modifiée et e-mail envoyé avec succès.")
        except Exception as e:
            messages.error(request, f"Fiche modifiée, mais l’e-mail n’a pas pu être envoyé : {e}")
        
        return redirect('accueil') if request.user.is_authenticated else redirect('/')

    context = {
        'individual': individual,
        'blood_types': blood_types,
        'genders': genders,
    }
    return render(request, 'modifier_individual.html', context)

import random
import string

def reset_key(request):
    if request.method == 'POST':
        cnib = request.POST.get('cnib')
        email = request.POST.get('email')

        try:
            individual = Individual.objects.get(cnib=cnib, email=email)

            # Générer un nouveau mot de passe aléatoire
            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

            # Hacher et enregistrer le nouveau mot de passe
            individual.key = make_password(new_password)
            individual.save()

            # Envoyer le mail professionnel
            subject = "Réinitialisation de votre clé d’accès"
            message = (
                f"Bonjour {individual.full_name},\n\n"
                "Une demande de réinitialisation de votre clé d’accès a été traitée avec succès.\n"
                f"Voici votre nouvelle clé d’accès confidentielle : {new_password}\n\n"
                "Nous vous conseillons de la conserver en lieu sûr et de la modifier dès que possible.\n\n"
                "Si vous n’êtes pas à l’origine de cette demande, merci de nous contacter immédiatement.\n\n"
                "Cordialement,\n"
                "L’équipe de gestion des fiches médicales."
            )

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False
            )

            messages.success(request, "Une nouvelle clé a été envoyée sur votre adresse e-mail.")
            return redirect('index')

        except Individual.DoesNotExist:
            return render(request, 'reset.html', {'error': "Aucune fiche trouvée avec ces informations."})
        except Exception as e:
            return render(request, 'reset.html', {'error': f"Erreur lors de l’envoi de l’e-mail : {e}"})

    return render(request, 'reset.html')