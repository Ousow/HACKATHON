"""
Générateur de RIB (Relevé d'Identité Bancaire) PDF.
"""
import random
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

BANQUES = [
    {"nom": "BNP Paribas", "bic": "BNPAFRPP", "code": "30004"},
    {"nom": "Société Générale", "bic": "SOGEFRPP", "code": "30003"},
    {"nom": "Crédit Mutuel", "bic": "CMCIFRPP", "code": "10278"},
    {"nom": "Caisse d'Épargne", "bic": "CEPAFRPP", "code": "18306"},
    {"nom": "LCL", "bic": "LCREFRPP", "code": "30002"},
    {"nom": "Crédit Agricole", "bic": "AGRIFRPP", "code": "18206"},
]


def generate_rib_pdf(path: str, entreprise: dict, force_iban: str = None) -> dict:
    """
    Génère un RIB PDF.

    Args:
        force_iban: si renseigné, affiche cet IBAN à la place du vrai
                    (simulation fraude : substitution de RIB).
    """
    banque = random.choice(BANQUES)
    code_guichet = str(random.randint(10000, 99999))
    num_compte = "".join([str(random.randint(0, 9)) for _ in range(11)])
    cle_rib = str(random.randint(10, 97))

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    story = []

    s_titre = ParagraphStyle("titre", fontSize=16, fontName="Helvetica-Bold",
                              alignment=TA_CENTER, textColor=colors.HexColor("#1a3a5c"), spaceAfter=6)
    s_normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=14)

    story.append(Paragraph("RELEVÉ D'IDENTITÉ BANCAIRE", s_titre))
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 6*mm))

    # Titulaire
    story.append(Paragraph("<b>Titulaire du compte :</b>", s_normal))
    story.append(Spacer(1, 2*mm))
    titulaire_data = [
        ["Raison sociale :", entreprise["nom"]],
        ["Adresse :", f"{entreprise['adresse']}, {entreprise['code_postal']} {entreprise['ville']}"],
        ["SIRET :", entreprise["siret"]],
    ]
    t1 = Table(titulaire_data, colWidths=[45*mm, 120*mm])
    t1.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 6*mm))

    # Coordonnées bancaires
    story.append(Paragraph("<b>Coordonnées bancaires :</b>", s_normal))
    story.append(Spacer(1, 2*mm))
    banque_data = [
        ["Banque :", banque["nom"]],
        ["Code banque :", banque["code"]],
        ["Code guichet :", code_guichet],
        ["Numéro de compte :", num_compte],
        ["Clé RIB :", cle_rib],
        ["BIC / SWIFT :", banque["bic"]],
        ["IBAN :", force_iban if force_iban else entreprise["iban"]],
    ]
    t2 = Table(banque_data, colWidths=[45*mm, 120*mm])
    t2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        f"Document émis le {date.today().strftime('%d/%m/%Y')} — "
        f"À conserver précieusement pour vos règlements bancaires.",
        ParagraphStyle("footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)

    return {
        "type": "rib",
        "fichier": path,
        "entreprise_siret": entreprise["siret"],
        "banque": banque["nom"],
        "bic": banque["bic"],
        "iban_reel": entreprise["iban"],
        "iban_affiche": force_iban if force_iban else entreprise["iban"],
        "anomalies": {
            "rib_incoherent": force_iban is not None and force_iban != entreprise["iban"]
        },
    }
