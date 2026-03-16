"""
Générateur d'attestations de vigilance URSSAF.
Supporte : attestation valide, expirée, ou avec mauvais SIRET.
"""
import random
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def generate_attestation_urssaf_pdf(
    path: str,
    entreprise: dict,
    expired: bool = False,
    force_siret: str = None,
    date_reference: date = None,
) -> dict:
    """
    Génère une attestation de vigilance URSSAF.

    Args:
        path: chemin de sortie
        entreprise: dict entreprise
        expired: si True, génère une attestation expirée
        force_siret: impose un mauvais SIRET (scénario incohérent)
        date_reference: date de référence (défaut=aujourd'hui)

    Returns:
        dict ground truth
    """
    if date_reference is None:
        date_reference = date.today()

    if expired:
        date_edition = date_reference - timedelta(days=random.randint(200, 400))
        date_expiration = date_edition + timedelta(days=random.randint(30, 90))
        is_expired = True
    else:
        date_edition = date_reference - timedelta(days=random.randint(0, 30))
        date_expiration = date_edition + timedelta(days=random.randint(90, 180))
        is_expired = False

    siret_affiche = force_siret if force_siret else entreprise["siret"]
    num_attestation = f"ATT-{random.randint(100000, 999999)}-{date_edition.year}"

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    story = []

    style_titre = ParagraphStyle("titre", fontSize=16, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, spaceAfter=6,
                                  textColor=colors.HexColor("#003189"))
    style_sous_titre = ParagraphStyle("sous_titre", fontSize=11, fontName="Helvetica-Bold",
                                       alignment=TA_CENTER, spaceAfter=10,
                                       textColor=colors.HexColor("#003189"))
    style_normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=14)
    style_bold = ParagraphStyle("bold", fontSize=9, fontName="Helvetica-Bold", leading=14)
    style_center = ParagraphStyle("center", fontSize=9, fontName="Helvetica",
                                   leading=14, alignment=TA_CENTER)

    # En-tête URSSAF
    story.append(Paragraph("URSSAF", style_titre))
    story.append(Paragraph("ATTESTATION DE VIGILANCE", style_sous_titre))
    story.append(Paragraph(
        "Article L.8222-1 du Code du Travail",
        ParagraphStyle("ref", fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
    ))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#003189")))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("L'URSSAF certifie que l'entreprise :", style_normal))
    story.append(Spacer(1, 4*mm))

    # Infos entreprise
    info_data = [
        ["Raison sociale :", entreprise["nom"]],
        ["Forme juridique :", entreprise["forme_juridique"]],
        ["Adresse :", f"{entreprise['adresse']}, {entreprise['code_postal']} {entreprise['ville']}"],
        ["SIRET :", siret_affiche],
        ["N° TVA :", entreprise["tva"]],
        ["Code APE :", f"{entreprise['code_ape']} – {entreprise['libelle_ape']}"],
    ]
    info_table = Table(info_data, colWidths=[50*mm, 105*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0f3fb"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaacc")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6*mm))

    # Texte légal
    story.append(Paragraph(
        "Est à jour de ses obligations déclaratives et de paiement "
        "auprès de l'URSSAF à la date d'édition du présent document.",
        style_normal
    ))
    story.append(Spacer(1, 4*mm))

    # Dates
    date_data = [
        ["Date d'édition :", date_edition.strftime("%d/%m/%Y")],
        ["Date d'expiration :", date_expiration.strftime("%d/%m/%Y")],
        ["Numéro d'attestation :", num_attestation],
    ]
    date_table = Table(date_data, colWidths=[60*mm, 95*mm])
    date_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8edf8")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(date_table)
    story.append(Spacer(1, 8*mm))

    # Mention expiration
    if is_expired:
        story.append(Paragraph(
            "⚠ ATTENTION : Cette attestation est arrivée à échéance.",
            ParagraphStyle("warn", fontSize=10, fontName="Helvetica-Bold",
                           textColor=colors.red, alignment=TA_CENTER)
        ))
        story.append(Spacer(1, 4*mm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Ce document peut être vérifié sur net-entreprises.fr — "
        "Document généré automatiquement, ne nécessite pas de signature.",
        ParagraphStyle("footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)

    return {
        "type": "attestation_urssaf",
        "fichier": path,
        "num_attestation": num_attestation,
        "entreprise_siret": entreprise["siret"],
        "siret_affiche": siret_affiche,
        "date_edition": date_edition.isoformat(),
        "date_expiration": date_expiration.isoformat(),
        "anomalies": {
            "attestation_expiree": is_expired,
            "siret_incoherent": force_siret is not None and force_siret != entreprise["siret"],
        }
    }
