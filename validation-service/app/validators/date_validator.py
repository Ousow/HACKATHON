"""
Validateur des dates et périodes de validité.
Détecte les attestations expirées et les dates incohérentes.
"""

from datetime import date, timedelta
from typing import List
from loguru import logger

from app.validators.base import BaseValidator
from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
    TypeAnomalie,
    NiveauGravite,
)


# Délai de grâce pour les attestations (jours après expiration)
DELAI_GRACE_JOURS = 0

# Durée de validité maximale d'une attestation URSSAF (6 mois)
DUREE_MAX_ATTESTATION_JOURS = 180

# Alerte si l'attestation expire bientôt (jours)
SEUIL_ALERTE_EXPIRATION_JOURS = 15


class DateValidator(BaseValidator):
    """
    Validateur de dates - Vérifie :
    1. Attestation URSSAF expirée
    2. Attestation URSSAF bientôt expirée (alerte)
    3. Dates de facture futures
    4. Cohérence des dates (édition < expiration)
    5. Délai de paiement raisonnable
    """
    
    def __init__(self, date_reference: date = None):
        super().__init__()
        self.date_reference = date_reference or date.today()
    
    @property
    def description(self) -> str:
        return "Validation des dates et des périodes de validité"
    
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide les dates du dossier"""
        anomalies = []
        
        # Valider l'attestation URSSAF
        if dossier.attestation_urssaf:
            anomalies.extend(self._validate_attestation_dates(dossier.attestation_urssaf))
        
        # Valider la facture
        if dossier.facture:
            anomalies.extend(self._validate_facture_dates(dossier.facture))
        
        # Valider le devis
        if dossier.devis:
            anomalies.extend(self._validate_devis_dates(dossier.devis))
        
        # Valider le Kbis
        if dossier.kbis:
            anomalies.extend(self._validate_kbis_dates(dossier.kbis))
        
        # Valider la cohérence des dates entre documents
        anomalies.extend(self._validate_cross_document_dates(dossier))
        
        logger.info(f"DateValidator: {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies
    
    def _validate_attestation_dates(self, attestation) -> List[AnomalieDetectee]:
        """Valide les dates d'une attestation URSSAF"""
        anomalies = []
        
        date_edition = attestation.date_edition
        date_expiration = attestation.date_expiration
        
        # 1. Vérifier que l'attestation n'est pas expirée
        if date_expiration < self.date_reference:
            jours_expires = (self.date_reference - date_expiration).days
            
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.ATTESTATION_EXPIREE,
                gravite=NiveauGravite.CRITICAL,
                message=f"Attestation URSSAF expirée depuis {jours_expires} jour(s) (expiration: {date_expiration.strftime('%d/%m/%Y')})",
                documents_concernes=["attestation_urssaf"],
                details={
                    "date_edition": date_edition.isoformat(),
                    "date_expiration": date_expiration.isoformat(),
                    "date_reference": self.date_reference.isoformat(),
                    "jours_expires": jours_expires,
                },
                confiance=1.0
            ))
        
        # 2. Alerte si l'attestation expire bientôt
        elif (date_expiration - self.date_reference).days <= SEUIL_ALERTE_EXPIRATION_JOURS:
            jours_restants = (date_expiration - self.date_reference).days
            
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.ATTESTATION_EXPIREE,
                gravite=NiveauGravite.WARNING,
                message=f"Attestation URSSAF expire dans {jours_restants} jour(s) (expiration: {date_expiration.strftime('%d/%m/%Y')})",
                documents_concernes=["attestation_urssaf"],
                details={
                    "date_expiration": date_expiration.isoformat(),
                    "jours_restants": jours_restants,
                },
                confiance=1.0
            ))
        
        # 3. Vérifier la cohérence édition < expiration
        if date_edition >= date_expiration:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.ERROR,
                message="Date d'édition postérieure ou égale à la date d'expiration",
                documents_concernes=["attestation_urssaf"],
                details={
                    "date_edition": date_edition.isoformat(),
                    "date_expiration": date_expiration.isoformat(),
                }
            ))
        
        # 4. Vérifier que la durée de validité est raisonnable
        duree_validite = (date_expiration - date_edition).days
        if duree_validite > DUREE_MAX_ATTESTATION_JOURS:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.WARNING,
                message=f"Durée de validité inhabituellement longue: {duree_validite} jours",
                documents_concernes=["attestation_urssaf"],
                details={
                    "duree_validite_jours": duree_validite,
                    "duree_max_attendue": DUREE_MAX_ATTESTATION_JOURS,
                },
                confiance=0.7
            ))
        
        # 5. Vérifier que l'édition n'est pas dans le futur
        if date_edition > self.date_reference:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.ERROR,
                message=f"Date d'édition dans le futur: {date_edition.strftime('%d/%m/%Y')}",
                documents_concernes=["attestation_urssaf"],
                details={
                    "date_edition": date_edition.isoformat(),
                    "date_reference": self.date_reference.isoformat(),
                }
            ))
        
        return anomalies
    
    def _validate_facture_dates(self, facture) -> List[AnomalieDetectee]:
        """Valide les dates d'une facture"""
        anomalies = []
        
        date_emission = facture.date_emission
        date_echeance = facture.date_echeance
        
        # 1. Vérifier que la date d'émission n'est pas dans le futur
        if date_emission > self.date_reference:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.ERROR,
                message=f"Date d'émission de facture dans le futur: {date_emission.strftime('%d/%m/%Y')}",
                documents_concernes=["facture"],
                details={
                    "date_emission": date_emission.isoformat(),
                    "date_reference": self.date_reference.isoformat(),
                }
            ))
        
        # 2. Vérifier la cohérence émission < échéance
        if date_echeance and date_emission > date_echeance:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.ERROR,
                message="Date d'émission postérieure à la date d'échéance",
                documents_concernes=["facture"],
                details={
                    "date_emission": date_emission.isoformat(),
                    "date_echeance": date_echeance.isoformat(),
                }
            ))
        
        # 3. Vérifier que le délai de paiement n'est pas excessif (>90 jours)
        if date_echeance:
            delai = (date_echeance - date_emission).days
            if delai > 90:
                anomalies.append(AnomalieDetectee(
                    type_anomalie=TypeAnomalie.DATE_FUTURE,
                    gravite=NiveauGravite.INFO,
                    message=f"Délai de paiement inhabituel: {delai} jours (max légal: 60 jours en B2B)",
                    documents_concernes=["facture"],
                    details={
                        "delai_jours": delai,
                        "delai_legal_max": 60,
                    },
                    confiance=0.6
                ))
        
        return anomalies
    
    def _validate_devis_dates(self, devis) -> List[AnomalieDetectee]:
        """Valide les dates d'un devis"""
        anomalies = []
        
        date_emission = devis.date_emission
        date_validite = devis.date_validite
        
        # Vérifier la cohérence des dates
        if date_validite and date_emission > date_validite:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.DATE_FUTURE,
                gravite=NiveauGravite.WARNING,
                message="Devis avec date d'émission postérieure à la date de validité",
                documents_concernes=["devis"],
                details={
                    "date_emission": date_emission.isoformat(),
                    "date_validite": date_validite.isoformat(),
                }
            ))
        
        return anomalies
    
    def _validate_kbis_dates(self, kbis) -> List[AnomalieDetectee]:
        """Valide les dates d'un Kbis"""
        anomalies = []
        
        date_extrait = kbis.date_extrait
        
        # Vérifier que le Kbis n'est pas trop ancien (>3 mois)
        age_kbis = (self.date_reference - date_extrait).days
        if age_kbis > 90:
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.ATTESTATION_EXPIREE,
                gravite=NiveauGravite.INFO,
                message=f"Extrait Kbis ancien: {age_kbis} jours (recommandé: <3 mois)",
                documents_concernes=["kbis"],
                details={
                    "date_extrait": date_extrait.isoformat(),
                    "age_jours": age_kbis,
                },
                confiance=0.5
            ))
        
        return anomalies
    
    def _validate_cross_document_dates(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide la cohérence des dates entre différents documents"""
        anomalies = []
        
        # Si on a une facture et une attestation, vérifier que l'attestation est valide à la date de la facture
        if dossier.facture and dossier.attestation_urssaf:
            date_facture = dossier.facture.date_emission
            date_expiration_attestation = dossier.attestation_urssaf.date_expiration
            
            if date_facture > date_expiration_attestation:
                jours_ecart = (date_facture - date_expiration_attestation).days
                anomalies.append(AnomalieDetectee(
                    type_anomalie=TypeAnomalie.ATTESTATION_EXPIREE,
                    gravite=NiveauGravite.CRITICAL,
                    message=f"Attestation URSSAF expirée ({jours_ecart} jours) au moment de la facturation",
                    documents_concernes=["facture", "attestation_urssaf"],
                    details={
                        "date_facture": date_facture.isoformat(),
                        "date_expiration_attestation": date_expiration_attestation.isoformat(),
                        "ecart_jours": jours_ecart,
                    },
                    confiance=1.0
                ))
        
        return anomalies
