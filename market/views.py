"""
API Views for Tasonaliz Market, Companies, Financial Statements, Analysis, News,
Commodities, and User Comments.
"""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Comment, Company
from .permissions import IsAuthorOrReadOnly
from .providers.bist_directory_provider import sync_all_bist_companies
from .providers.commodities_provider import get_precious_metals_and_commodities
from .providers.financial_analysis_engine import generate_financial_analysis
from .providers.kap_financial_provider import get_company_financial_statements
from .providers.news_provider import get_company_news
from .providers.stock_price_provider import (
    get_featured_market_summary,
    get_stock_quote_and_history,
)
from .serializers import CommentSerializer, CompanyListSerializer


def ensure_companies_populated():
    if Company.objects.count() < 50:
        sync_all_bist_companies(force=False)


class HomeOverviewAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        ensure_companies_populated()

        total_companies = Company.objects.count()
        bist30_count = Company.objects.filter(is_bist30=True).count()
        sectors = list(
            Company.objects.exclude(sector="")
            .values_list("sector", flat=True)
            .distinct()
            .order_by("sector")
        )

        market_summary = get_featured_market_summary()
        # Enrich featured quotes with company names from DB
        featured_codes = [q["code"] for q in market_summary.get("featured_quotes", [])]
        name_map = dict(
            Company.objects.filter(code__in=featured_codes).values_list("code", "name")
        )
        for q in market_summary.get("featured_quotes", []):
            q["name"] = name_map.get(q["code"], q["code"])

        commodities_data = get_precious_metals_and_commodities()
        recent_comments = Comment.objects.select_related("user", "company").all()[:6]

        return Response(
            {
                "bist_stats": {
                    "total_companies": total_companies,
                    "bist30_count": bist30_count,
                    "sector_count": len(sectors),
                },
                "market_summary": market_summary,
                "commodities_preview": {
                    "fx_reference": commodities_data.get("fx_reference"),
                    "assets": commodities_data.get("assets", [])[:6],
                    "last_updated": commodities_data.get("last_updated"),
                    "source_name": commodities_data.get("source_name"),
                },
                "recent_comments": CommentSerializer(
                    recent_comments, many=True, context={"request": request}
                ).data,
            }
        )


class CompanyListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        ensure_companies_populated()

        query = request.query_params.get("q", "").strip()
        sector = request.query_params.get("sector", "").strip()
        bist30_only = request.query_params.get("bist30", "").lower() in ("true", "1")

        qs = Company.objects.annotate(comment_count=Count("comments"))

        if query:
            qs = qs.filter(
                Q(code__icontains=query) | Q(name__icontains=query)
            )
        if sector:
            qs = qs.filter(sector__iexact=sector)
        if bist30_only:
            qs = qs.filter(is_bist30=True)

        qs = qs.order_by("-is_bist30", "code")

        sectors = list(
            Company.objects.exclude(sector="")
            .values_list("sector", flat=True)
            .distinct()
            .order_by("sector")
        )

        total_matched = qs.count()
        # Allow returning all BIST companies cleanly
        companies_data = CompanyListSerializer(qs, many=True).data

        return Response(
            {
                "count": total_matched,
                "total_bist_count": Company.objects.count(),
                "sectors": sectors,
                "source_name": "Kamuyu Aydınlatma Platformu (KAP - BIST Şirketler Dizini)",
                "source_url": "https://www.kap.org.tr/tr/bist-sirketler",
                "results": companies_data,
            }
        )


class CompanyDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, code: str):
        ensure_companies_populated()
        clean_code = code.strip().upper()
        company = get_object_or_404(
            Company.objects.annotate(comment_count=Count("comments")),
            code__iexact=clean_code,
        )
        period = request.query_params.get("period", "6mo").strip()
        if period not in ("1mo", "3mo", "6mo", "1y", "2y"):
            period = "6mo"

        stock_data = get_stock_quote_and_history(company.code, period=period)

        return Response(
            {
                "company": CompanyListSerializer(company).data,
                "market_data": stock_data,
            }
        )


class CompanyNewsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, code: str):
        ensure_companies_populated()
        clean_code = code.strip().upper()
        company = get_object_or_404(Company, code__iexact=clean_code)
        news_data = get_company_news(
            code=company.code,
            company_name=company.name,
            kap_url=company.kap_url,
        )
        return Response(news_data)


class CompanyFinancialsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, code: str):
        ensure_companies_populated()
        clean_code = code.strip().upper()
        company = get_object_or_404(Company, code__iexact=clean_code)

        financials = get_company_financial_statements(
            code=company.code,
            kap_url=company.kap_url,
        )
        analysis = generate_financial_analysis(financials)

        return Response(
            {
                "company": CompanyListSerializer(company).data,
                "financials": financials,
                "analysis": analysis,
            }
        )


class CommoditiesAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = get_precious_metals_and_commodities()
        return Response(data)


class CommentListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.select_related("user", "company").all()
        company_code = self.request.query_params.get("company", "").strip().upper()
        target_type = self.request.query_params.get("target_type", "").strip().upper()
        statement_type = self.request.query_params.get("statement_type", "").strip().upper()
        period = self.request.query_params.get("period", "").strip()

        if company_code:
            qs = qs.filter(company__code__iexact=company_code)
        if target_type in ("COMPANY", "FINANCIAL_TABLE"):
            qs = qs.filter(target_type=target_type)
        if statement_type in ("BILANCO", "GELIR", "NAKIT"):
            qs = qs.filter(statement_type=statement_type)
        if period:
            qs = qs.filter(period=period)

        return qs[:100]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CommentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.select_related("user", "company").all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
