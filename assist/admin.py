from django.contrib import admin
from django.contrib.auth.models import User
from .models import Profile, Individual, AccessLog

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'created_at')
    list_filter = ('user_type',)
    search_fields = ('user__username', 'user__email')

# Admin de Individual (fiche médicale)
@admin.register(Individual)
class IndividualAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'gender', 'blood_type', 'qr_code', 'date_of_birth', 'is_active', 'created_by')
    search_fields = ('first_name', 'last_name', 'cnib', 'emergency_contact_name')
    list_filter = ('gender', 'blood_type', 'is_active', 'created_by')
    readonly_fields = ('unique_id', 'qr_code', 'created_at', 'updated_at', 'age', 'get_public_url', 'get_private_url')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('first_name', 'last_name', 'cnib', 'date_of_birth', 'gender', 'blood_type', 'key')
        }),
        ('Urgences et médicaments (public)', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'critical_allergies', 'current_medications')
        }),
        ('Dossier médical (privé)', {
            'fields': ('medical_conditions', 'past_surgeries', 'medical_history', 'attending_physician', 'physician_phone')
        }),
        ('Assurance & autres', {
            'fields': ('insurance_info', 'additional_emergency_contacts')
        }),
        ('QR code & système', {
            'fields': ('unique_id', 'qr_code', 'get_public_url', 'get_private_url', 'is_active', 'created_by', 'created_at', 'updated_at')
        }),
    )

    def get_public_url(self, obj):
        try:
            return obj.get_public_url()
        except:
            return "N/A"
    get_public_url.short_description = "URL publique"

    def get_private_url(self, obj):
        try:
            return obj.get_private_url()
        except:
            return "N/A"
    get_private_url.short_description = "URL privée"


# Admin pour les logs d’accès
@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('individual', 'accessed_by', 'access_type', 'ip_address', 'accessed_at')
    search_fields = ('individual__first_name', 'individual__last_name', 'accessed_by__username', 'ip_address')
    list_filter = ('access_type', 'accessed_at')
    readonly_fields = ('individual', 'accessed_by', 'access_type', 'ip_address', 'user_agent', 'accessed_at')
