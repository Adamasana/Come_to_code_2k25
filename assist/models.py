from django.db import models
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from io import BytesIO
from django.core.files import File
from PIL import Image
import uuid
import qrcode
from datetime import date
import os
from django.conf import settings
# Create your models here.

class Profile(models.Model):
    USER_TYPE_CHOICES = [
        ('admin', 'Administrateur'),
        ('agent', 'Agent'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='agent')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"

    @property
    def is_admin(self):
        return self.user_type == 'admin'

    @property
    def is_agent(self):
        return self.user_type == 'agent'
    


class Individual(models.Model):
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]

    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    unique_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Identifiant unique"
    )

    # Infos publiques
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    cnib = models.CharField(max_length=15, verbose_name="Cnib")
    key = models.CharField(max_length=10000, verbose_name="Key")  # à hasher manuellement
    email = models.EmailField(null=True, blank=True,)
    date_of_birth = models.DateField(verbose_name="Date de naissance")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name="Sexe")
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, verbose_name="Groupe sanguin")

    emergency_contact_name = models.CharField(max_length=200, verbose_name="Contact d'urgence (nom)")
    emergency_contact_phone = models.CharField(max_length=20, verbose_name="Contact d'urgence (téléphone)")
    critical_allergies = models.TextField(blank=True, verbose_name="Allergies critiques")
    current_medications = models.TextField(blank=True, verbose_name="Médicaments actuels")

    # Infos sensibles
    medical_conditions = models.TextField(blank=True, verbose_name="Conditions médicales")
    past_surgeries = models.TextField(blank=True, verbose_name="Chirurgies passées")
    medical_history = models.TextField(blank=True, verbose_name="Historique médical détaillé")
    attending_physician = models.CharField(max_length=200, blank=True, verbose_name="Médecin traitant")
    physician_phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du médecin")
    insurance_info = models.TextField(blank=True, verbose_name="Informations d'assurance")
    additional_emergency_contacts = models.TextField(blank=True, verbose_name="Contacts d'urgence supplémentaires")

    # Admin
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Créé par")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, verbose_name="Code QR")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Individu"
        verbose_name_plural = "Individus"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def get_public_url(self):
        """URL publique accessible sans authentification"""
        return reverse('individual_public', kwargs={'unique_id': self.unique_id})

    def get_private_url(self):
        """URL privée nécessitant une authentification"""
        return reverse('individual_private', kwargs={'unique_id': self.unique_id})

    def get_qr_url(self, request):
        """Construit l'URL complète (avec domaine) à inclure dans le QR"""
        protocol = "https" if request.is_secure() else "http"
        host = request.get_host()
        return f"{protocol}://{host}{self.get_public_url()}"

    def generate_qr_code(self, request):
        """Génère le QR code avec l'URL publique complète et logo au centre"""
        from PIL import Image

        protocol = "https" if request.is_secure() else "http"
        host = request.get_host()
        qr_data = f"{protocol}://{host}{self.get_public_url()}"

        # Créer le QR code avec correction d'erreur élevée
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Changé pour supporter le logo
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Générer l'image QR
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        # Ajouter le logo (remplacez le chemin par celui de votre logo)
        logo_path = os.path.join(settings.MEDIA_ROOT, 'logo.png')
        logo = Image.open(logo_path)

        # Redimensionner le logo (1/5 de la taille du QR code)
        qr_width, qr_height = img.size
        logo_size = min(qr_width, qr_height) // 3
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Position centrale
        logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)

        # Coller le logo
        if logo.mode == 'RGBA':
            img.paste(logo, logo_pos, logo)
        else:
            img.paste(logo, logo_pos)

        # Sauvegarder
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f'qr_{self.unique_id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        buffer.close()



class AccessLog(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    accessed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Accédé par"
    )
    access_type = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Accès public'),
            ('private', 'Accès privé (agent)'),
        ],
        verbose_name="Type d'accès"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log d'accès"
        verbose_name_plural = "Logs d'accès"
        ordering = ['-accessed_at']

    def __str__(self):
        user_info = self.accessed_by.username if self.accessed_by else "Anonyme"
        return f"{self.individual.full_name} - {user_info} - {self.get_access_type_display()}"
