import hashlib
import json

import requests
import schedula as sh
import stripe
from flask import current_app as ca

default_taxes = [
    {
        "display_name": "IVA",
        "description": "VAT Italy",
        "percentage": 22.0,
        "country": "IT",
        "jurisdiction": "IT",
        "inclusive": False
    },
    {
        "display_name": "MwSt",
        "description": "VAT Germany",
        "percentage": 19.0,
        "country": "DE",
        "jurisdiction": "DE",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT France",
        "percentage": 20.0,
        "country": "FR",
        "jurisdiction": "FR",
        "inclusive": False
    },
    {
        "display_name": "IVA",
        "description": "VAT Spain",
        "percentage": 21.0,
        "country": "ES",
        "jurisdiction": "ES",
        "inclusive": False
    },
    {
        "display_name": "VAT",
        "description": "VAT United Kingdom",
        "percentage": 20,
        "country": "GB",
        "jurisdiction": "GB",
        "inclusive": False
    },
    {
        "display_name": "ÁFA",
        "description": "VAT Hungary",
        "percentage": 27.0,
        "country": "HU",
        "jurisdiction": "HU",
        "inclusive": False
    },
    {
        "display_name": "PDV",
        "description": "VAT Croatia",
        "percentage": 25.0,
        "country": "HR",
        "jurisdiction": "HR",
        "inclusive": False
    },
    {
        "display_name": "MOMS",
        "description": "VAT Sweden",
        "percentage": 25.0,
        "country": "SE",
        "jurisdiction": "SE",
        "inclusive": False
    },
    {
        "display_name": "BTW",
        "description": "VAT Netherlands",
        "percentage": 21.0,
        "country": "NL",
        "jurisdiction": "NL",
        "inclusive": False
    },
    {
        "display_name": "MWST",
        "description": "VAT Austria",
        "percentage": 20.0,
        "country": "AT",
        "jurisdiction": "AT",
        "inclusive": False
    },
    {
        "display_name": "TÁRG",
        "description": "VAT Romania",
        "percentage": 21.0,
        "country": "RO",
        "jurisdiction": "RO",
        "inclusive": False
    },
    {
        "display_name": "VAT",
        "description": "VAT Ireland",
        "percentage": 23.0,
        "country": "IE",
        "jurisdiction": "IE",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Belgium",
        "percentage": 21.0,
        "country": "BE",
        "jurisdiction": "BE",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Luxembourg",
        "percentage": 17.0,
        "country": "LU",
        "jurisdiction": "LU",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Denmark",
        "percentage": 25.0,
        "country": "DK",
        "jurisdiction": "DK",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Finland",
        "percentage": 25.5,
        "country": "FI",
        "jurisdiction": "FI",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Greece",
        "percentage": 24.0,
        "country": "GR",
        "jurisdiction": "GR",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Portugal",
        "percentage": 23.0,
        "country": "PT",
        "jurisdiction": "PT",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Czech Republic",
        "percentage": 21.0,
        "country": "CZ",
        "jurisdiction": "CZ",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Slovakia",
        "percentage": 23.0,
        "country": "SK",
        "jurisdiction": "SK",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Poland",
        "percentage": 23.0,
        "country": "PL",
        "jurisdiction": "PL",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Bulgaria",
        "percentage": 20.0,
        "country": "BG",
        "jurisdiction": "BG",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Lithuania",
        "percentage": 21.0,
        "country": "LT",
        "jurisdiction": "LT",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Latvia",
        "percentage": 21.0,
        "country": "LV",
        "jurisdiction": "LV",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Estonia",
        "percentage": 24.0,
        "country": "EE",
        "jurisdiction": "EE",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Cyprus",
        "percentage": 19.0,
        "country": "CY",
        "jurisdiction": "CY",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Malta",
        "percentage": 18.0,
        "country": "MT",
        "jurisdiction": "MT",
        "inclusive": False
    },
    {
        "display_name": "TVA",
        "description": "VAT Slovenia",
        "percentage": 22.0,
        "country": "SI",
        "jurisdiction": "SI",
        "inclusive": False
    }
]


def _fetch_vat_rates() -> dict:
    response = requests.get("https://api.vatcomply.com/vat_rates", timeout=10)
    response.raise_for_status()
    rates = {d["country_code"]: d["standard_rate"] for d in response.json()}
    if "EL" in rates:
        rates["GR"] = rates["EL"]
    elif "GR" in rates:
        rates["EL"] = rates["GR"]
    res = []
    for r in default_taxes:
        r = r.copy()
        r["percentage"] = rates.get(r["country"], r["percentage"])
        res.append(r)
    return res


def fetch_vat_rates():
    cache = ca.extensions["schedula_cache"]
    tax_rates = cache.get("tax-rates")
    if not tax_rates:
        try:
            tax_rates = _fetch_vat_rates()["rates"]
            cache.set("tax-rates", tax_rates, timeout=60)
            cache.set("tax-rates-latest", tax_rates, timeout=0)
        except Exception:
            tax_rates = cache.get("tax-rates-latest")
            if not tax_rates:
                cache.set("tax-rates-latest", default_taxes, timeout=0)
                tax_rates = default_taxes

    return tax_rates


def get_tax_rates(tax_rates):
    res = []
    tax_rates_list = None
    api_key = ca.config["STRIPE_SECRET_KEY"]
    if tax_rates is True:
        tax_rates = fetch_vat_rates()
    for tax_rate in tax_rates:
        if isinstance(tax_rate, dict):
            metadata = tax_rate.get("metadata", {})
            kwargs = {k: v for k, v in tax_rate.items() if k != "metadata"}
            hash = hashlib.sha256(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
            if tax_rates_list is None:
                tax_rates_list = list(stripe.TaxRate.list(api_key=api_key).auto_paging_iter())
            for tax_rate in tax_rates_list:
                if tax_rate.metadata.get("hash") == hash:
                    tax_rate = tax_rate.id
                    break
            else:
                tax_rate = stripe.TaxRate.create(
                    api_key=api_key,
                    metadata=sh.combine_dicts(metadata, {"hash": hash}),
                    **kwargs,
                ).id
        res.append(tax_rate)
    return res
