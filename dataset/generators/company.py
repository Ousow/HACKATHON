"""
Générateur d'entreprises françaises fictives mais réalistes.
Produit : SIRET, SIREN, TVA intracommunautaire, adresse, nom, etc.
"""
import random
import string
from faker import Faker

fake = Faker("fr_FR")

# Groupe 5 – Hackathon 2026
BINOMES = [
    "Chaouki Dina",
    "Deumeni Ngaleu Cécile-Audrée",
    "Sow Oumou",
    "Bachir Ryann",
    "Rouviere Bastien",
    "Attaoui Rayana",
]

FORMES_JURIDIQUES = ["SARL", "SAS", "SA", "EURL", "SNC", "Auto-entrepreneur"]
SECTEURS_APE = {
    "6201Z": "Programmation informatique",
    "4711D": "Supermarchés",
    "4120A": "Construction de maisons individuelles",
    "6920Z": "Activités comptables",
    "7320Z": "Études de marché et sondages",
    "8299Z": "Autres activités de soutien aux entreprises",
}


def _luhn_checksum(number: str) -> int:
    """Calcule le checksum Luhn d'un numéro."""
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(divmod(d * 2, 10))
    return checksum % 10


def generate_siren() -> str:
    """Génère un numéro SIREN (9 chiffres) valide selon Luhn."""
    while True:
        base = "".join([str(random.randint(0, 9)) for _ in range(8)])
        for check in range(10):
            candidate = base + str(check)
            if _luhn_checksum(candidate) == 0:
                return candidate


def generate_siret(siren: str = None) -> tuple[str, str]:
    """Génère un SIRET (14 chiffres). Retourne (siren, siret)."""
    if siren is None:
        siren = generate_siren()
    nic = str(random.randint(0, 99999)).zfill(5)
    siret = siren + nic
    return siren, siret


def generate_tva_fr(siren: str) -> str:
    """Calcule le numéro de TVA intracommunautaire français."""
    key = (12 + 3 * (int(siren) % 97)) % 97
    return f"FR{str(key).zfill(2)}{siren}"


def generate_iban() -> str:
    """Génère un IBAN français fictif."""
    bank = str(random.randint(10000, 99999))
    branch = str(random.randint(10000, 99999))
    account = "".join([str(random.randint(0, 9)) for _ in range(11)])
    key = str(random.randint(10, 97))
    bban = bank + branch + account + key
    # Calcul clé IBAN simplifié
    check = 98 - (int(bban + "1527" + "00") % 97)
    return f"FR{str(check).zfill(2)} {bank} {branch} {account[:4]} {account[4:8]} {account[8:]} {key}"


def generate_bic() -> str:
    """Génère un BIC fictif."""
    banks = ["BNPAFRPP", "SOGEFRPP", "CMCIFRPP", "CEPAFRPP", "LCREFRPP", "AGRIFRPP"]
    return random.choice(banks)


def generate_company(
    use_binome: bool = False,
    force_siret: str = None,
    force_tva: str = None
) -> dict:
    """
    Génère une entreprise française fictive complète.

    Args:
        use_binome: si True, utilise les noms des binômes pour personnaliser
        force_siret: impose un SIRET précis (pour scénario incohérent)
        force_tva: impose un n° TVA précis (pour scénario incohérent)

    Returns:
        dict avec toutes les infos de l'entreprise
    """
    if use_binome and BINOMES:
        binome = random.choice(BINOMES)
        parts = binome.split()
        nom = f"{random.choice(FORMES_JURIDIQUES)} {parts[-1].upper()}"
    else:
        nom = fake.company()

    forme = random.choice(FORMES_JURIDIQUES)
    code_ape, libelle_ape = random.choice(list(SECTEURS_APE.items()))

    siren, siret = generate_siret()
    if force_siret:
        # On garde le SIREN du SIRET forcé
        siret = force_siret
        siren = force_siret[:9]

    tva = generate_tva_fr(siren)
    if force_tva:
        tva = force_tva

    iban = generate_iban()
    bic = generate_bic()

    return {
        "nom": nom,
        "forme_juridique": forme,
        "adresse": fake.street_address(),
        "code_postal": fake.postcode(),
        "ville": fake.city(),
        "siren": siren,
        "siret": siret,
        "tva": tva,
        "capital": random.choice([1000, 5000, 10000, 50000, 100000]),
        "code_ape": code_ape,
        "libelle_ape": libelle_ape,
        "iban": iban,
        "bic": bic,
        "telephone": fake.phone_number(),
        "email": fake.company_email(),
        "representant": fake.name(),
    }
