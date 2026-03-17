"""
Validateur de complétude du dossier.
Vérifie que tous les documents requis sont présents.
"""

from typing import List, Set
from loguru import logger

from app.validators.base import BaseValidator
from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
    TypeAnomalie,
    NiveauGravite,
)


# Documents obligatoires pour différents types de dossiers
DOCUMENTS_OBLIGATOIRES_COMPLET = {"facture", "attestation_urssaf"}
DOCUMENTS_RECOMMANDES = {"devis", "kbis", "rib"}


class CompletenessValidator(BaseValidator):
    """
    Validateur de complétude - Vérifie :
    1. Présence des documents obligatoires (facture + attestation)
    2. Présence des documents recommandés
    3. Alertes sur les dossiers incomplets
    """
    
    def __init__(
        self,
        documents_obligatoires: Set[str] = None,
        documents_recommandes: Set[str] = None
    ):
        super().__init__()
        self.documents_obligatoires = documents_obligatoires or DOCUMENTS_OBLIGATOIRES_COMPLET
        self.documents_recommandes = documents_recommandes or DOCUMENTS_RECOMMANDES
    
    @property
    def description(self) -> str:
        return "Validation de la complétude du dossier fournisseur"
    
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide la complétude du dossier"""
        anomalies = []
        
        documents_presents = set(dossier.get_documents_presents())
        
        # Vérifier les documents obligatoires
        documents_manquants_obligatoires = self.documents_obligatoires - documents_presents
        
        if documents_manquants_obligatoires:
            # On a au moins un document obligatoire manquant
            if "facture" in documents_manquants_obligatoires:
                anomalies.append(AnomalieDetectee(
                    type_anomalie=TypeAnomalie.DOCUMENT_MANQUANT,
                    gravite=NiveauGravite.CRITICAL,
                    message="Facture manquante - Dossier incomplet",
                    documents_concernes=["facture"],
                    details={
                        "document_manquant": "facture",
                        "documents_presents": list(documents_presents),
                    }
                ))
            
            if "attestation_urssaf" in documents_manquants_obligatoires:
                anomalies.append(AnomalieDetectee(
                    type_anomalie=TypeAnomalie.DOCUMENT_MANQUANT,
                    gravite=NiveauGravite.ERROR,
                    message="Attestation URSSAF manquante - Conformité non vérifiable",
                    documents_concernes=["attestation_urssaf"],
                    details={
                        "document_manquant": "attestation_urssaf",
                        "documents_presents": list(documents_presents),
                        "risque": "Impossibilité de vérifier la régularité du fournisseur",
                    }
                ))
        
        # Vérifier les documents recommandés (seulement si les obligatoires sont là)
        if not documents_manquants_obligatoires:
            documents_manquants_recommandes = self.documents_recommandes - documents_presents
            
            if documents_manquants_recommandes:
                anomalies.append(AnomalieDetectee(
                    type_anomalie=TypeAnomalie.DOCUMENT_MANQUANT,
                    gravite=NiveauGravite.INFO,
                    message=f"Document(s) recommandé(s) manquant(s): {', '.join(documents_manquants_recommandes)}",
                    documents_concernes=list(documents_manquants_recommandes),
                    details={
                        "documents_manquants": list(documents_manquants_recommandes),
                        "documents_presents": list(documents_presents),
                    },
                    confiance=0.5
                ))
        
        # Cas particulier: facture seule sans aucun justificatif
        if documents_presents == {"facture"}:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DOCUMENT_MANQUANT,
                gravite=NiveauGravite.ERROR,
                message="Facture isolée - Aucun justificatif d'accompagnement",
                documents_concernes=["facture"],
                details={
                    "alerte": "Dossier à risque: pas de vérification possible du fournisseur",
                    "documents_manquants": list(self.documents_obligatoires - {"facture"}) + list(self.documents_recommandes),
                }
            ))
        
        logger.info(f"CompletenessValidator: {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies
    
    def get_completeness_score(self, dossier: DossierFournisseur) -> float:
        """
        Calcule un score de complétude du dossier (0.0 à 1.0).
        
        Returns:
            Score de complétude (1.0 = dossier complet)
        """
        documents_presents = set(dossier.get_documents_presents())
        
        # Poids des documents
        poids = {
            "facture": 0.30,
            "attestation_urssaf": 0.30,
            "kbis": 0.15,
            "devis": 0.10,
            "rib": 0.15,
        }
        
        score = 0.0
        for doc, p in poids.items():
            if doc in documents_presents:
                score += p
        
        return min(1.0, score)
