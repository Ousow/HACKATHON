"""
Validateur de cohérence SIRET entre documents.
Détecte les incohérences de SIRET entre facture, attestation URSSAF, Kbis, etc.
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


class SIRETValidator(BaseValidator):
    """
    Validateur SIRET - Vérifie :
    1. Format valide du SIRET (14 chiffres)
    2. Algorithme de Luhn (validité mathématique)
    3. Cohérence du SIRET entre tous les documents d'un même fournisseur
    """
    
    @property
    def description(self) -> str:
        return "Validation du format et de la cohérence des numéros SIRET"
    
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide les SIRET du dossier"""
        anomalies = []
        sirets_par_document = {}
        
        # Collecter tous les SIRET des documents
        if dossier.facture:
            siret = self._clean_siret(dossier.facture.siret_emetteur)
            sirets_par_document["facture"] = siret
            
            # Vérifier le format et la validité
            format_anomalie = self._validate_format(siret, "facture")
            if format_anomalie:
                anomalies.append(format_anomalie)
        
        if dossier.attestation_urssaf:
            siret = self._clean_siret(dossier.attestation_urssaf.siret)
            sirets_par_document["attestation_urssaf"] = siret
            
            format_anomalie = self._validate_format(siret, "attestation_urssaf")
            if format_anomalie:
                anomalies.append(format_anomalie)
        
        if dossier.kbis:
            siret = self._clean_siret(dossier.kbis.siret_siege)
            sirets_par_document["kbis"] = siret
            
            format_anomalie = self._validate_format(siret, "kbis")
            if format_anomalie:
                anomalies.append(format_anomalie)
        
        if dossier.devis:
            siret = self._clean_siret(dossier.devis.siret_emetteur)
            sirets_par_document["devis"] = siret
            
            format_anomalie = self._validate_format(siret, "devis")
            if format_anomalie:
                anomalies.append(format_anomalie)
        
        if dossier.rib and dossier.rib.siret:
            siret = self._clean_siret(dossier.rib.siret)
            sirets_par_document["rib"] = siret
            
            format_anomalie = self._validate_format(siret, "rib")
            if format_anomalie:
                anomalies.append(format_anomalie)
        
        # Vérifier la cohérence inter-documents
        coherence_anomalies = self._validate_coherence(sirets_par_document)
        anomalies.extend(coherence_anomalies)
        
        logger.info(f"SIRETValidator: {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies
    
    def _clean_siret(self, siret: str) -> str:
        """Nettoie un SIRET (supprime espaces et caractères non numériques)"""
        if siret is None:
            return ""
        return re.sub(r'\D', '', siret)
    
    def _validate_format(self, siret: str, document: str) -> AnomalieDetectee | None:
        """Valide le format d'un SIRET"""
        
        if not siret:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.SIRET_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"SIRET manquant dans le document {document}",
                documents_concernes=[document],
                details={"siret": None, "raison": "SIRET absent"}
            )
        
        # Vérifier la longueur (14 chiffres)
        if len(siret) != 14:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.SIRET_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"SIRET invalide ({len(siret)} chiffres au lieu de 14) dans {document}",
                documents_concernes=[document],
                details={"siret": siret, "longueur": len(siret), "raison": "Longueur incorrecte"}
            )
        
        # Vérifier que ce sont bien des chiffres
        if not siret.isdigit():
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.SIRET_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"SIRET contient des caractères non numériques dans {document}",
                documents_concernes=[document],
                details={"siret": siret, "raison": "Caractères non numériques"}
            )
        
        # Vérifier l'algorithme de Luhn
        if not self._validate_luhn(siret):
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.SIRET_INVALIDE,
                gravite=NiveauGravite.WARNING,
                message=f"SIRET échoue à la vérification Luhn dans {document}",
                documents_concernes=[document],
                details={"siret": siret, "raison": "Échec validation Luhn"},
                confiance=0.9
            )
        
        return None
    
    def _validate_luhn(self, siret: str) -> bool:
        """
        Valide un SIRET avec l'algorithme de Luhn.
        Note: En France, le SIRET utilise une variante de Luhn.
        """
        try:
            total = 0
            for i, char in enumerate(siret):
                digit = int(char)
                # Position impaire (1, 3, 5...) : multiplier par 2
                if i % 2 == 1:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                total += digit
            return total % 10 == 0
        except ValueError:
            return False
    
    def _validate_coherence(self, sirets_par_document: dict) -> List[AnomalieDetectee]:
        """Vérifie que tous les documents ont le même SIRET fournisseur"""
        anomalies = []
        
        if len(sirets_par_document) < 2:
            # Pas assez de documents pour comparer
            return anomalies
        
        # Extraire les SIRET uniques non vides
        sirets_uniques = set(s for s in sirets_par_document.values() if s)
        
        if len(sirets_uniques) > 1:
            # Incohérence détectée !
            docs_par_siret = {}
            for doc, siret in sirets_par_document.items():
                if siret:
                    if siret not in docs_par_siret:
                        docs_par_siret[siret] = []
                    docs_par_siret[siret].append(doc)
            
            # Trouver le SIRET majoritaire (probable vrai SIRET)
            siret_majoritaire = max(docs_par_siret.keys(), key=lambda s: len(docs_par_siret[s]))
            
            for siret, docs in docs_par_siret.items():
                if siret != siret_majoritaire:
                    anomalies.append(AnomalieDetectee(
                        type_anomalie=TypeAnomalie.SIRET_INCOHERENT,
                        gravite=NiveauGravite.CRITICAL,
                        message=f"SIRET incohérent détecté : {siret} dans {docs} diffère du SIRET {siret_majoritaire}",
                        documents_concernes=docs + docs_par_siret[siret_majoritaire],
                        details={
                            "siret_attendu": siret_majoritaire,
                            "siret_trouve": siret,
                            "documents_attendus": docs_par_siret[siret_majoritaire],
                            "documents_incoherents": docs,
                        },
                        confiance=1.0
                    ))
            
            logger.warning(f"Incohérence SIRET détectée: {sirets_uniques}")
        
        return anomalies


def validate_siren_from_siret(siret: str) -> str:
    """Extrait le SIREN (9 premiers chiffres) du SIRET"""
    clean = re.sub(r'\D', '', siret)
    if len(clean) >= 9:
        return clean[:9]
    return ""


def sirets_same_company(siret1: str, siret2: str) -> bool:
    """
    Vérifie si deux SIRET appartiennent à la même entreprise (même SIREN).
    Utile pour détecter si deux établissements d'une même entreprise sont utilisés.
    """
    siren1 = validate_siren_from_siret(siret1)
    siren2 = validate_siren_from_siret(siret2)
    return siren1 == siren2 and siren1 != ""
