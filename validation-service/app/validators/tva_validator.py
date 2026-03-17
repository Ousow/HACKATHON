"""
Validateur de cohérence TVA.
Détecte les erreurs de calcul de TVA sur les factures.
"""

import re
from typing import List
from loguru import logger

from app.validators.base import BaseValidator
from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
    TypeAnomalie,
    NiveauGravite,
)


# Taux de TVA légaux en France
TAUX_TVA_LEGAUX = {
    0.20: "Taux normal (20%)",
    0.10: "Taux intermédiaire (10%)",
    0.055: "Taux réduit (5.5%)",
    0.021: "Taux super-réduit (2.1%)",
    0.0: "Exonération (0%)",
}

# Tolérance pour les erreurs d'arrondi
TOLERANCE_ARRONDI = 0.02  # 2 centimes


class TVAValidator(BaseValidator):
    """
    Validateur TVA - Vérifie :
    1. Calcul correct de la TVA (HT × taux = TVA)
    2. Calcul correct du TTC (HT + TVA = TTC)
    3. Taux de TVA légal
    4. Format du numéro de TVA intracommunautaire
    """
    
    @property
    def description(self) -> str:
        return "Validation des calculs de TVA et des numéros TVA intracommunautaire"
    
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide les données TVA du dossier"""
        anomalies = []
        
        # Valider la facture
        if dossier.facture:
            anomalies.extend(self._validate_facture_tva(dossier.facture))
            
            # Valider le numéro TVA intracommunautaire
            if dossier.facture.tva_intracommunautaire:
                tva_anomalie = self._validate_tva_number(
                    dossier.facture.tva_intracommunautaire,
                    "facture"
                )
                if tva_anomalie:
                    anomalies.append(tva_anomalie)
        
        # Valider le devis
        if dossier.devis:
            anomalies.extend(self._validate_devis_tva(dossier.devis))
        
        # Valider cohérence TVA entre facture et attestation
        if dossier.facture and dossier.attestation_urssaf:
            if dossier.facture.tva_intracommunautaire and dossier.attestation_urssaf.tva_intracommunautaire:
                if dossier.facture.tva_intracommunautaire != dossier.attestation_urssaf.tva_intracommunautaire:
                    anomalies.append(AnomalieDetectee(
                        type_anomalie=TypeAnomalie.TVA_INTRACOMMUNAUTAIRE_INVALIDE,
                        gravite=NiveauGravite.WARNING,
                        message="Numéro TVA intracommunautaire différent entre facture et attestation URSSAF",
                        documents_concernes=["facture", "attestation_urssaf"],
                        details={
                            "tva_facture": dossier.facture.tva_intracommunautaire,
                            "tva_attestation": dossier.attestation_urssaf.tva_intracommunautaire,
                        }
                    ))
        
        logger.info(f"TVAValidator: {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies
    
    def _validate_facture_tva(self, facture) -> List[AnomalieDetectee]:
        """Valide les calculs de TVA sur une facture"""
        anomalies = []
        
        montant_ht = facture.montant_ht
        taux_tva = facture.taux_tva
        montant_tva_declare = facture.montant_tva
        montant_ttc_declare = facture.montant_ttc
        
        # 1. Vérifier que le taux de TVA est légal
        taux_valide = any(
            abs(taux_tva - taux) < 0.001 
            for taux in TAUX_TVA_LEGAUX.keys()
        )
        
        if not taux_valide and taux_tva > 0:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.TVA_INCOHERENTE,
                gravite=NiveauGravite.WARNING,
                message=f"Taux de TVA inhabituel: {taux_tva*100:.1f}%",
                documents_concernes=["facture"],
                details={
                    "taux_declare": taux_tva,
                    "taux_legaux": list(TAUX_TVA_LEGAUX.keys()),
                },
                confiance=0.8
            ))
        
        # 2. Vérifier le calcul de la TVA
        tva_calculee = round(montant_ht * taux_tva, 2)
        ecart_tva = abs(tva_calculee - montant_tva_declare)
        
        if ecart_tva > TOLERANCE_ARRONDI:
            # Calculer le taux implicite
            taux_implicite = montant_tva_declare / montant_ht if montant_ht > 0 else 0
            
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.TVA_INCOHERENTE,
                gravite=NiveauGravite.CRITICAL,
                message=f"Montant TVA incohérent: {montant_tva_declare}€ déclaré vs {tva_calculee}€ calculé (écart: {ecart_tva:.2f}€)",
                documents_concernes=["facture"],
                details={
                    "montant_ht": montant_ht,
                    "taux_tva_declare": taux_tva,
                    "tva_declaree": montant_tva_declare,
                    "tva_calculee": tva_calculee,
                    "ecart": round(ecart_tva, 2),
                    "taux_implicite": round(taux_implicite, 4),
                },
                confiance=1.0
            ))
        
        # 3. Vérifier le calcul du TTC
        ttc_calcule = round(montant_ht + montant_tva_declare, 2)
        ecart_ttc = abs(ttc_calcule - montant_ttc_declare)
        
        if ecart_ttc > TOLERANCE_ARRONDI:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.MONTANT_FALSIFIE,
                gravite=NiveauGravite.CRITICAL,
                message=f"Montant TTC incohérent: {montant_ttc_declare}€ déclaré vs {ttc_calcule}€ calculé (écart: {ecart_ttc:.2f}€)",
                documents_concernes=["facture"],
                details={
                    "montant_ht": montant_ht,
                    "montant_tva": montant_tva_declare,
                    "ttc_declare": montant_ttc_declare,
                    "ttc_calcule": ttc_calcule,
                    "ecart": round(ecart_ttc, 2),
                    "surfacturation_pct": round((montant_ttc_declare - ttc_calcule) / ttc_calcule * 100, 2) if ttc_calcule > 0 else 0,
                },
                confiance=1.0
            ))
        
        # 4. Vérifier les montants négatifs
        if montant_ht < 0 or montant_tva_declare < 0 or montant_ttc_declare < 0:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.MONTANT_NEGATIF,
                gravite=NiveauGravite.ERROR,
                message="Montant négatif détecté sur la facture",
                documents_concernes=["facture"],
                details={
                    "montant_ht": montant_ht,
                    "montant_tva": montant_tva_declare,
                    "montant_ttc": montant_ttc_declare,
                }
            ))
        
        return anomalies
    
    def _validate_devis_tva(self, devis) -> List[AnomalieDetectee]:
        """Valide les calculs de TVA sur un devis"""
        anomalies = []
        
        montant_ht = devis.montant_ht
        taux_tva = devis.taux_tva
        montant_tva_declare = devis.montant_tva
        montant_ttc_declare = devis.montant_ttc
        
        # Vérifier le calcul de la TVA
        tva_calculee = round(montant_ht * taux_tva, 2)
        ecart_tva = abs(tva_calculee - montant_tva_declare)
        
        if ecart_tva > TOLERANCE_ARRONDI:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.TVA_INCOHERENTE,
                gravite=NiveauGravite.WARNING,  # WARNING pour devis, moins critique
                message=f"Montant TVA incohérent sur devis: {montant_tva_declare}€ vs {tva_calculee}€ calculé",
                documents_concernes=["devis"],
                details={
                    "montant_ht": montant_ht,
                    "taux_tva": taux_tva,
                    "tva_declaree": montant_tva_declare,
                    "tva_calculee": tva_calculee,
                    "ecart": round(ecart_tva, 2),
                }
            ))
        
        return anomalies
    
    def _validate_tva_number(self, tva_number: str, document: str) -> AnomalieDetectee | None:
        """
        Valide le format d'un numéro de TVA intracommunautaire.
        Format français: FR + 2 chiffres clé + SIREN (9 chiffres) = 13 caractères
        """
        if not tva_number:
            return None
        
        clean = re.sub(r'\s', '', tva_number).upper()
        
        # Format français: FRXX999999999
        pattern_fr = r'^FR[0-9A-Z]{2}\d{9}$'
        
        # Format européen général
        pattern_eu = r'^[A-Z]{2}[0-9A-Z]+$'
        
        if clean.startswith('FR'):
            if not re.match(pattern_fr, clean):
                return AnomalieDetectee(
                    type_anomalie=TypeAnomalie.TVA_INTRACOMMUNAUTAIRE_INVALIDE,
                    gravite=NiveauGravite.WARNING,
                    message=f"Format TVA intracommunautaire français invalide: {tva_number}",
                    documents_concernes=[document],
                    details={
                        "tva_number": tva_number,
                        "format_attendu": "FRXX999999999 (13 caractères)",
                    }
                )
            
            # Vérifier la clé de contrôle
            if len(clean) == 13:
                try:
                    cle = int(clean[2:4])
                    siren = int(clean[4:])
                    cle_calculee = (12 + 3 * (siren % 97)) % 97
                    if cle != cle_calculee:
                        return AnomalieDetectee(
                            type_anomalie=TypeAnomalie.TVA_INTRACOMMUNAUTAIRE_INVALIDE,
                            gravite=NiveauGravite.WARNING,
                            message=f"Clé de contrôle TVA invalide: {tva_number}",
                            documents_concernes=[document],
                            details={
                                "tva_number": tva_number,
                                "cle_declaree": cle,
                                "cle_calculee": cle_calculee,
                            },
                            confiance=0.9
                        )
                except ValueError:
                    pass
        
        elif not re.match(pattern_eu, clean):
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.TVA_INTRACOMMUNAUTAIRE_INVALIDE,
                gravite=NiveauGravite.WARNING,
                message=f"Format TVA intracommunautaire invalide: {tva_number}",
                documents_concernes=[document],
                details={"tva_number": tva_number}
            )
        
        return None


def calculer_tva(montant_ht: float, taux: float) -> dict:
    """
    Calcule la TVA et le TTC à partir du HT.
    Utilitaire pour vérification manuelle.
    """
    montant_tva = round(montant_ht * taux, 2)
    montant_ttc = round(montant_ht + montant_tva, 2)
    return {
        "montant_ht": montant_ht,
        "taux_tva": taux,
        "montant_tva": montant_tva,
        "montant_ttc": montant_ttc,
    }


def detecter_taux_probable(montant_ht: float, montant_tva: float) -> float | None:
    """
    Détecte le taux de TVA probable à partir du HT et de la TVA.
    Retourne None si aucun taux légal ne correspond.
    """
    if montant_ht <= 0:
        return None
    
    taux_calcule = montant_tva / montant_ht
    
    for taux_legal in TAUX_TVA_LEGAUX.keys():
        if abs(taux_calcule - taux_legal) < 0.005:  # Tolérance de 0.5%
            return taux_legal
    
    return None
