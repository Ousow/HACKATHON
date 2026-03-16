"""
Générateur d'extrait KBIS.
"""
import random
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from faker import Faker

fake = Faker("fr_FR")


def generate_kbis_pdf(path: str, entreprise: dict, date_reference: date = None) -> dict:
    """Génère un extrait KBIS PDF."""
    if date_reference is None:
        date_reference = date.today() - timedelta(days=random.randint(0, 60))

    date_immatriculation = date_reference - timedelta(days=random.randint(365, 3650))
    rcs_ville = fake.city()
    num_rcs = f"{rcs_ville.upper().split()[0]} {entreprise['siren']}"

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    story = []

    s_titre = ParagraphStyle("titre", fontSize=14, fontName="Helvetica-Bold",
                              alignment=TA_CENTER, textColor=colors.HexColor("#7b0000"), spaceAfter=4)
    s_sous = ParagraphStyle("sous", fontSize=11, fontName="Helvetica-Bold",
                             alignment=TA_CENTER, spaceAfter=6)
    s_normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=14)

    story.append(Paragraph("TRIBUNAL DE COMMERCE", s_titre))
    story.append(Paragraph(f"DE {rcs_ville.upper()}", s_titre))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("EXTRAIT KBIS", s_sous))
    story.append(Paragraph(
        "Extrait du Registre du Commerce et des Sociétés",
        ParagraphStyle("sub2", fontSize=9, alignment=TA_CENTER, textColor=colors.grey)
    ))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#7b0000")))
    story.append(Spacer(1, 6*mm))

    data = [
        ["Dénomination sociale :", entreprise["nom"]],
        ["Forme juridique :", entreprise["forme_juridique"]],
        ["Siège social :", f"{entreprise['adresse']}, {entreprise['code_postal']} {entreprise['ville']}"],
        ["Capital social :", f"{entreprise['capital']:,} €"],
        ["SIREN :", entreprise["siren"]],
        ["SIRET (siège) :", entreprise["siret"]],
        ["N° RCS :", num_rcs],
        ["Code APE :", f"{entreprise['code_ape']} – {entreprise['libelle_ape']}"],
        ["Date d'immatriculation :", date_immatriculation.strftime("%d/%m/%Y")],
        ["Représentant légal :", f"{entreprise['representant']} – Gérant / Président"],
    ]

    table = Table(data, colWidths=[55*mm, 110*mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#fdf0f0"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccaaaa")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        f"Délivré le {date_reference.strftime('%d/%m/%Y')} par le Greffe du Tribunal de Commerce "
        f"de {rcs_ville}. Ce document est certifié conforme aux inscriptions portées au RCS.",
        s_normal
    ))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "Document officiel — infogreffe.fr — Vérifiable en ligne avec le code de sécurité.",
        ParagraphStyle("footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)

    return {
        "type": "kbis",
        "fichier": path,
        "entreprise_siret": entreprise["siret"],
        "siren": entreprise["siren"],
        "num_rcs": num_rcs,
        "date_immatriculation": date_immatriculation.isoformat(),
        "date_edition": date_reference.isoformat(),
        "anomalies": {}
    }
