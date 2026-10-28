from django.urls import path
from .views import (
    CommentDetailAPIView,
    CommentListCreateAPIView,
    CommoditiesAPIView,
    CompanyDetailAPIView,
    CompanyFinancialsAPIView,
    CompanyListAPIView,
    CompanyNewsAPIView,
    HomeOverviewAPIView,
)

urlpatterns = [
    path("overview/", HomeOverviewAPIView.as_view(), name="market-overview"),
    path("companies/", CompanyListAPIView.as_view(), name="company-list"),
    path("companies/<str:code>/", CompanyDetailAPIView.as_view(), name="company-detail"),
    path("companies/<str:code>/news/", CompanyNewsAPIView.as_view(), name="company-news"),
    path(
        "companies/<str:code>/financials/",
        CompanyFinancialsAPIView.as_view(),
        name="company-financials",
    ),
    path("commodities/", CommoditiesAPIView.as_view(), name="commodities-list"),
    path("comments/", CommentListCreateAPIView.as_view(), name="comment-list-create"),
    path("comments/<int:pk>/", CommentDetailAPIView.as_view(), name="comment-detail"),
]
