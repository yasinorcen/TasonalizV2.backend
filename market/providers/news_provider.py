"""
Company News & KAP Disclosure Links Provider (Section 3.2).
Fetches headlines, publication dates, source names, and original article URLs via public RSS.
Strictly respects copyright: never copies full article text.
"""

import logging
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from django.core.cache import cache
from django.utils import timezone
import requests

logger = logging.getLogger(__name__)


def get_company_news(code: str, company_name: str, kap_url: str = "") -> dict:
    """
    Fetches company-related headlines from Google News RSS (TR) and provides
    official KAP notification links.
    """
    clean_code = code.strip().upper()
    cache_key = f"company_news_v1_{clean_code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = timezone.now().isoformat()
    short_name = " ".join(company_name.split()[:2]) if company_name else clean_code
    search_query = f'"{clean_code}" OR "{short_name}" borsa hisse KAP'
    rss_url = (
        f"https://news.google.com/rss/search?q={quote_plus(search_query)}"
        "&hl=tr&gl=TR&ceid=TR:tr"
    )

    items = []
    try:
        resp = requests.get(
            rss_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
            },
            timeout=10,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is not None:
            for item_el in channel.findall("item")[:10]:
                raw_title = (item_el.findtext("title") or "").strip()
                link = (item_el.findtext("link") or "").strip()
                pub_date = (item_el.findtext("pubDate") or "").strip()
                source_el = item_el.find("source")
                source_name = (
                    source_el.text.strip()
                    if source_el is not None and source_el.text
                    else "Haber Kaynağı"
                )

                # Clean trailing " - SourceName" from title if present
                clean_title = raw_title
                suffix = f" - {source_name}"
                if clean_title.endswith(suffix):
                    clean_title = clean_title[: -len(suffix)].strip()

                if clean_title and link:
                    items.append(
                        {
                            "title": clean_title,
                            "published_at": pub_date,
                            "source_name": source_name,
                            "url": link,
                        }
                    )
    except Exception as exc:
        logger.warning("News RSS fetch failed for %s: %s", clean_code, exc)

    result = {
        "code": clean_code,
        "data_available": len(items) > 0,
        "items": items,
        "kap_company_url": kap_url or "https://www.kap.org.tr/tr/bist-sirketler",
        "source_name": "Google Haberler RSS Endeksi & Resmî KAP Bildirim Bağlantısı",
        "copyright_notice": (
            "Telif hakları ve kaynak kullanım koşulları gereği yalnızca haber başlığı, yayın tarihi, "
            "kaynak adı ve orijinal haber bağlantısı gösterilmektedir; haber metinleri kopyalanmaz."
        ),
        "last_updated": now_iso,
        "empty_message": (
            None
            if len(items) > 0
            else (
                f"{clean_code} şirketi için açık haber akışında güncel haber başlığı bulunamadı. "
                "Şirketin resmî özel durum açıklamaları için doğrudan KAP sayfasını ziyaret edebilirsiniz."
            )
        ),
    }
    cache.set(cache_key, result, timeout=600)
    return result
