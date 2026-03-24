from django.conf import settings
from django.db import models


class CompanyType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company_type = models.ForeignKey(CompanyType, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "company_type")

    def __str__(self):
        return f"{self.name} ({self.company_type.name})"


class TableColumn(models.Model):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("policy", "Policy Engine"),
        ("profile", "Profile Recommender"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=100)
    key = models.SlugField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")

    class Meta:
        unique_together = ("company", "key")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.company.name}: {self.name}"


class TableRow(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="rows")
    row_index = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["row_index", "id"]

    def __str__(self):
        return f"Row {self.row_index} ({self.company.name})"


class Submission(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(default=dict)
    file = models.FileField(upload_to="submissions/", blank=True, null=True)

    def __str__(self):
        return f"Submission {self.id} ({self.company.name})"


class ExpertFeedback(models.Model):
    table_row = models.OneToOneField(TableRow, on_delete=models.CASCADE, related_name="expert_feedback")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recommended_pqc = models.CharField(max_length=32, blank=True, default="")
    deployed_cat = models.CharField(max_length=32, blank=True, default="")
    cat_justification = models.CharField(max_length=32, blank=True, default="")
    feasibility = models.CharField(max_length=32, blank=True, default="")
    migration_priority = models.CharField(max_length=32, blank=True, default="")
    overall = models.CharField(max_length=32, blank=True, default="")
    comments = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Expert Feedback ({self.table_row_id})"
