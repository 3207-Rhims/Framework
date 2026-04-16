from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("companies/", views.company_select, name="company-select"),
    path("manual/<str:language>/", views.user_manual, name="user-manual"),
    path(
        "framework-explanations/<str:language>/",
        views.full_framework_explanations,
        name="full-framework-explanations",
    ),
    path("workflow-image/<str:image_type>/", views.workflow_image, name="workflow-image"),
    path("company/<slug:company_type>/", views.company_data, name="company-data"),
    path("api/company/<slug:company_type>/columns/", views.company_columns, name="company-columns"),
    path("api/company/<slug:company_type>/rows/", views.company_rows, name="company-rows"),
    path(
        "api/company/<slug:company_type>/rows/<int:row_id>/",
        views.company_row_detail,
        name="company-row-detail",
    ),
    path(
        "api/company/<slug:company_type>/policy-engine/",
        views.policy_engine,
        name="policy-engine",
    ),
    path(
        "api/company/<slug:company_type>/profile-recommender/",
        views.profile_recommender,
        name="profile-recommender",
    ),
    path(
        "api/company/<slug:company_type>/utility-score/",
        views.utility_score,
        name="utility-score",
    ),
    path(
        "api/company/<slug:company_type>/expert-feedback/<int:row_id>/",
        views.expert_feedback,
        name="expert-feedback",
    ),
    path(
        "api/company/<slug:company_type>/submit/",
        views.submit_table,
        name="submit-table",
    ),
    path(
        "api/company/<slug:company_type>/import/",
        views.import_rows,
        name="import-rows",
    ),
    path(
        "api/company/<slug:company_type>/clear/",
        views.clear_company_data,
        name="clear-company-data",
    ),
    path(
        "api/company/<slug:company_type>/sample/",
        views.load_sample_data,
        name="load-sample-data",
    ),
]
