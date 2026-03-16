"""
Générateur de devis PDF réalistes en français.
"""
import random
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def generate_devis_pdf(
    path: str,
    emetteur: dict,
    destinataire: dict,
    date_emission: date = None,
    taux_tva: float = 0.20,
) -> dict:
    """
    Génère un devis PDF.

    Returns:
        dict métadata (ground truth)
    """
    if date_emission is None:
        date_emission = date.today() - timedelta(days=random.randint(0, 90))

    date_validite = date_emission + timedelta(days=random.choice([30, 60, 90]))
    num_devis = f"DEV-{date_emission.year}-{random.randint(1000, 9999)}"

    produits = [
        ("Analyse des besoins", 1, 800),
        ("Conception architecture", 1, 1500),
        ("Développement module A", 1, 3000),
        ("Développement module B", 1, 2500),
        ("Tests et recette", 1, 1000),
        ("Formation utilisateurs", 1, 1200),
        ("Documentation technique", 1, 600),
        ("Déploiement et mise en production", 1, 900),
    ]

    n_lignes = random.randint(3, 7)
    lignes = []
    for _ in range(n_lignes):
        desc, _, max_pu = random.choice(produits)
        pu_ht = round(random.uniform(max_pu * 0.6, max_pu), 2)
        qte = random.randint(1, 5)
        lignes.append({
            "description": desc,
            "quantite": qte,
            "pu_ht": pu_ht,
            "total_ht": round(qte * pu_ht, 2),
        })

    total_ht = round(sum(l["total_ht"] for l in lignes), 2)
    tva_amount = round(total_ht * taux_tva, 2)
    total_ttc = round(total_ht + tva_amount, 2)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    styles = getSampleStyleSheet()
    story = []

    style_titre = ParagraphStyle("titre", fontSize=20, fontName="Helvetica-Bold",
                                  spaceAfter=6, textColor=colors.HexColor("#2e7d32"))
    style_normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=13)

    story.append(Paragraph("DEVIS", style_titre))
    story.append(Spacer(1, 4*mm))

    header_data = [[
        Paragraph(f"<b>{emetteur['nom']}</b><br/>{emetteur['forme_juridique']}<br/>"
                  f"{emetteur['adresse']}<br/>{emetteur['code_postal']} {emetteur['ville']}<br/>"
                  f"SIRET : {emetteur['siret']}<br/>TVA : {emetteur['tva']}", style_normal),
        Paragraph(f"<b>Devis N° :</b> {num_devis}<br/>"
                  f"<b>Date :</b> {date_emission.strftime('%d/%m/%Y')}<br/>"
                  f"<b>Valable jusqu'au :</b> {date_validite.strftime('%d/%m/%Y')}<br/><br/>"
                  f"<b>Client :</b><br/>{destinataire['nom']}<br/>"
                  f"{destinataire['adresse']}<br/>{destinataire['code_postal']} {destinataire['ville']}<br/>"
                  f"SIRET : {destinataire['siret']}", style_normal),
    ]]
    header_table = Table(header_data, colWidths=[85*mm, 85*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.5, colors.grey),
        ("BOX", (1, 0), (1, 0), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f1f8f1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8*mm))

    table_data = [["Désignation", "Qté", "P.U. HT (€)", "Total HT (€)"]]
    for l in lignes:
        table_data.append([l["description"], str(l["quantite"]),
                           f"{l['pu_ht']:,.2f}", f"{l['total_ht']:,.2f}"])

    lines_table = Table(table_data, colWidths=[90*mm, 20*mm, 35*mm, 35*mm])
    lines_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fdf7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(lines_table)
    story.append(Spacer(1, 4*mm))

    totaux_data = [
        ["Total HT", f"{total_ht:,.2f} €"],
        [f"TVA ({taux_tva*100:.1f}%)", f"{tva_amount:,.2f} €"],
        ["Total TTC", f"{total_ttc:,.2f} €"],
    ]
    totaux_table = Table(totaux_data, colWidths=[130*mm, 40*mm])
    totaux_table.setStyle(TableStyle([
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#2e7d32")),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(totaux_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph(
        "Ce devis est valable jusqu'à la date indiquée. Toute commande passée après cette date "
        "sera soumise à un nouveau devis. Signature et cachet de l'entreprise valent acceptation.",
        style_normal
    ))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"{emetteur['forme_juridique']} au capital de {emetteur['capital']:,} € — "
        f"SIRET {emetteur['siret']} — TVA {emetteur['tva']}",
        ParagraphStyle("footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)

    return {
        "type": "devis",
        "fichier": path,
        "num_devis": num_devis,
        "date_emission": date_emission.isoformat(),
        "date_validite": date_validite.isoformat(),
        "emetteur_siret": emetteur["siret"],
        "destinataire_siret": destinataire["siret"],
        "total_ht": total_ht,
        "taux_tva": taux_tva,
        "tva_amount": tva_amount,
        "total_ttc": total_ttc,
        "anomalies": {}
    }
