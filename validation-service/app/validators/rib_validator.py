"""
Validateur de cohérence RIB/IBAN.
Détecte les substitutions frauduleuses de coordonnées bancaires.
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


# Codes pays européens pour validation IBAN
CODES_PAYS_IBAN = {
    'FR': 27,  # France
    'DE': 22,  # Allemagne
    'ES': 24,  # Espagne
    'IT': 27,  # Italie
    'BE': 16,  # Belgique
    'NL': 18,  # Pays-Bas
    'LU': 20,  # Luxembourg
    'CH': 21,  # Suisse
    'GB': 22,  # Royaume-Uni
    'PT': 25,  # Portugal
}


class RIBValidator(BaseValidator):
    """
    Validateur RIB/IBAN - Vérifie :
    1. Format valide de l'IBAN
    2. Clé de contrôle IBAN (mod 97)
    3. Cohérence IBAN entre la facture et le RIB
    4. Format du BIC
    """
    
    @property
    def description(self) -> str:
        return "Validation des coordonnées bancaires et détection de fraude RIB"
    
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """Valide les coordonnées bancaires du dossier"""
        anomalies = []
        
        # Valider le format du RIB s'il existe
        if dossier.rib:
            iban_anomalie = self._validate_iban_format(dossier.rib.iban, "rib")
            if iban_anomalie:
                anomalies.append(iban_anomalie)
            
            bic_anomalie = self._validate_bic_format(dossier.rib.bic, "rib")
            if bic_anomalie:
                anomalies.append(bic_anomalie)
        
        # Valider l'IBAN de la facture s'il existe
        if dossier.facture and dossier.facture.iban:
            iban_anomalie = self._validate_iban_format(dossier.facture.iban, "facture")
            if iban_anomalie:
                anomalies.append(iban_anomalie)
        
        # Vérifier la cohérence IBAN entre facture et RIB
        if dossier.facture and dossier.facture.iban and dossier.rib:
            coherence_anomalie = self._validate_iban_coherence(
                dossier.facture.iban,
                dossier.rib.iban
            )
            if coherence_anomalie:
                anomalies.append(coherence_anomalie)
        
        logger.info(f"RIBValidator: {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies
    
    def _clean_iban(self, iban: str) -> str:
        """Nettoie un IBAN (supprime espaces et met en majuscules)"""
        if not iban:
            return ""
        return re.sub(r'\s', '', iban).upper()
    
    def _validate_iban_format(self, iban: str, document: str) -> AnomalieDetectee | None:
        """Valide le format et la clé de contrôle d'un IBAN"""
        
        if not iban:
            return None
        
        clean_iban = self._clean_iban(iban)
        
        # Vérifier la longueur minimale
        if len(clean_iban) < 15:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.IBAN_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"IBAN trop court dans {document}: {clean_iban}",
                documents_concernes=[document],
                details={
                    "iban": clean_iban,
                    "longueur": len(clean_iban),
                    "raison": "Longueur insuffisante"
                }
            )
        
        # Extraire le code pays
        code_pays = clean_iban[:2]
        
        # Vérifier que le code pays est valide
        if code_pays not in CODES_PAYS_IBAN:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.IBAN_INVALIDE,
                gravite=NiveauGravite.WARNING,
                message=f"Code pays IBAN non reconnu dans {document}: {code_pays}",
                documents_concernes=[document],
                details={
                    "iban": clean_iban,
                    "code_pays": code_pays,
                },
                confiance=0.8
            )
        
        # Vérifier la longueur selon le pays
        longueur_attendue = CODES_PAYS_IBAN.get(code_pays)
        if longueur_attendue and len(clean_iban) != longueur_attendue:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.IBAN_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"Longueur IBAN incorrecte pour {code_pays}: {len(clean_iban)} au lieu de {longueur_attendue}",
                documents_concernes=[document],
                details={
                    "iban": clean_iban,
                    "longueur": len(clean_iban),
                    "longueur_attendue": longueur_attendue,
                }
            )
        
        # Vérifier la clé de contrôle (modulo 97)
        if not self._validate_iban_checksum(clean_iban):
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.IBAN_INVALIDE,
                gravite=NiveauGravite.ERROR,
                message=f"Clé de contrôle IBAN invalide dans {document}",
                documents_concernes=[document],
                details={
                    "iban": clean_iban,
                    "raison": "Échec validation modulo 97"
                }
            )
        
        return None
    
    def _validate_iban_checksum(self, iban: str) -> bool:
        """
        Valide la clé de contrôle IBAN selon la norme ISO 13616.
        L'IBAN réorganisé puis converti en chiffres doit être divisible par 97.
        """
        try:
            # Réorganiser: mettre les 4 premiers caractères à la fin
            reorganized = iban[4:] + iban[:4]
            
            # Convertir les lettres en chiffres (A=10, B=11, ..., Z=35)
            numeric = ""
            for char in reorganized:
                if char.isdigit():
                    numeric += char
                elif char.isalpha():
                    numeric += str(ord(char) - ord('A') + 10)
                else:
                    return False
            
            # Vérifier modulo 97
            return int(numeric) % 97 == 1
        
        except (ValueError, TypeError):
            return False
    
    def _validate_bic_format(self, bic: str, document: str) -> AnomalieDetectee | None:
        """Valide le format d'un code BIC/SWIFT"""
        
        if not bic:
            return None
        
        clean_bic = re.sub(r'\s', '', bic).upper()
        
        # Format BIC: 8 ou 11 caractères
        # AAAABBCCXXX où:
        # - AAAA: code banque (lettres)
        # - BB: code pays (lettres)
        # - CC: code localisation (alphanumérique)
        # - XXX: code branche optionnel (alphanumérique)
        
        pattern = r'^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$'
        
        if not re.match(pattern, clean_bic):
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.IBAN_INVALIDE,
                gravite=NiveauGravite.WARNING,
                message=f"Format BIC invalide dans {document}: {clean_bic}",
                documents_concernes=[document],
                details={
                    "bic": clean_bic,
                    "format_attendu": "8 ou 11 caractères (ex: BNPAFRPP)",
                }
            )
        
        return None
    
    def _validate_iban_coherence(self, iban_facture: str, iban_rib: str) -> AnomalieDetectee | None:
        """
        Vérifie que l'IBAN de la facture correspond à celui du RIB.
        C'est une vérification critique pour détecter la fraude au RIB.
        """
        
        clean_facture = self._clean_iban(iban_facture)
        clean_rib = self._clean_iban(iban_rib)
        
        if clean_facture and clean_rib and clean_facture != clean_rib:
            return AnomalieDetectee(
                type_anomalie=TypeAnomalie.RIB_INCOHERENT,
                gravite=NiveauGravite.CRITICAL,
                message="ALERTE FRAUDE: L'IBAN de la facture ne correspond pas au RIB fourni !",
                documents_concernes=["facture", "rib"],
                details={
                    "iban_facture": clean_facture,
                    "iban_rib": clean_rib,
                    "alerte": "Possible tentative de fraude au virement (substitution de RIB)",
                },
                confiance=1.0
            )
        
        return None


def masquer_iban(iban: str) -> str:
    """Masque un IBAN pour l'affichage sécurisé (ex: FR76 XXXX XXXX XXXX 1234)"""
    clean = re.sub(r'\s', '', iban).upper()
    if len(clean) < 8:
        return clean
    
    # Garder les 4 premiers et 4 derniers caractères
    return f"{clean[:4]} {'X' * 4} {'X' * 4} {'X' * 4} {clean[-4:]}"
