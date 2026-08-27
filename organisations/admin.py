from django.contrib import admin
from .models import Organisation, OrganisationMembership


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    readonly_fields = ("slug",)


@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "role")