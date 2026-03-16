"""
Générateur de factures PDF réalistes en français.
Supporte : factures légitimes, montants falsifiés, TVA incohérente.
"""
import random
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


TAUX_TVA = [0.20, 0.10, 0.055, 0.021]  # Taux légaux français


def _build_lignes(n_lignes: int = None) -> list[dict]:
    """Génère des lignes de facture fictives."""
    produits = [
        ("Prestation de conseil", 150, 500),
        ("Développement logiciel", 600, 2000),
        ("Formation", 300, 1200),
        ("Maintenance", 100, 800),
        ("Licence logicielle", 200, 5000),
        ("Audit", 500, 3000),
        ("Support technique", 80, 400),
        ("Hébergement serveur", 50, 500),
    ]
    if n_lignes is None:
        n_lignes = random.randint(2, 6)

    lignes = []
    for _ in range(n_lignes):
        desc, min_pu, max_pu = random.choice(produits)
        qte = random.randint(1, 20)
        pu_ht = round(random.uniform(min_pu, max_pu), 2)
        total_ht = round(qte * pu_ht, 2)
        lignes.append({
            "description": desc,
            "quantite": qte,
            "pu_ht": pu_ht,
            "total_ht": total_ht,
        })
    return lignes


def generate_facture_pdf(
    path: str,
    emetteur: dict,
    destinataire: dict,
    date_emission: date = None,
    taux_tva: float = 0.20,
    falsify_montant: bool = False,
    falsify_tva: bool = False,
) -> dict:
    """
    Génère une facture PDF.

    Args:
        path: chemin de sortie du PDF
        emetteur: dict entreprise émettrice
        destinataire: dict entreprise destinataire
        date_emission: date de la facture (défaut=aujourd'hui)
        taux_tva: taux de TVA à appliquer
        falsify_montant: si True, falsifie le total TTC affiché
        falsify_tva: si True, affiche une TVA incohérente avec le HT

    Returns:
        dict métadata (ground truth)
    """
    if date_emission is None:
        date_emission = date.today() - timedelta(days=random.randint(0, 180))

    num_facture = f"FAC-{date_emission.year}-{random.randint(1000, 9999)}"
    date_echeance = date_emission + timedelta(days=random.choice([30, 45, 60]))

    lignes = _build_lignes()
    total_ht = round(sum(l["total_ht"] for l in lignes), 2)
    tva_amount_real = round(total_ht * taux_tva, 2)
    total_ttc_real = round(total_ht + tva_amount_real, 2)

    # Valeurs affichées (peuvent être falsifiées)
    tva_amount_displayed = round(total_ht * random.choice(TAUX_TVA), 2) if falsify_tva else tva_amount_real
    total_ttc_displayed = round(total_ht + tva_amount_displayed * random.uniform(1.1, 1.5), 2) if falsify_montant else total_ttc_real

    # --- Construction PDF ---
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    styles = getSampleStyleSheet()
    story = []

    style_titre = ParagraphStyle("titre", fontSize=20, fontName="Helvetica-Bold",
                                  spaceAfter=6, textColor=colors.HexColor("#1a3a5c"))
    style_normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=13)
    style_bold = ParagraphStyle("bold", fontSize=9, fontName="Helvetica-Bold", leading=13)
    style_right = ParagraphStyle("right", fontSize=9, fontName="Helvetica",
                                  alignment=TA_RIGHT, leading=13)

    # En-tête
    story.append(Paragraph("FACTURE", style_titre))
    story.append(Spacer(1, 4*mm))

    header_data = [
        [
            Paragraph(f"<b>{emetteur['nom']}</b><br/>{emetteur['forme_juridique']}<br/>"
                      f"{emetteur['adresse']}<br/>{emetteur['code_postal']} {emetteur['ville']}<br/>"
                      f"SIRET : {emetteur['siret']}<br/>TVA : {emetteur['tva']}<br/>"
                      f"Tél : {emetteur['telephone']}<br/>{emetteur['email']}", style_normal),
            Paragraph(f"<b>Facture N° :</b> {num_facture}<br/>"
                      f"<b>Date d'émission :</b> {date_emission.strftime('%d/%m/%Y')}<br/>"
                      f"<b>Date d'échéance :</b> {date_echeance.strftime('%d/%m/%Y')}<br/><br/>"
                      f"<b>Facturé à :</b><br/>{destinataire['nom']}<br/>"
                      f"{destinataire['adresse']}<br/>{destinataire['code_postal']} {destinataire['ville']}<br/>"
                      f"SIRET : {destinataire['siret']}", style_normal),
        ]
    ]
    header_table = Table(header_data, colWidths=[85*mm, 85*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.5, colors.grey),
        ("BOX", (1, 0), (1, 0), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f0f4f8")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8*mm))

    # Lignes de facturation
    col_headers = ["Description", "Qté", "P.U. HT (€)", "Total HT (€)"]
    table_data = [col_headers]
    for l in lignes:
        table_data.append([
            l["description"],
            str(l["quantite"]),
            f"{l['pu_ht']:,.2f}",
            f"{l['total_ht']:,.2f}",
        ])

    lines_table = Table(table_data, colWidths=[90*mm, 20*mm, 35*mm, 35*mm])
    lines_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(lines_table)
    story.append(Spacer(1, 4*mm))

    # Totaux
    totaux_data = [
        ["Total HT", f"{total_ht:,.2f} €"],
        [f"TVA ({taux_tva*100:.1f}%)", f"{tva_amount_displayed:,.2f} €"],
        ["Total TTC", f"{total_ttc_displayed:,.2f} €"],
    ]
    totaux_table = Table(totaux_data, colWidths=[130*mm, 40*mm])
    totaux_table.setStyle(TableStyle([
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(totaux_table)
    story.append(Spacer(1, 8*mm))

    # RIB / Paiement
    rib_text = (f"<b>Règlement par virement :</b><br/>"
                f"Banque : {emetteur['bic']} — IBAN : {emetteur['iban']}<br/>"
                f"Pénalités de retard : 3× le taux légal. Escompte : aucun.")
    story.append(Paragraph(rib_text, style_normal))
    story.append(Spacer(1, 4*mm))

    # Mentions légales
    mentions = (f"{emetteur['forme_juridique']} au capital de {emetteur['capital']:,} € — "
                f"SIRET {emetteur['siret']} — APE {emetteur['code_ape']} — TVA {emetteur['tva']}")
    story.append(Paragraph(mentions, ParagraphStyle("footer", fontSize=7,
                                                      textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(story)

    # Ground truth retourné
    return {
        "type": "facture",
        "fichier": path,
        "num_facture": num_facture,
        "date_emission": date_emission.isoformat(),
        "date_echeance": date_echeance.isoformat(),
        "emetteur_siret": emetteur["siret"],
        "emetteur_tva": emetteur["tva"],
        "destinataire_siret": destinataire["siret"],
        "total_ht": total_ht,
        "taux_tva": taux_tva,
        "tva_amount_real": tva_amount_real,
        "total_ttc_real": total_ttc_real,
        "total_ttc_displayed": total_ttc_displayed,
        "anomalies": {
            "montant_falsifie": falsify_montant,
            "tva_incoherente": falsify_tva,
            "tva_displayed": tva_amount_displayed,
        }
    }
