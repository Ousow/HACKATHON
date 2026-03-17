import re
from datetime import datetime
from typing import Any, Dict, List, Optional


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_amount(amount_str: str) -> Optional[float]:
    """
    Gère correctement les formats :
    - 12 915,39
    - 12,915.39
    - 12915,39
    - 12915.39
    """
    if not amount_str:
        return None

    s = amount_str.strip()
    s = s.replace("\xa0", " ").replace("€", "").strip()
    s = s.replace(" ", "")

    # Cas mixte : "12,915.39" ou "12.915,39"
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")

        # Format US : 12,915.39
        if last_dot > last_comma:
            s = s.replace(",", "")
        # Format FR : 12.915,39
        else:
            s = s.replace(".", "")
            s = s.replace(",", ".")

    # Cas FR : 12915,39
    elif "," in s:
        s = s.replace(",", ".")

    # Cas "12915.39" : rien à faire

    try:
        return float(s)
    except ValueError:
        return None


def parse_french_date(date_str: str) -> Optional[str]:
    """
    Convertit différentes dates FR vers ISO YYYY-MM-DD.
    """
    if not date_str:
        return None

    date_str = date_str.strip().lower()

    month_map = {
        "janvier": "01",
        "février": "02",
        "fevrier": "02",
        "mars": "03",
        "avril": "04",
        "mai": "05",
        "juin": "06",
        "juillet": "07",
        "août": "08",
        "aout": "08",
        "septembre": "09",
        "octobre": "10",
        "novembre": "11",
        "décembre": "12",
        "decembre": "12",
    }

    # 12/03/2025 ou 12-03-2025
    m = re.match(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})", date_str)
    if m:
        day, month, year = m.groups()
        if len(year) == 2:
            year = "20" + year
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 12 mars 2025
    m = re.match(r"(\d{1,2})\s+([a-zéèêëàâîïôöùûüç]+)\s+(\d{4})", date_str)
    if m:
        day, month_txt, year = m.groups()
        month = month_map.get(month_txt)
        if month:
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return None

    return None


def guess_document_type(text: str) -> str:
    lower = text.lower()

    if "facture" in lower:
        return "facture"
    if "devis" in lower:
        return "devis"
    if "attestation" in lower:
        return "attestation"
    if "bon de commande" in lower:
        return "bon_de_commande"
    if "relevé d'identité bancaire" in lower or "releve d'identite bancaire" in lower or "rib" in lower:
        return "rib"

    return "inconnu"


def extract_siret(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    candidates = []
    invalid_candidates = []

    for line in lines:
        if re.search(r"\b(IBAN|BANQUE|BIC)\b", line, flags=re.IGNORECASE):
            continue

        if re.search(r"\bSIRET\b", line, flags=re.IGNORECASE):
            found = re.findall(r"(\d[\d\s.]{12,20})", line)
            for raw in found:
                cleaned = re.sub(r"\D", "", raw)
                if len(cleaned) == 14:
                    candidates.append(cleaned)
                else:
                    invalid_candidates.append(cleaned)

    # fallback plus large si rien trouvé
    if not candidates:
        for m in re.finditer(r"\b((?:\d[\s.]*){14})\b", text):
            cleaned = re.sub(r"\D", "", m.group(1))
            if len(cleaned) == 14:
                candidates.append(cleaned)

    candidates = list(dict.fromkeys(candidates))
    invalid_candidates = list(dict.fromkeys(invalid_candidates))

    if candidates:
        return {
            "value": candidates[0],
            "all_candidates": candidates,
            "invalid_candidates": invalid_candidates,
            "confidence": 0.95,
            "source": "regex"
        }

    return {
        "value": None,
        "all_candidates": [],
        "invalid_candidates": invalid_candidates,
        "confidence": 0.0,
        "source": None
    }


def extract_tva(text: str) -> Dict[str, Any]:
    """
    TVA intracom FR : FR + 2 car. alphanum + 9 chiffres
    """
    patterns = [
        r"\bTVA(?:\s+intracommunautaire)?\s*[:\-]?\s*(FR[0-9A-Z]{2}\s?\d{9})\b",
        r"\bN[°o]?\s*TVA\s*[:\-]?\s*(FR[0-9A-Z]{2}\s?\d{9})\b",
        r"\b(FR[0-9A-Z]{2}\s?\d{9})\b",
    ]

    matches = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            val = re.sub(r"\s+", "", m.group(1).upper())
            matches.append(val)

    matches = list(dict.fromkeys(matches))

    if not matches:
        return {"value": None, "all_candidates": [], "confidence": 0.0, "source": None}

    return {
        "value": matches[0],
        "all_candidates": matches,
        "confidence": 0.92,
        "source": "regex"
    }


def extract_amount_by_labels(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Cherche des montants proches de labels : HT, TTC, TVA.
    """
    results = {
        "montant_ht": {"value": None, "confidence": 0.0, "source": None},
        "montant_ttc": {"value": None, "confidence": 0.0, "source": None},
        "montant_tva": {"value": None, "confidence": 0.0, "source": None},
    }

    amount_pattern = r"(\d{1,3}(?:[ ,.]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2}))"

    label_patterns = {
        "montant_ht": [
            rf"(?:montant\s+)?HT\b[^0-9\n]{{0,25}}{amount_pattern}",
            rf"total\s+HT\b[^0-9\n]{{0,25}}{amount_pattern}",
            rf"net\s+HT\b[^0-9\n]{{0,25}}{amount_pattern}",
        ],
        "montant_ttc": [
            rf"(?:montant\s+)?TTC\b[^0-9\n]{{0,25}}{amount_pattern}",
            rf"total\s+TTC\b[^0-9\n]{{0,25}}{amount_pattern}",
            rf"net\s+à\s+payer\b[^0-9\n]{{0,25}}{amount_pattern}",
        ],
        "montant_tva": [
            rf"\bTVA\b(?:\s*\([^)]+\))?[^0-9\n]{{0,25}}{amount_pattern}",
            rf"montant\s+TVA\b[^0-9\n]{{0,25}}{amount_pattern}",
        ]
    }

    for field, patterns in label_patterns.items():
        candidates = []
        for pattern in patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                amount = clean_amount(m.group(1))
                if amount is not None:
                    candidates.append(amount)

        if candidates:
            results[field] = {
                "value": candidates[-1],
                "all_candidates": candidates,
                "currency": "EUR",
                "confidence": 0.88,
                "source": "regex_label"
            }

    return results


def extract_dates(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Fusionne date d'émission et date d'édition dans un seul champ date_emission.
    Garde séparément date_expiration.
    """
    results = {
        "date_emission": {"value": None, "confidence": 0.0, "source": None},
        "date_expiration": {"value": None, "confidence": 0.0, "source": None},
    }

    date_expr = (
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}"
        r"|\d{1,2}\s+[A-Za-zéèêëàâîïôöùûüç]+\s+\d{4})"
    )

    emission_patterns = [
        rf"date\s+d['’](?:émission|edition|édition)\s*[:\-]?\s*{date_expr}",
        rf"date\s+de\s+facture\s*[:\-]?\s*{date_expr}",
        rf"émise?\s+le\s*[:\-]?\s*{date_expr}",
        rf"\bdate\b\s*[:\-]?\s*{date_expr}",
    ]

    expiration_patterns = [
        rf"date\s+d['’]expiration\s*[:\-]?\s*{date_expr}",
        rf"date\s+d['’]échéance\s*[:\-]?\s*{date_expr}",
        rf"expire\s+le\s*[:\-]?\s*{date_expr}",
        rf"valable\s+jusqu['’]au\s*[:\-]?\s*{date_expr}",
        rf"fin\s+de\s+validité\s*[:\-]?\s*{date_expr}",
        rf"date\s+de\s+validité\s*[:\-]?\s*{date_expr}",
    ]

    for pattern in emission_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            iso = parse_french_date(m.group(1))
            if iso:
                results["date_emission"] = {
                    "value": iso,
                    "confidence": 0.85,
                    "source": "regex_date_context"
                }
                break

    for pattern in expiration_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            iso = parse_french_date(m.group(1))
            if iso:
                results["date_expiration"] = {
                    "value": iso,
                    "confidence": 0.85,
                    "source": "regex_date_context"
                }
                break

    return results


def expected_fields_by_doc_type(doc_type: str) -> List[str]:
    mapping = {
        "facture": ["siret", "tva", "montant_ht", "montant_ttc", "date_emission"],
        "devis": ["siret", "tva", "montant_ht", "montant_ttc", "date_emission", "date_expiration"],
        "attestation": ["siret", "date_emission", "date_expiration"],
        "bon_de_commande": ["siret", "date_emission"],
        "rib": ["siret", "date_emission"],
    }
    return mapping.get(doc_type, ["siret"])


def build_warnings(doc_type: str, fields: Dict[str, Dict[str, Any]]) -> List[str]:
    labels = {
        "siret": "SIRET",
        "tva": "TVA intracom",
        "montant_ht": "Montant HT",
        "montant_ttc": "Montant TTC",
        "montant_tva": "Montant TVA",
        "date_emission": "Date d'émission",
        "date_expiration": "Date d'expiration",
    }

    warnings = []

    for field_name in expected_fields_by_doc_type(doc_type):
        field = fields.get(field_name, {})
        if not field.get("value"):
            warnings.append(f"{labels.get(field_name, field_name)} introuvable")

    siret_field = fields.get("siret", {})
    invalid_candidates = siret_field.get("invalid_candidates", [])
    if invalid_candidates:
        warnings.append("SIRET détecté mais invalide (erreur OCR possible)")

    return warnings


def extract_fields(text: str, document_name: str = "") -> Dict[str, Any]:
    normalized_text = normalize_text(text)
    doc_type = guess_document_type(normalized_text)

    siret = extract_siret(normalized_text)
    tva = extract_tva(normalized_text)
    amounts = extract_amount_by_labels(normalized_text)
    dates = extract_dates(normalized_text)

    fields = {
        "siret": siret,
        "tva": tva,
        "montant_ht": amounts["montant_ht"],
        "montant_ttc": amounts["montant_ttc"],
        "montant_tva": amounts["montant_tva"],
        "date_emission": dates["date_emission"],
        "date_expiration": dates["date_expiration"],
    }

    warnings = build_warnings(doc_type, fields)

    return {
        "document_name": document_name,
        "document_type_guess": doc_type,
        "fields": fields,
        "warnings": warnings,
        "extracted_text_preview": normalized_text[:1000]
    }