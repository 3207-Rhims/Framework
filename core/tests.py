import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Company, CompanyType, ExpertFeedback, Submission, TableColumn, TableRow

from .algorithms import get_default_weight_config, resolve_weight_config


class WeightConfigTests(SimpleTestCase):
    def test_defaults_are_returned_when_no_payload_is_provided(self):
        defaults = get_default_weight_config()
        resolved = resolve_weight_config()
        self.assertEqual(resolved, defaults)
        self.assertIsNot(resolved, defaults)

    def test_missing_values_fall_back_to_defaults_and_group_is_normalized(self):
        resolved = resolve_weight_config(
            {
                "server_utility": {
                    "cpu": "7",
                    "bytes": "",
                }
            }
        )

        expected_cpu = 7 / 7.3
        expected_bytes = 0.3 / 7.3
        self.assertAlmostEqual(resolved["server_utility"]["cpu"], expected_cpu)
        self.assertAlmostEqual(resolved["server_utility"]["bytes"], expected_bytes)

    def test_zero_sum_group_falls_back_to_defaults(self):
        defaults = get_default_weight_config()
        resolved = resolve_weight_config(
            {
                "migration_score": {
                    "risk": 0,
                    "feasibility": 0,
                    "complexity": 0,
                }
            }
        )
        self.assertEqual(resolved["migration_score"], defaults["migration_score"])

    def test_non_numeric_weights_raise_error(self):
        with self.assertRaisesMessage(ValueError, "must be numeric"):
            resolve_weight_config({"server_utility": {"cpu": "abc"}})

    def test_negative_weights_raise_error(self):
        with self.assertRaisesMessage(ValueError, "cannot be negative"):
            resolve_weight_config({"device_utility": {"ram": -1}})


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ExpertFeedbackSubmissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="feedback-user",
            password="strong-pass-123",
        )
        self.client.force_login(self.user)
        self.company_type = CompanyType.objects.create(name="Retail", slug="retail")
        self.company = Company.objects.create(
            user=self.user,
            company_type=self.company_type,
            name="Retail Company",
        )
        TableColumn.objects.create(company=self.company, name="ID", key="id", order=1)
        self.row = TableRow.objects.create(
            company=self.company,
            row_index=1,
            data={"id": "C1"},
        )

    def test_submit_table_includes_why_text_and_comments(self):
        feedback_payload = {
            "recommended_pqc": "Partially appropriate",
            "recommended_pqc_why": "The selected algorithm needs more deployment evidence.",
            "deployed_cat": "Not appropriate",
            "deployed_cat_why": "The deployed category is too weak for this conduit.",
            "comments": "Please review the category choice before rollout.",
        }

        response = self.client.post(
            reverse("expert-feedback", args=[self.company_type.slug, self.row.id]),
            data=json.dumps(feedback_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("submit-table", args=[self.company_type.slug]),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        submission = Submission.objects.latest("id")
        submitted_row = submission.data["rows"][0]
        self.assertEqual(
            submitted_row["Expert Feedback: Recommended PQC Why"],
            feedback_payload["recommended_pqc_why"],
        )
        self.assertEqual(
            submitted_row["Expert Feedback: Deployed CAT Why"],
            feedback_payload["deployed_cat_why"],
        )
        self.assertEqual(
            submitted_row["Expert Feedback: Comments"],
            feedback_payload["comments"],
        )

    def test_submit_table_falls_back_to_feedback_columns_in_row_data(self):
        self.row.data.update(
            {
                "expert_feedback_recommended_pqc_why": "",
            }
        )
        self.row.save(update_fields=["data"])

        TableColumn.objects.create(
            company=self.company,
            name="Expert Feedback: Overall Why",
            key="expert_feedback_overall_why",
            order=2,
        )
        TableColumn.objects.create(
            company=self.company,
            name="Expert Feedback: Comments",
            key="expert_feedback_comments",
            order=3,
        )
        self.row.data.update(
            {
                "expert_feedback_overall_why": "Operational constraints need more justification.",
                "expert_feedback_comments": "Imported reviewer notes.",
            }
        )
        self.row.save(update_fields=["data"])

        response = self.client.post(
            reverse("submit-table", args=[self.company_type.slug]),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        submission = Submission.objects.latest("id")
        submitted_row = submission.data["rows"][0]
        self.assertEqual(
            submitted_row["Expert Feedback: Overall Why"],
            "Operational constraints need more justification.",
        )
        self.assertEqual(
            submitted_row["Expert Feedback: Comments"],
            "Imported reviewer notes.",
        )

    def test_overall_question_uses_likert_scale_and_is_saved(self):
        response = self.client.post(
            reverse("expert-feedback", args=[self.company_type.slug, self.row.id]),
            data=json.dumps(
                {
                    "recommended_pqc": "Appropriate",
                    "deployed_cat": "Appropriate",
                    "feasibility": "Appropriate",
                    "migration_priority": "Appropriate",
                    "overall": "Strongly agree",
                    "comments": "High confidence overall.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        feedback = ExpertFeedback.objects.get(table_row=self.row)
        self.assertEqual(feedback.overall, "Strongly agree")
        self.assertEqual(feedback.overall_why, "")

    def test_legacy_overall_value_is_mapped_when_modal_data_is_loaded(self):
        ExpertFeedback.objects.create(
            table_row=self.row,
            overall="Appropriate",
        )

        response = self.client.get(
            reverse("expert-feedback", args=[self.company_type.slug, self.row.id]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["feedback"]["overall"], "Agree")
