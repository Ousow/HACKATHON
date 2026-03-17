"""
Classe de base pour tous les validateurs.
Définit l'interface commune et les méthodes utilitaires.
"""

from abc import ABC, abstractmethod
from typing import List
from loguru import logger

from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
)


class BaseValidator(ABC):
    """
    Classe abstraite de base pour tous les validateurs.
    Chaque validateur vérifie un aspect spécifique du dossier.
    """
    
    def __init__(self):
        self.name = self.__class__.__name__
        logger.debug(f"Initialisation du validateur: {self.name}")
    
    @abstractmethod
    def validate(self, dossier: DossierFournisseur) -> List[AnomalieDetectee]:
        """
        Valide le dossier et retourne la liste des anomalies détectées.
        
        Args:
            dossier: Le dossier fournisseur à valider
            
        Returns:
            Liste des anomalies détectées (vide si tout est correct)
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description du validateur"""
        pass
    
    def can_validate(self, dossier: DossierFournisseur) -> bool:
        """
        Vérifie si le validateur peut s'appliquer au dossier.
        Par défaut, retourne True.
        
        Args:
            dossier: Le dossier à vérifier
            
        Returns:
            True si le validateur peut s'appliquer
        """
        return True
    
    def __repr__(self) -> str:
        return f"<{self.name}: {self.description}>"
