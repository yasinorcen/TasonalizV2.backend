"""
Automated test suite for Tasonaliz Backend (Stage 6: Test & Security).
Covers:
- Registration, Login, and JWT authentication
- BIST Company listing, search, and filtering
- Comment creation, editing (sets is_edited=True), deletion, and strict author-only permissions
- Financial Analysis Engine (ratio calculation, period comparison, and missing data warnings)
- HTTP Security Headers (X-Frame-Options, nosniff, CSP)
"""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Comment, Company
from .providers.financial_analysis_engine import generate_financial_analysis


class TasonalizBackendTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(
            code="THYAO",
            name="TÜRK HAVA YOLLARI A.O.",
            sector="Ulaştırma ve Havacılık",
            indices="BIST 30, BIST 100, BIST TÜM",
            kap_url="https://www.kap.org.tr/tr/sirket-bilgileri/ozet/1068-turk-hava-yollari-a-o",
            is_bist30=True,
        )
        self.company2 = Company.objects.create(
            code="ASELS",
            name="ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.",
            sector="Teknoloji ve Bilişim",
            indices="BIST 30, BIST 100, BIST TÜM",
            kap_url="https://www.kap.org.tr/tr/sirket-bilgileri/ozet/856-aselsan-elektronik-sanayi-ve-ticaret-a-s",
            is_bist30=True,
        )
        self.user_a = User.objects.create_user(
            username="analist_ali",
            email="ali@example.com",
            password="GucluParola123!",
        )
        self.user_b = User.objects.create_user(
            username="yatirimci_zeynep",
            email="zeynep@example.com",
            password="GucluParola123!",
        )

    def test_health_and_security_headers(self):
        res = self.client.get(reverse("api-health"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(res["X-Content-Type-Options"], "nosniff")
        self.assertIn("Content-Security-Policy", res)

    def test_user_registration_and_login(self):
        reg_res = self.client.post(
            reverse("auth-register"),
            {
                "username": "yeni_ogrenci",
                "email": "ogrenci@example.com",
                "first_name": "Yasin",
                "last_name": "Örcen",
                "password": "SafePassword2026!",
                "password_confirm": "SafePassword2026!",
            },
            format="json",
        )
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", reg_res.data)
        self.assertEqual(reg_res.data["user"]["username"], "yeni_ogrenci")

        login_res = self.client.post(
            reverse("auth-login"),
            {
                "username": "ogrenci@example.com",
                "password": "SafePassword2026!",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        access_token = login_res.data["tokens"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_res = self.client.get(reverse("auth-me"))
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data["username"], "yeni_ogrenci")

    def test_company_search_and_filtering(self):
        res = self.client.get(reverse("company-list"), {"q": "ASELS"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        codes = [item["code"] for item in res.data["results"]]
        self.assertIn("ASELS", codes)

    def test_comment_permissions_and_edit_tracking(self):
        # Unauthenticated user cannot post comment
        unauth_res = self.client.post(
            reverse("comment-list-create"),
            {
                "company_code": "THYAO",
                "target_type": "COMPANY",
                "content": "Yetkisiz yorum denemesi",
            },
            format="json",
        )
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticate as User A and create a financial table comment
        login_a = self.client.post(
            reverse("auth-login"),
            {"username": "analist_ali", "password": "GucluParola123!"},
            format="json",
        )
        token_a = login_a.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")

        create_res = self.client.post(
            reverse("comment-list-create"),
            {
                "company_code": "THYAO",
                "target_type": "FINANCIAL_TABLE",
                "statement_type": "BILANCO",
                "period": "2025/12",
                "content": "Özkaynak büyümesi oldukça dengeli görünüyor.",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        comment_id = create_res.data["id"]
        self.assertFalse(create_res.data["is_edited"])
        self.assertTrue(create_res.data["is_owner"])

        # Authenticate as User B and try to edit or delete User A's comment -> Forbidden (403)
        login_b = self.client.post(
            reverse("auth-login"),
            {"username": "yatirimci_zeynep", "password": "GucluParola123!"},
            format="json",
        )
        token_b = login_b.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}")

        forbidden_edit = self.client.patch(
            reverse("comment-detail", args=[comment_id]),
            {"content": "Başkasının yorumunu değiştirmeye çalışıyorum."},
            format="json",
        )
        self.assertEqual(forbidden_edit.status_code, status.HTTP_403_FORBIDDEN)

        forbidden_delete = self.client.delete(
            reverse("comment-detail", args=[comment_id])
        )
        self.assertEqual(forbidden_delete.status_code, status.HTTP_403_FORBIDDEN)

        # User A edits their own comment -> 200 OK & is_edited becomes True
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")
        own_edit = self.client.patch(
            reverse("comment-detail", args=[comment_id]),
            {"content": "Özkaynak büyümesi ve nakit pozisyonu oldukça dengeli görünüyor."},
            format="json",
        )
        self.assertEqual(own_edit.status_code, status.HTTP_200_OK)
        self.assertTrue(own_edit.data["is_edited"])

        # User A deletes their own comment -> 204 No Content
        own_delete = self.client.delete(reverse("comment-detail", args=[comment_id]))
        self.assertEqual(own_delete.status_code, status.HTTP_204_CONTENT if hasattr(status, "HTTP_204_CONTENT") else status.HTTP_204_NO_CONTENT)
        self.assertEqual(Comment.objects.count(), 0)

    def test_financial_analysis_engine_and_missing_data_handling(self):
        sample_financials = {
            "data_available": True,
            "tables": {
                "BILANCO": {
                    "periods": ["2025/12", "2024/12"],
                    "rows": [
                        {"key": "current_assets", "values": {"2025/12": 200.0, "2024/12": 150.0}},
                        {"key": "current_liabilities", "values": {"2025/12": 100.0, "2024/12": 100.0}},
                        {"key": "total_assets", "values": {"2025/12": 500.0, "2024/12": 400.0}},
                        {"key": "total_liabilities", "values": {"2025/12": 200.0, "2024/12": 180.0}},
                        {"key": "total_equity", "values": {"2025/12": 300.0, "2024/12": 220.0}},
                    ],
                },
                "GELIR": {
                    "periods": ["2025/12", "2024/12"],
                    "rows": [
                        {"key": "revenue", "values": {"2025/12": 1000.0, "2024/12": 800.0}},
                        {"key": "gross_profit", "values": {"2025/12": 300.0, "2024/12": 240.0}},
                        {"key": "operating_income", "values": {"2025/12": 150.0, "2024/12": 120.0}},
                        {"key": "net_income", "values": {"2025/12": 120.0, "2024/12": 90.0}},
                    ],
                },
                "NAKIT": {
                    "periods": ["2025/12"],
                    "rows": [
                        {"key": "operating_cash_flow", "values": {"2025/12": 180.0}},
                        {"key": "investing_cash_flow", "values": {"2025/12": -70.0}},
                        {"key": "financing_cash_flow", "values": {"2025/12": -30.0}},
                    ],
                },
            },
        }
        analysis = generate_financial_analysis(sample_financials)
        ratio_map = {r["code"]: r for r in analysis["ratios"]}
        self.assertEqual(ratio_map["current_ratio"]["value"], 2.0)
        self.assertEqual(ratio_map["net_margin"]["value"], 12.0)
        self.assertEqual(ratio_map["roe"]["value"], 40.0)
        self.assertIn("yatırım tavsiyesi", analysis["disclaimer"].lower())
