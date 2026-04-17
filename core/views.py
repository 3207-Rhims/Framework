import csv
import io
import json
import math
from pathlib import Path
from typing import List

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import models
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .models import Company, CompanyType, ExpertFeedback, Submission, TableColumn, TableRow
from .algorithms import (
    compute_possible_deployed_cat,
    compute_utility_scores,
    get_default_weight_config,
    get_weight_form_config,
    resolve_weight_config,
)

EXPERT_FEEDBACK_CHOICES = {
    "recommended_pqc": "recommended_pqc",
    "deployed_cat": "deployed_cat",
    "cat_justification": "cat_justification",
    "feasibility": "feasibility",
    "migration_priority": "migration_priority",
    "overall": "overall",
    "comments": "comments",
}

COMPANY_TYPES = [
    {"name": "Retail", "slug": "retail"},
    {"name": "Manufacturing", "slug": "manufacturing"},
    {"name": "Technology", "slug": "technology"},
    {"name": "Corporate", "slug": "corporate"},
    {"name": "Consulting", "slug": "consulting"},
    {"name": "Services", "slug": "services"},
]

DEFAULT_COLUMNS = [
    {"name": "Column A", "key": "col_a"},
    {"name": "Column B", "key": "col_b"},
    {"name": "Column C", "key": "col_c"},
    {"name": "Column D", "key": "col_d"},
    {"name": "Column E", "key": "col_e"},
    {"name": "Column F", "key": "col_f"},
    {"name": "Column G", "key": "col_g"},
    {"name": "Column H", "key": "col_h"},
]

FEEDBACK_EXPORT_LABELS = [
    ("recommended_pqc", "Expert Feedback: Recommended PQC"),
    ("deployed_cat", "Expert Feedback: Deployed CAT"),
    ("cat_justification", "Expert Feedback: CAT Justification"),
    ("feasibility", "Expert Feedback: Feasibility"),
    ("migration_priority", "Expert Feedback: Migration Priority"),
    ("overall", "Expert Feedback: Overall"),
    ("comments", "Expert Feedback: Comments"),
]

FEEDBACK_COLUMN_ALIASES = {
    "recommended_pqc": [
        "Expert Feedback: Recommended PQC",
        "Expert Feedback (Recommended PQC)",
        "Expert Feedback (Algorithm Selection)",
    ],
    "deployed_cat": [
        "Expert Feedback: Deployed CAT",
        "Expert Feedback (Deployed CAT)",
    ],
    "cat_justification": [
        "Expert Feedback: CAT Justification",
        "Expert Feedback (CAT Justification)",
    ],
    "feasibility": [
        "Expert Feedback: Feasibility",
        "Expert Feedback (Feasibility)",
    ],
    "migration_priority": [
        "Expert Feedback: Migration Priority",
        "Expert Feedback (Migration Priority)",
    ],
    "overall": [
        "Expert Feedback: Overall",
        "Expert Feedback (Overall)",
    ],
    "comments": [
        "Expert Feedback: Comments",
        "Expert Feedback (Comments)",
        "Expert Comments",
    ],
}

USER_MANUAL_FILES = {
    "en": "User_manual_en.pdf",
    "jp": "User_manual_jp.pdf",
}

FULL_FRAMEWORK_EXPLANATION_FILES = {
    "en": "Full_Framework_Explanations_en.pdf",
    "jp": "Full_Framework_Explanations_jp.pdf",
}

WORKFLOW_IMAGE_FILES = {
    "policy": "policy_engine.png",
    "profile": "profile recommender.png",
}


def seed_company_types():
    for entry in COMPANY_TYPES:
        CompanyType.objects.get_or_create(slug=entry["slug"], defaults={"name": entry["name"]})


def get_company_type(slug):
    seed_company_types()
    return get_object_or_404(CompanyType, slug=slug)


def ensure_company(user, company_type):
    company, _ = Company.objects.get_or_create(
        user=user,
        company_type=company_type,
        defaults={"name": f"{company_type.name} Company"},
    )
    return company


def ensure_default_columns(company):
    if company.columns.exists():
        return
    for index, column in enumerate(DEFAULT_COLUMNS):
        TableColumn.objects.create(
            company=company,
            name=column["name"],
            key=column["key"],
            order=index,
        )


def ensure_default_rows(company, count=8):
    if company.rows.exists():
        return
    columns = list(company.columns.all())
    for idx in range(count):
        data = {column.key: "" for column in columns}
        TableRow.objects.create(company=company, row_index=idx + 1, data=data)


def company_to_dataframe(company):
    columns = list(company.columns.all())
    rows = list(company.rows.all())
    data = []
    for row in rows:
        record = {column.name: row.data.get(column.key, "") for column in columns}
        data.append(record)
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required for running algorithms.") from exc
    return pd.DataFrame(data)


def replace_company_data(company, headers, rows):
    company.rows.all().delete()
    company.columns.all().delete()

    created_columns = []
    for index, header in enumerate(headers):
        clean_header = header.strip() if header else f"Column {index + 1}"
        key = slugify(clean_header) or f"col_{index + 1}"
        column = TableColumn.objects.create(
            company=company,
            name=clean_header,
            key=key,
            order=index + 1,
            source="manual",
        )
        created_columns.append(column)

    columns = list(company.columns.all())
    created_rows = []
    for row_index, row_values in enumerate(rows, start=1):
        data = {column.key: "" for column in columns}
        for column, value in zip(created_columns, row_values):
            data[column.key] = value
        row = TableRow.objects.create(
            company=company,
            row_index=row_index,
            data=data,
        )
        created_rows.append(serialize_row(row, company))

    return created_rows


def ensure_columns(company, column_names: List[str]):
    created = []
    current = {col.name: col for col in company.columns.all()}
    base_order = company.columns.aggregate(models.Max("order")).get("order__max") or 0
    for idx, name in enumerate(column_names, start=1):
        if name in current:
            continue
        key = slugify(name) or f"col_{base_order + idx}"
        column = TableColumn.objects.create(
            company=company,
            name=name,
            key=key,
            order=base_order + idx,
            source="manual",
        )
        created.append(column)
    return created


def update_rows_from_dataframe(company, df, column_names: List[str]):
    columns = {col.name: col for col in company.columns.all()}
    rows = list(company.rows.all())
    records = df.to_dict(orient="records")
    for row_obj, record in zip(rows, records):
        for name in column_names:
            column = columns.get(name)
            if not column:
                continue
            row_obj.data[column.key] = _clean_json_value(record.get(name, ""))
        row_obj.save(update_fields=["data"])


def _value_from_row_aliases(row, columns_by_name, aliases):
    for alias in aliases:
        column = columns_by_name.get(alias)
        if not column:
            continue
        value = _clean_json_value(row.data.get(column.key, ""))
        if value not in ("", None):
            return str(value)
    return ""


def sync_expert_feedback_from_table(company, rows=None, columns=None):
    rows = list(rows if rows is not None else company.rows.all())
    columns = list(columns if columns is not None else company.columns.all())
    columns_by_name = {column.name: column for column in columns}

    synced_count = 0
    for row in rows:
        feedback_values = {
            field: _value_from_row_aliases(row, columns_by_name, aliases)
            for field, aliases in FEEDBACK_COLUMN_ALIASES.items()
        }
        if not any(feedback_values.values()):
            continue

        feedback, _ = ExpertFeedback.objects.get_or_create(table_row=row)
        changed = False
        for field, value in feedback_values.items():
            if value and getattr(feedback, field) != value:
                setattr(feedback, field, value)
                changed = True
        if changed:
            feedback.save()
        synced_count += 1

    return synced_count




def _clean_json_value(value):
    if value is None:
        return ""
    try:
        import numpy as np  # type: ignore
        if isinstance(value, np.generic):
            value = value.item()
    except Exception:
        pass
    try:
        import pandas as pd  # type: ignore
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, (list, tuple)):
        return [_clean_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _clean_json_value(v) for k, v in value.items()}
    return value


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _resolve_request_weights(payload):
    mode = "custom" if payload.get("weight_mode") == "custom" else "default"
    raw_weights = payload.get("weights") if mode == "custom" else None
    weights = resolve_weight_config(raw_weights)
    return mode, weights


def _localized_weight_form_config(language_code):
    config = get_weight_form_config()
    if not str(language_code).startswith("ja"):
        return config

    translations = {
        "server_utility": {
            "label": "サーバー向けユーティリティ重み",
            "description": "サーバーまたはゲートウェイの暗号化・認証ランキングに使われます。",
            "fields": {
                "cpu": "CPU / レイテンシ",
                "bytes": "バイト数",
            },
        },
        "device_utility": {
            "label": "組み込み / 制約端末ユーティリティ重み",
            "description": "組み込み、MCU、制約デバイスのランキングに使われます。",
            "fields": {
                "cpu": "CPU / サイクル",
                "bytes": "バイト数",
                "ram": "RAM",
            },
        },
        "migration_risk": {
            "label": "移行リスク重み",
            "description": "Exposure、Impact、Lifetime から作るリスクスコアに使われます。",
            "fields": {
                "exposure": "Exposure",
                "impact": "Impact",
                "lifetime": "Lifetime",
            },
        },
        "migration_feasibility": {
            "label": "移行実現性重み",
            "description": "Firmware、Crypto、Vendor readiness から作る実現性スコアに使われます。",
            "fields": {
                "firmware": "Firmware",
                "crypto": "Crypto",
                "vendor": "Vendor",
            },
        },
        "migration_complexity": {
            "label": "移行複雑性重み",
            "description": "Placement、Purdue layer、Device type から作る複雑性スコアに使われます。",
            "fields": {
                "placement": "Placement",
                "purdue": "Purdue",
                "device": "Device",
            },
        },
        "migration_score": {
            "label": "移行最終スコア重み",
            "description": "Risk、Feasibility、Complexity を混ぜる最終スコアに使われます。",
            "fields": {
                "risk": "Risk",
                "feasibility": "Feasibility",
                "complexity": "Complexity",
            },
        },
    }

    for group in config:
        translated = translations.get(group["key"])
        if not translated:
            continue
        group["label"] = translated["label"]
        group["description"] = translated["description"]
        for field in group["fields"]:
            field["label"] = translated["fields"].get(field["key"], field["label"])

    return config


def home(request):
    return render(request, "home.html")


def logout_view(request):
    logout(request)
    return redirect("home")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("company-select")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def company_select(request):
    seed_company_types()
    return render(request, "company_select.html", {"company_types": COMPANY_TYPES})


@login_required
def company_data(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)
    ensure_default_rows(company)
    return render(
        request,
        "company_data.html",
        {
            "company_type": company_type_obj,
            "company": company,
            "default_weight_config": get_default_weight_config(),
            "weight_form_config": _localized_weight_form_config(getattr(request, "LANGUAGE_CODE", "")),
        },
    )


@login_required
def user_manual(request, language):
    filename = USER_MANUAL_FILES.get(language)
    if not filename:
        raise Http404("Manual not found.")

    manual_path = Path(__file__).resolve().parents[1] / "Algoritthm implementation" / "data" / filename
    if not manual_path.exists():
        raise Http404("Manual file is missing.")

    return FileResponse(manual_path.open("rb"), content_type="application/pdf")


@login_required
def full_framework_explanations(request, language):
    filename = FULL_FRAMEWORK_EXPLANATION_FILES.get(language)
    if not filename:
        raise Http404("Explanation file not found.")

    file_path = Path(__file__).resolve().parents[1] / "Algoritthm implementation" / "data" / filename
    if not file_path.exists():
        raise Http404("Explanation PDF is missing.")

    return FileResponse(file_path.open("rb"), content_type="application/pdf")


@login_required
def workflow_image(request, image_type):
    filename = WORKFLOW_IMAGE_FILES.get(image_type)
    if not filename:
        raise Http404("Workflow image not found.")

    image_path = Path(__file__).resolve().parents[1] / "Algoritthm implementation" / "data" / filename
    if not image_path.exists():
        raise Http404("Workflow image is missing.")

    return FileResponse(image_path.open("rb"), content_type="image/png")


@login_required
def company_columns(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)
    columns = [
        {"title": "#", "field": "row_index", "width": 70, "hozAlign": "center"}
    ]
    hidden_keys = {
        "expert_feedback_cat",
        "expert_feedback_algo",
        "expert_feedback_migration",
        "expert_comments",
    }
    for column in company.columns.all():
        if column.key in hidden_keys:
            continue
        col_def = {
            "title": column.name,
            "field": column.key,
            "editor": "textarea",
            "formatter": "textarea",
        }
        columns.append(col_def)
    return JsonResponse({"columns": columns})


@login_required
@require_http_methods(["GET", "POST"])
def company_rows(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)

    if request.method == "POST":
        payload = json.loads(request.body or "{}")
        row_index = payload.get("row_index") or (company.rows.count() + 1)
        data = payload.get("data") or {}
        row = TableRow.objects.create(company=company, row_index=row_index, data=data)
        return JsonResponse({"row": serialize_row(row, company)})

    ensure_default_rows(company)
    rows = [serialize_row(row, company) for row in company.rows.all()]
    return JsonResponse({"rows": rows})


@login_required
@require_http_methods(["PATCH", "DELETE"])
def company_row_detail(request, company_type, row_id):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    row = get_object_or_404(TableRow, company=company, id=row_id)

    if request.method == "DELETE":
        row.delete()
        return JsonResponse({"status": "deleted"})

    payload = json.loads(request.body or "{}")
    data_updates = payload.get("data", {})
    row.data.update(data_updates)
    row.save(update_fields=["data"])
    return JsonResponse({"row": serialize_row(row, company)})


@login_required
@require_http_methods(["POST"])
def policy_engine(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)
    ensure_default_rows(company)
    try:
        df = company_to_dataframe(company)
        df = compute_possible_deployed_cat(df)
    except (ValueError, ImportError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    ensure_columns(company, ["Possible Deployed CAT"])
    update_rows_from_dataframe(company, df, ["Possible Deployed CAT"])
    return JsonResponse({"status": "ok"})


@login_required
@require_http_methods(["POST"])
def profile_recommender(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)
    ensure_default_rows(company)
    payload = _parse_json_body(request)
    try:
        weight_mode, weights = _resolve_request_weights(payload)
        df = company_to_dataframe(company)
        df = compute_utility_scores(df, weights)
    except (ValueError, ImportError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    new_cols = [
        "Enc_Ranking_By_Utility",
        "Enc_Best_Alg",
        "Enc_Best_Utility",
        "Auth_Ranking_By_Utility",
        "Auth_Best_Alg",
        "Auth_Best_Utility",
        "Enc_Confidence_Top3",
        "Auth_Confidence_Top3",
        "Migration_Priority",
    ]
    ensure_columns(company, new_cols)
    update_rows_from_dataframe(company, df, new_cols)
    return JsonResponse({"status": "ok", "used_weights": weights, "weight_mode": weight_mode})


@login_required
@require_http_methods(["POST"])
def utility_score(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)
    ensure_default_rows(company)
    payload = _parse_json_body(request)
    try:
        weight_mode, weights = _resolve_request_weights(payload)
        df = company_to_dataframe(company)
        df = compute_utility_scores(df, weights)
    except (ValueError, ImportError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    new_cols = [
        "Enc_Ranking_By_Utility",
        "Enc_Best_Alg",
        "Enc_Best_Utility",
        "Auth_Ranking_By_Utility",
        "Auth_Best_Alg",
        "Auth_Best_Utility",
        "Enc_Confidence_Top3",
        "Auth_Confidence_Top3",
        "Migration_Priority",
    ]
    ensure_columns(company, new_cols)
    update_rows_from_dataframe(company, df, new_cols)
    return JsonResponse({"status": "ok", "used_weights": weights, "weight_mode": weight_mode})


@login_required
@require_http_methods(["GET", "POST"])
def expert_feedback(request, company_type, row_id):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    row = get_object_or_404(TableRow, company=company, id=row_id)

    if request.method == "GET":
        feedback = ExpertFeedback.objects.filter(table_row=row).first()
        data = {
            "recommended_pqc": feedback.recommended_pqc if feedback else "",
            "deployed_cat": feedback.deployed_cat if feedback else "",
            "cat_justification": feedback.cat_justification if feedback else "",
            "feasibility": feedback.feasibility if feedback else "",
            "migration_priority": feedback.migration_priority if feedback else "",
            "overall": feedback.overall if feedback else "",
            "comments": feedback.comments if feedback else "",
        }
        return JsonResponse({"feedback": data})

    payload = json.loads(request.body or "{}")
    feedback, _ = ExpertFeedback.objects.get_or_create(table_row=row)
    feedback.recommended_pqc = payload.get("recommended_pqc", "")
    feedback.deployed_cat = payload.get("deployed_cat", "")
    feedback.cat_justification = payload.get("cat_justification", "")
    feedback.feasibility = payload.get("feasibility", "")
    feedback.migration_priority = payload.get("migration_priority", "")
    feedback.overall = payload.get("overall", "")
    feedback.comments = payload.get("comments", "")
    feedback.save()
    return JsonResponse({"status": "saved"})


@login_required
@require_http_methods(["POST"])
def import_rows(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    ensure_default_columns(company)

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "No file uploaded."}, status=400)

    filename = upload.name.lower()
    if filename.endswith(".csv"):
        parsed = parse_csv(upload)
    elif filename.endswith(".xlsx"):
        parsed = parse_xlsx(upload)
    else:
        return JsonResponse({"error": "Unsupported file type. Use CSV or XLSX."}, status=400)

    if parsed is None:
        return JsonResponse(
            {"error": "XLSX import requires openpyxl. Install it and try again."},
            status=400,
        )

    headers = parsed["headers"]
    rows = parsed["rows"]

    created_rows = replace_company_data(company, headers, rows)
    return JsonResponse({"rows": created_rows})


@login_required
@require_http_methods(["POST"])
def clear_company_data(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)
    company.rows.all().delete()
    company.columns.all().delete()
    return JsonResponse({"status": "cleared"})


@login_required
@require_http_methods(["POST"])
def load_sample_data(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)

    base_dir = Path(__file__).resolve().parents[1] / "Algoritthm implementation" / "data"
    sample_csv = base_dir / "Smart Grid - Sheet1 (4).csv"
    sample_xlsx = base_dir / "Smart Grid.xlsx"

    if sample_csv.exists():
        with sample_csv.open("r", encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
        if not rows:
            return JsonResponse({"error": "Sample dataset is empty."}, status=400)
        headers = [str(cell).strip() for cell in rows[0]]
        data_rows = rows[1:]
    elif sample_xlsx.exists():
        parsed = parse_xlsx(sample_xlsx)
        if parsed is None:
            return JsonResponse(
                {"error": "XLSX import requires openpyxl. Install it and try again."},
                status=400,
            )
        headers = parsed["headers"]
        data_rows = parsed["rows"]
    else:
        return JsonResponse({"error": "Sample dataset not found."}, status=404)

    replace_company_data(company, headers, data_rows)
    return JsonResponse({"status": "loaded"})


@login_required
@require_http_methods(["POST"])
def submit_table(request, company_type):
    company_type_obj = get_company_type(company_type)
    company = ensure_company(request.user, company_type_obj)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    rows_payload = payload.get("rows") if isinstance(payload, dict) else None

    if rows_payload:
        columns_by_key = {col.key: col for col in company.columns.all()}
        for row_entry in rows_payload:
            row_id = row_entry.get("row_id") or row_entry.get("id")
            if not row_id:
                continue
            row_obj = TableRow.objects.filter(company=company, id=row_id).first()
            if not row_obj:
                continue
            updated = False
            for key, value in row_entry.items():
                if key in ("id", "row_index", "_delete"):
                    continue
                if key in columns_by_key:
                    row_obj.data[key] = _clean_json_value(value)
                    updated = True
            if updated:
                row_obj.save(update_fields=["data"])

    columns = list(company.columns.all())
    rows = list(company.rows.all())
    sync_expert_feedback_from_table(company, rows=rows, columns=columns)

    feedback_map = {
        fb.table_row_id: fb
        for fb in ExpertFeedback.objects.filter(table_row__company=company)
    }

    payload_rows = []
    for row in rows:
        record = {}
        for column in columns:
            record[column.name] = _clean_json_value(row.data.get(column.key, ""))
        feedback = feedback_map.get(row.id)
        for key, label in FEEDBACK_EXPORT_LABELS:
            value = getattr(feedback, key, "") if feedback else ""
            record[label] = _clean_json_value(value)
        payload_rows.append(record)

    submission = Submission.objects.create(
        company=company,
        user=request.user,
        data={
            "columns": [column.name for column in columns]
            + [label for _, label in FEEDBACK_EXPORT_LABELS],
            "rows": payload_rows,
        },
    )

    try:
        import pandas as pd  # type: ignore
        from django.core.files.base import ContentFile
        output = io.BytesIO()
        df = pd.DataFrame(payload_rows)
        df.to_excel(output, index=False)
        output.seek(0)
        submission.file.save(
            f"submission_{submission.id}.xlsx",
            ContentFile(output.read()),
            save=True,
        )
    except Exception:
        # If pandas/openpyxl is missing, keep JSON only.
        pass

    return JsonResponse({"status": "submitted", "submission_id": submission.id})


def parse_csv(upload):
    decoded = upload.read().decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        return {"headers": [], "rows": []}
    headers = [str(cell).strip() for cell in rows[0]]
    values = [row for row in rows[1:]]
    return {"headers": headers, "rows": values}


def parse_xlsx(upload):
    try:
        import openpyxl
    except ImportError:
        return None

    workbook = openpyxl.load_workbook(upload, data_only=True)
    sheet = workbook.active
    headers = []
    rows = []
    for idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if idx == 1:
            headers = [str(cell).strip() if cell is not None else "" for cell in row]
            continue
        values = [cell if cell is not None else "" for cell in row]
        rows.append(values)
    return {"headers": headers, "rows": rows}


def add_generated_columns(company, prefix, source, count):
    last_order = company.columns.aggregate(models.Max("order")).get("order__max")
    if last_order is None:
        last_order = 0
    created = []
    for idx in range(1, count + 1):
        name = f"{prefix} {last_order + idx}"
        key = slugify(name)
        column, created_flag = TableColumn.objects.get_or_create(
            company=company,
            key=key,
            defaults={
                "name": name,
                "order": last_order + idx,
                "source": source,
            },
        )
        if created_flag:
            created.append(
                {
                    "title": column.name,
                    "field": column.key,
                    "editor": "textarea",
                    "formatter": "textarea",
                }
            )
            for row in company.rows.all():
                row.data[column.key] = ""
                row.save(update_fields=["data"])
    return created


def serialize_row(row, company):
    data = {"row_id": row.id, "row_index": row.row_index}
    for column in company.columns.all():
        data[column.key] = row.data.get(column.key, "")
    return data
