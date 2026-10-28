from django.contrib import admin
from .models import Comment, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sector", "is_bist30", "updated_at")
    search_fields = ("code", "name", "sector")
    list_filter = ("is_bist30", "sector")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "company",
        "target_type",
        "statement_type",
        "period",
        "is_edited",
        "created_at",
    )
    list_filter = ("target_type", "statement_type", "is_edited")
    search_fields = ("user__username", "company__code", "content")
