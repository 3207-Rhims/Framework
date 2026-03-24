from django.contrib import admin
from django.utils.html import format_html

from .models import Company, CompanyType, ExpertFeedback, Submission, TableColumn, TableRow


@admin.register(CompanyType)
class CompanyTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "company_type", "user", "created_at")
    list_filter = ("company_type",)


@admin.register(TableColumn)
class TableColumnAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "order", "source")
    list_filter = ("source",)


@admin.register(TableRow)
class TableRowAdmin(admin.ModelAdmin):
    list_display = ("company", "row_index", "created_at")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "user", "created_at", "file_link")
    list_filter = ("created_at", "company")

    def file_link(self, obj):
        if not obj.file:
            return ""
        return format_html('<a href="{}">Download</a>', obj.file.url)

    file_link.short_description = "Excel"


@admin.register(ExpertFeedback)
class ExpertFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "table_row",
        "recommended_pqc",
        "deployed_cat",
        "cat_justification",
        "feasibility",
        "migration_priority",
        "overall",
        "updated_at",
    )
