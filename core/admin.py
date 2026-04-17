from django.contrib import admin
from django.utils.html import format_html, format_html_join

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
    list_display = ("id", "company", "user", "created_at", "feedback_rows", "file_link")
    list_filter = ("created_at", "company")
    readonly_fields = ("feedback_preview",)

    def file_link(self, obj):
        if not obj.file:
            return ""
        return format_html('<a href="{}">Download</a>', obj.file.url)

    file_link.short_description = "Excel"

    def feedback_rows(self, obj):
        rows = obj.data.get("rows", []) if isinstance(obj.data, dict) else []
        count = 0
        for row in rows:
            if any(
                value
                for key, value in row.items()
                if key.startswith("Expert Feedback") or key == "Expert Comments"
            ):
                count += 1
        return count

    feedback_rows.short_description = "Rows with feedback"

    def feedback_preview(self, obj):
        rows = obj.data.get("rows", []) if isinstance(obj.data, dict) else []
        preview_rows = []
        for row in rows:
            feedback = {
                key: value
                for key, value in row.items()
                if (key.startswith("Expert Feedback") or key == "Expert Comments") and value
            }
            if not feedback:
                continue
            row_label = row.get("ID") or row.get("row_index") or row.get("#") or "Row"
            feedback_html = format_html_join(
                "<br>",
                "<strong>{}</strong>: {}",
                feedback.items(),
            )
            preview_rows.append((row_label, feedback_html))

        if not preview_rows:
            return "No expert feedback was included in this submission."

        return format_html_join("", "<p><strong>{}</strong><br>{}</p>", preview_rows)

    feedback_preview.short_description = "Expert feedback snapshot"


@admin.register(ExpertFeedback)
class ExpertFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "table_row",
        "company",
        "recommended_pqc",
        "deployed_cat",
        "cat_justification",
        "feasibility",
        "migration_priority",
        "overall",
        "updated_at",
    )
    list_filter = ("table_row__company", "updated_at")
    search_fields = ("table_row__company__name", "comments")

    def company(self, obj):
        return obj.table_row.company
