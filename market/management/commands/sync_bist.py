from django.core.management.base import BaseCommand
from market.providers.bist_directory_provider import sync_all_bist_companies


class Command(BaseCommand):
    help = "Resmî KAP dizininden tüm Borsa İstanbul (BIST) şirketlerini veritabanına senkronize eder."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Mevcut şirket sayısına bakmaksızın KAP üzerinden tam senkronizasyon yapar.",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)
        result = sync_all_bist_companies(force=force)
        self.stdout.write(
            self.style.SUCCESS(
                f"BIST şirket senkronizasyonu tamamlandı: Toplam {result.get('total_companies')} şirket."
            )
        )
