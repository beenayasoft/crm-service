from django.contrib import admin
from .models import Opportunity

@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'stage', 'estimated_amount', 'probability', 'expected_close_date', 'created_at')
    list_filter = ('stage', 'source', 'created_at')
    search_fields = ('name', 'description', 'tier__nom')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'closed_at')
    fieldsets = (
        ('Informations principales', {
            'fields': ('name', 'tier', 'stage', 'estimated_amount', 'probability', 'expected_close_date')
        }),
        ('Détails', {
            'fields': ('source', 'description', 'assigned_to')
        }),
        ('Opportunité gagnée', {
            'fields': ('project_id',),
            'classes': ('collapse',),
        }),
        ('Opportunité perdue', {
            'fields': ('loss_reason', 'loss_description'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',),
        }),
    )
