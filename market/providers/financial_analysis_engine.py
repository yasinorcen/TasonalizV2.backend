"""
Educational & Transparent Financial Statement Analysis Engine (Section 3.4).
Computes period-over-period changes, cash flow structure, and fundamental ratios
from verified statement rows.
- Never provides investment advice or guaranteed return claims.
- Explicitly documents the formula, periods, and line items used.
- Clearly warns when any input data is missing or not applicable (e.g. banking sector layout).
"""

from typing import Any


def _row_map(rows: list[dict]) -> dict[str, dict[str, float | None]]:
    return {r["key"]: r.get("values", {}) for r in rows}


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round(((current - previous) / abs(previous)) * 100, 2)


def generate_financial_analysis(financial_data: dict) -> dict:
    """
    Produces structured, plain-language financial analysis based on Bilanço,
    Gelir Tablosu, and Nakit Akışı tables.
    """
    tables = financial_data.get("tables", {})
    bilanco = tables.get("BILANCO", {})
    gelir = tables.get("GELIR", {})
    nakit = tables.get("NAKIT", {})

    bs_periods: list[str] = bilanco.get("periods", [])
    is_periods: list[str] = gelir.get("periods", [])
    cf_periods: list[str] = nakit.get("periods", [])

    bs_map = _row_map(bilanco.get("rows", []))
    is_map = _row_map(gelir.get("rows", []))
    cf_map = _row_map(nakit.get("rows", []))

    warnings: list[str] = []
    if not financial_data.get("data_available"):
        warnings.append(
            "Bu şirket için yapılandırılmış finansal tablo verisi bulunamadığından otomatik "
            "oran ve dönem karşılaştırması hesaplanamamıştır."
        )

    latest_bs_period = bs_periods[0] if bs_periods else None
    prev_bs_period = bs_periods[1] if len(bs_periods) > 1 else None

    latest_is_period = is_periods[0] if is_periods else None
    prev_is_period = is_periods[1] if len(is_periods) > 1 else None

    latest_cf_period = cf_periods[0] if cf_periods else None

    # 1. Period-over-period comparisons (Bilanço & Gelir Tablosu)
    comparisons = []

    def add_comparison(
        key: str,
        title: str,
        category: str,
        data_map: dict,
        curr_p: str | None,
        prev_p: str | None,
        explanation_fn,
    ):
        if not curr_p:
            return
        curr_val = data_map.get(key, {}).get(curr_p)
        prev_val = data_map.get(key, {}).get(prev_p) if prev_p else None
        pct = _pct_change(curr_val, prev_val)
        comparisons.append(
            {
                "key": key,
                "title": title,
                "category": category,
                "current_period": curr_p,
                "previous_period": prev_p,
                "current_value": curr_val,
                "previous_value": prev_val,
                "change_percent": pct,
                "summary": explanation_fn(curr_val, prev_val, pct, curr_p, prev_p),
            }
        )

    add_comparison(
        "total_assets",
        "Toplam Varlıklar Değişimi",
        "Bilanço",
        bs_map,
        latest_bs_period,
        prev_bs_period,
        lambda c, p, pct, cp, pp: (
            f"{cp} döneminde toplam varlıklar {pp} dönemine kıyasla %{pct:+.2f} oranında "
            f"{'artış' if (pct or 0) >= 0 else 'azalış'} göstermiştir."
            if pct is not None
            else "Dönemler arası toplam varlık değişimi için karşılaştırma verisi eksik."
        ),
    )

    add_comparison(
        "total_liabilities",
        "Toplam Yükümlülükler Değişimi",
        "Bilanço",
        bs_map,
        latest_bs_period,
        prev_bs_period,
        lambda c, p, pct, cp, pp: (
            f"{cp} döneminde toplam yabancı kaynaklar (borçlar) {pp} dönemine göre %{pct:+.2f} "
            f"oranında {'artmıştır' if (pct or 0) >= 0 else 'gerilemiştir'}."
            if pct is not None
            else "Toplam yükümlülük değişimi için önceki dönem verisi bulunmamaktadır."
        ),
    )

    add_comparison(
        "total_equity",
        "Özkaynaklar Değişimi",
        "Bilanço",
        bs_map,
        latest_bs_period,
        prev_bs_period,
        lambda c, p, pct, cp, pp: (
            f"Ana ortaklığa ait özkaynaklar {cp} döneminde {pp} dönemine kıyasla %{pct:+.2f} "
            f"oranında {'büyümüştür' if (pct or 0) >= 0 else 'daralmıştır'}."
            if pct is not None
            else "Özkaynak değişim hesabı için yeterli geçmiş dönem verisi bulunamadı."
        ),
    )

    add_comparison(
        "revenue",
        "Satış Gelirleri (Hasılat) Değişimi",
        "Gelir Tablosu",
        is_map,
        latest_is_period,
        prev_is_period,
        lambda c, p, pct, cp, pp: (
            f"Şirketin satış gelirleri (hasılat) {cp} döneminde bir önceki raporlama dönemi "
            f"({pp}) ile karşılaştırıldığında %{pct:+.2f} {'artmıştır' if (pct or 0) >= 0 else 'azalmıştır'}."
            if pct is not None
            else "Hasılat değişim analizi için karşılaştırılabilir iki dönem verisi bulunamadı."
        ),
    )

    add_comparison(
        "operating_income",
        "Esas Faaliyet Kârı Değişimi",
        "Gelir Tablosu",
        is_map,
        latest_is_period,
        prev_is_period,
        lambda c, p, pct, cp, pp: (
            f"Ana faaliyetlerden üretilen operasyonel kâr {cp} döneminde {pp} dönemine göre "
            f"%{pct:+.2f} oranında değişim göstermiştir."
            if pct is not None
            else "Esas faaliyet kârı kalemi bu sektör/şirket tablosunda ayrı raporlanmamış veya önceki dönem eksik."
        ),
    )

    add_comparison(
        "net_income",
        "Net Dönem Kârı / Zararı Değişimi",
        "Gelir Tablosu",
        is_map,
        latest_is_period,
        prev_is_period,
        lambda c, p, pct, cp, pp: (
            f"Net dönem kârı/zararı {cp} döneminde {pp} dönemine göre %{pct:+.2f} değişim göstermiştir."
            if pct is not None
            else "Net dönem kârı karşılaştırması için veri bulunamadı."
        ),
    )

    # 2. Fundamental Financial Ratios (with explicit formulas & educational explanations)
    ratios = []

    def get_bs(key: str) -> float | None:
        return bs_map.get(key, {}).get(latest_bs_period) if latest_bs_period else None

    def get_is(key: str) -> float | None:
        return is_map.get(key, {}).get(latest_is_period) if latest_is_period else None

    curr_assets = get_bs("current_assets")
    curr_liab = get_bs("current_liabilities")
    tot_assets = get_bs("total_assets")
    tot_liab = get_bs("total_liabilities")
    tot_equity = get_bs("total_equity")

    rev = get_is("revenue")
    gross_p = get_is("gross_profit")
    op_inc = get_is("operating_income")
    net_inc = get_is("net_income")

    # Ratio 1: Cari Oran
    if curr_assets is not None and curr_liab and curr_liab != 0:
        val = round(curr_assets / curr_liab, 2)
        ratios.append(
            {
                "code": "current_ratio",
                "name": "Cari Oran (Likidite)",
                "value": val,
                "unit": "x",
                "period": latest_bs_period,
                "formula": "Dönen Varlıklar / Kısa Vadeli Yükümlülükler",
                "status": "calculated",
                "educational_note": (
                    "Kısa vadeli borçların dönen varlıklarla kaç kez karşılanabildiğini gösterir. "
                    f"Hesaplanan {val}x değeri, her 1 TL kısa vadeli yükümlülüğe karşılık {val} TL "
                    "dönen varlık bulunduğunu ifade eder."
                ),
            }
        )
    else:
        ratios.append(
            {
                "code": "current_ratio",
                "name": "Cari Oran (Likidite)",
                "value": None,
                "unit": "x",
                "period": latest_bs_period,
                "formula": "Dönen Varlıklar / Kısa Vadeli Yükümlülükler",
                "status": "missing_data",
                "educational_note": (
                    "Bu şirket için Dönen Varlıklar veya Kısa Vadeli Yükümlülükler ayrı kalem olarak "
                    "raporlanmadığından (ör. bankacılık/finans bilançoları) Cari Oran hesaplanmamıştır."
                ),
            }
        )

    # Ratio 2: Borç / Özkaynak Oranı
    if tot_liab is not None and tot_equity and tot_equity != 0:
        val = round(tot_liab / tot_equity, 2)
        ratios.append(
            {
                "code": "debt_to_equity",
                "name": "Borç / Özkaynak Oranı (Kaldıraç)",
                "value": val,
                "unit": "x",
                "period": latest_bs_period,
                "formula": "Toplam Yükümlülükler / Özkaynaklar",
                "status": "calculated",
                "educational_note": (
                    "Şirketin yabancı kaynaklarının (borçlarının) özkaynaklarına oranını gösterir. "
                    f"{val}x değeri, her 1 TL özkaynağa karşılık {val} TL yabancı kaynak kullanıldığını belirtir."
                ),
            }
        )
    else:
        ratios.append(
            {
                "code": "debt_to_equity",
                "name": "Borç / Özkaynak Oranı (Kaldıraç)",
                "value": None,
                "unit": "x",
                "period": latest_bs_period,
                "formula": "Toplam Yükümlülükler / Özkaynaklar",
                "status": "missing_data",
                "educational_note": "Toplam yükümlülük veya özkaynak verisi eksik olduğundan hesaplanamamıştır.",
            }
        )

    # Ratio 3: Özkaynak Oranı
    if tot_equity is not None and tot_assets and tot_assets != 0:
        val = round((tot_equity / tot_assets) * 100, 2)
        ratios.append(
            {
                "code": "equity_ratio",
                "name": "Özkaynak / Varlık Oranı",
                "value": val,
                "unit": "%",
                "period": latest_bs_period,
                "formula": "(Özkaynaklar / Toplam Varlıklar) × 100",
                "status": "calculated",
                "educational_note": (
                    f"Toplam varlıkların %{val} oranındaki kısmının ortakların özsermayesi ile "
                    "finanse edildiğini gösterir."
                ),
            }
        )

    # Ratio 4: Brüt Kâr Marjı
    if gross_p is not None and rev and rev != 0:
        val = round((gross_p / rev) * 100, 2)
        ratios.append(
            {
                "code": "gross_margin",
                "name": "Brüt Kâr Marjı",
                "value": val,
                "unit": "%",
                "period": latest_is_period,
                "formula": "(Brüt Kâr / Hasılat) × 100",
                "status": "calculated",
                "educational_note": (
                    f"Satış gelirlerinden doğrudan satış maliyetleri düşüldükten sonra hasılatın "
                    f"%{val} kadarının brüt kâr olarak kaldığını gösterir."
                ),
            }
        )

    # Ratio 5: Net Kâr Marjı
    if net_inc is not None and rev and rev != 0:
        val = round((net_inc / rev) * 100, 2)
        ratios.append(
            {
                "code": "net_margin",
                "name": "Net Kâr Marjı",
                "value": val,
                "unit": "%",
                "period": latest_is_period,
                "formula": "(Net Dönem Kârı / Hasılat) × 100",
                "status": "calculated",
                "educational_note": (
                    f"Tüm giderler, finansman maliyetleri ve vergiler sonrasında her 100 TL satış "
                    f"gelirinden {val} TL net kâr/zarar oluştuğunu gösterir."
                ),
            }
        )

    # Ratio 6: Özkaynak Kârlılığı (ROE)
    if net_inc is not None and tot_equity and tot_equity > 0:
        val = round((net_inc / tot_equity) * 100, 2)
        ratios.append(
            {
                "code": "roe",
                "name": "Özkaynak Kârlılığı (ROE)",
                "value": val,
                "unit": "%",
                "period": latest_is_period or latest_bs_period,
                "formula": "(Net Dönem Kârı / Özkaynaklar) × 100",
                "status": "calculated",
                "educational_note": (
                    f"Ortakların şirkete koyduğu özkaynakların ilgili dönemde %{val} oranında "
                    "net kâr/zarar ürettiğini ifade eder."
                ),
            }
        )

    # 3. Cash Flow Overview
    cash_flow_summary = {
        "period": latest_cf_period,
        "operating": cf_map.get("operating_cash_flow", {}).get(latest_cf_period) if latest_cf_period else None,
        "investing": cf_map.get("investing_cash_flow", {}).get(latest_cf_period) if latest_cf_period else None,
        "financing": cf_map.get("financing_cash_flow", {}).get(latest_cf_period) if latest_cf_period else None,
        "free_cash_flow": cf_map.get("free_cash_flow", {}).get(latest_cf_period) if latest_cf_period else None,
        "ending_cash": cf_map.get("ending_cash", {}).get(latest_cf_period) if latest_cf_period else None,
        "commentary": [],
    }

    op_cf = cash_flow_summary["operating"]
    inv_cf = cash_flow_summary["investing"]
    fin_cf = cash_flow_summary["financing"]

    if op_cf is not None:
        if op_cf > 0:
            cash_flow_summary["commentary"].append(
                f"{latest_cf_period} döneminde şirket esas faaliyetlerinden pozitif nakit girişi üretmiştir."
            )
        else:
            cash_flow_summary["commentary"].append(
                f"{latest_cf_period} döneminde işletme faaliyetlerinden net nakit çıkışı gerçekleşmiştir."
            )
    if inv_cf is not None:
        if inv_cf < 0:
            cash_flow_summary["commentary"].append(
                "Yatırım faaliyetlerinden nakit akışının negatif olması, şirketin sabit kıymet veya yatırım harcaması yaptığına işaret edebilir."
            )
        else:
            cash_flow_summary["commentary"].append(
                "Yatırım faaliyetlerinden net nakit girişi kaydedilmiştir."
            )
    if fin_cf is not None:
        if fin_cf < 0:
            cash_flow_summary["commentary"].append(
                "Finansman faaliyetlerinden net nakit çıkışı (kredi geri ödemesi veya temettü ödemesi gibi) görülmektedir."
            )
        else:
            cash_flow_summary["commentary"].append(
                "Finansman faaliyetlerinden net nakit girişi (yeni borçlanma veya sermaye girişi gibi) gerçekleşmiştir."
            )

    if any(r["status"] == "missing_data" for r in ratios):
        warnings.append(
            "Bazı finansal oranlar, şirketin sektörel bilanço formatı (ör. Bankacılık, Sigorta veya Holding) "
            "nedeniyle ilgili alt kalemler standart tabloda yer almadığı için boş bırakılmıştır."
        )

    return {
        "latest_periods": {
            "bilanco": latest_bs_period,
            "gelir": latest_is_period,
            "nakit": latest_cf_period,
        },
        "comparisons": comparisons,
        "ratios": ratios,
        "cash_flow_summary": cash_flow_summary,
        "warnings": warnings,
        "disclaimer": (
            "Burada yer alan finansal analizler ve oran hesaplamaları yalnızca eğitim, bilgilendirme "
            "ve öğrenci simülasyonu amacı taşır. Kesinlikle yatırım tavsiyesi veya getiri vaadi değildir."
        ),
    }
