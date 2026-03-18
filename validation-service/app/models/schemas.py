"""
Schémas Pydantic pour les données extraites des documents.
Ces modèles représentent les informations structurées après OCR/NLP.
"""

from datetime import date
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class DocumentType(str, Enum):
    """Types de documents supportés"""
    FACTURE = "facture"
    DEVIS = "devis"
    ATTESTATION_URSSAF = "attestation_urssaf"
    KBIS = "kbis"
    RIB = "rib"


class TypeAnomalie(str, Enum):
    """Types d'anomalies détectables"""
    SIRET_INCOHERENT = "siret_incoherent"
    TVA_INCOHERENTE = "tva_incoherente"
    MONTANT_FALSIFIE = "montant_falsifie"
    ATTESTATION_EXPIREE = "attestation_expiree"
    RIB_INCOHERENT = "rib_incoherent"
    DOCUMENT_MANQUANT = "document_manquant"
    SIRET_INVALIDE = "siret_invalide"
    TVA_INTRACOMMUNAUTAIRE_INVALIDE = "tva_intracommunautaire_invalide"
    IBAN_INVALIDE = "iban_invalide"
    DATE_FUTURE = "date_future"
    MONTANT_NEGATIF = "montant_negatif"
    MULTI_ANOMALIES = "multi_anomalies"


class NiveauGravite(str, Enum):
    """Niveau de gravité d'une anomalie"""
    INFO = "info"           # Information, pas bloquant
    WARNING = "warning"     # Attention requise
    ERROR = "error"         # Erreur à corriger
    CRITICAL = "critical"   # Fraude potentielle, bloquant


class DocumentExtrait(BaseModel):
    """Classe de base pour tous les documents extraits"""
    type_document: DocumentType
    fichier_source: str
    date_extraction: date = Field(default_factory=date.today)
    confiance_ocr: float = Field(ge=0.0, le=1.0, default=0.85)
    
    class Config:
        use_enum_values = True


class FactureExtrait(DocumentExtrait):
    """Données extraites d'une facture"""
    type_document: DocumentType = DocumentType.FACTURE
    
    # Identifiants
    numero_facture: str
    siret_emetteur: str
    siret_destinataire: Optional[str] = None
    tva_intracommunautaire: Optional[str] = None
    
    # Montants
    montant_ht: float = Field(ge=0)
    taux_tva: float = Field(ge=0, le=1)  # 0.20 pour 20%
    montant_tva: float = Field(ge=0)
    montant_ttc: float = Field(ge=0)
    
    # Dates
    date_emission: date
    date_echeance: Optional[date] = None
    
    # Coordonnées bancaires (optionnel)
    iban: Optional[str] = None
    bic: Optional[str] = None
    
    # Informations entreprise
    nom_emetteur: Optional[str] = None
    adresse_emetteur: Optional[str] = None
    
    @field_validator('siret_emetteur', 'siret_destinataire')
    @classmethod
    def validate_siret_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Nettoyer le SIRET (enlever espaces)
        clean = re.sub(r'\s', '', v)
        if len(clean) != 14 or not clean.isdigit():
            # On garde la valeur mais on la signale
            pass
        return clean


class AttestationURSSAFExtrait(DocumentExtrait):
    """Données extraites d'une attestation URSSAF"""
    type_document: DocumentType = DocumentType.ATTESTATION_URSSAF
    
    # Identifiants
    numero_attestation: str
    siret: str
    tva_intracommunautaire: Optional[str] = None
    
    # Dates
    date_edition: date
    date_expiration: date
    
    # Informations entreprise
    raison_sociale: Optional[str] = None
    forme_juridique: Optional[str] = None
    adresse: Optional[str] = None
    code_ape: Optional[str] = None
    
    @field_validator('siret')
    @classmethod
    def validate_siret_format(cls, v: str) -> str:
        clean = re.sub(r'\s', '', v)
        return clean


class DevisExtrait(DocumentExtrait):
    """Données extraites d'un devis"""
    type_document: DocumentType = DocumentType.DEVIS
    
    # Identifiants
    numero_devis: str
    siret_emetteur: str
    
    # Montants
    montant_ht: float = Field(ge=0)
    taux_tva: float = Field(ge=0, le=1)
    montant_tva: float = Field(ge=0)
    montant_ttc: float = Field(ge=0)
    
    # Dates
    date_emission: date
    date_validite: Optional[date] = None


class KbisExtrait(DocumentExtrait):
    """Données extraites d'un extrait Kbis"""
    type_document: DocumentType = DocumentType.KBIS
    
    # Identifiants
    siren: str
    siret_siege: str
    numero_rcs: Optional[str] = None
    
    # Informations entreprise
    raison_sociale: str
    forme_juridique: str
    capital_social: Optional[float] = None
    date_immatriculation: Optional[date] = None
    adresse_siege: Optional[str] = None
    code_ape: Optional[str] = None
    activite_principale: Optional[str] = None
    
    # Date du document
    date_extrait: date
    
    @field_validator('siren')
    @classmethod
    def validate_siren(cls, v: str) -> str:
        clean = re.sub(r'\s', '', v)
        if len(clean) != 9:
            pass  # Signalé ailleurs
        return clean


class RIBExtrait(DocumentExtrait):
    """Données extraites d'un RIB"""
    type_document: DocumentType = DocumentType.RIB
    
    # Coordonnées bancaires
    iban: str
    bic: str
    
    # Informations titulaire
    titulaire: str
    siret: Optional[str] = None
    
    # Informations banque
    banque: Optional[str] = None
    
    @field_validator('iban')
    @classmethod
    def validate_iban_format(cls, v: str) -> str:
        clean = re.sub(r'\s', '', v).upper()
        return clean


class DossierFournisseur(BaseModel):
    """
    Ensemble des documents d'un fournisseur à valider.
    Représente un dossier complet ou partiel.
    """
    dossier_id: str
    fournisseur_nom: Optional[str] = None
    
    # Documents (tous optionnels car un dossier peut être incomplet)
    facture: Optional[FactureExtrait] = None
    devis: Optional[DevisExtrait] = None
    attestation_urssaf: Optional[AttestationURSSAFExtrait] = None
    kbis: Optional[KbisExtrait] = None
    rib: Optional[RIBExtrait] = None
    
    # Métadonnées
    date_soumission: date = Field(default_factory=date.today)
    
    def get_documents_presents(self) -> List[str]:
        """Retourne la liste des types de documents présents"""
        docs = []
        if self.facture:
            docs.append("facture")
        if self.devis:
            docs.append("devis")
        if self.attestation_urssaf:
            docs.append("attestation_urssaf")
        if self.kbis:
            docs.append("kbis")
        if self.rib:
            docs.append("rib")
        return docs


class AnomalieDetectee(BaseModel):
    """Représente une anomalie détectée lors de la validation"""
    type_anomalie: TypeAnomalie
    gravite: NiveauGravite
    message: str
    details: Optional[dict] = None
    documents_concernes: List[str] = Field(default_factory=list)
    confiance: float = Field(ge=0.0, le=1.0, default=1.0)
    
    # Pour le ML
    score_anomalie: Optional[float] = None  # Score du modèle ML si applicable
    
    class Config:
        use_enum_values = True


class ResultatValidation(BaseModel):
    """Résultat complet de la validation d'un dossier"""
    dossier_id: str
    est_valide: bool
    score_confiance: float = Field(ge=0.0, le=1.0)
    
    # Anomalies détectées
    anomalies: List[AnomalieDetectee] = Field(default_factory=list)
    nb_anomalies: int = 0
    
    # Statistiques par gravité
    nb_critiques: int = 0
    nb_erreurs: int = 0
    nb_warnings: int = 0
    nb_infos: int = 0
    
    # Documents analysés
    documents_analyses: List[str] = Field(default_factory=list)
    documents_manquants: List[str] = Field(default_factory=list)
    
    # Métadonnées
    date_validation: date = Field(default_factory=date.today)
    duree_validation_ms: Optional[float] = None
    
    def compute_stats(self):
        """Calcule les statistiques à partir des anomalies"""
        self.nb_anomalies = len(self.anomalies)
        self.nb_critiques = sum(1 for a in self.anomalies if a.gravite == NiveauGravite.CRITICAL)
        self.nb_erreurs = sum(1 for a in self.anomalies if a.gravite == NiveauGravite.ERROR)
        self.nb_warnings = sum(1 for a in self.anomalies if a.gravite == NiveauGravite.WARNING)
        self.nb_infos = sum(1 for a in self.anomalies if a.gravite == NiveauGravite.INFO)
        
        # Un dossier est invalide s'il y a au moins une anomalie critique ou erreur
        self.est_valide = (self.nb_critiques == 0 and self.nb_erreurs == 0)
        
        # Score de confiance inversement proportionnel aux anomalies
        if self.nb_anomalies == 0:
            self.score_confiance = 1.0
        else:
            penalty = (self.nb_critiques * 0.4 + self.nb_erreurs * 0.25 + 
                      self.nb_warnings * 0.1 + self.nb_infos * 0.02)
            self.score_confiance = max(0.0, 1.0 - penalty)
