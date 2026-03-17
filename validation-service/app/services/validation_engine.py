"""
Moteur de validation principal.
Orchestre tous les validateurs et le modèle ML pour valider un dossier fournisseur.
"""

import time
from datetime import date
from typing import List, Optional
from loguru import logger

from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
    ResultatValidation,
)
from app.validators import (
    BaseValidator,
    SIRETValidator,
    TVAValidator,
    DateValidator,
    RIBValidator,
    CompletenessValidator,
)
from app.models.anomaly_detector import AnomalyDetector, get_anomaly_detector


class ValidationEngine:
    """
    Moteur de validation intelligent.
    
    Combine :
    - Validateurs basés sur des règles métier (SIRET, TVA, dates, etc.)
    - Modèle de Machine Learning pour la détection d'anomalies
    
    Workflow:
    1. Validation de la complétude du dossier
    2. Validation des règles métier par chaque validateur
    3. Détection d'anomalies par ML
    4. Agrégation des résultats
    """
    
    def __init__(
        self,
        date_reference: date = None,
        use_ml: bool = True,
        ml_threshold: float = 0.5
    ):
        """
        Initialise le moteur de validation.
        
        Args:
            date_reference: Date de référence pour les calculs (défaut: aujourd'hui)
            use_ml: Activer la détection ML (défaut: True)
            ml_threshold: Seuil de détection ML (défaut: 0.5)
        """
        self.date_reference = date_reference or date.today()
        self.use_ml = use_ml
        self.ml_threshold = ml_threshold
        
        # Initialiser les validateurs
        self.validators: List[BaseValidator] = [
            CompletenessValidator(),
            SIRETValidator(),
            TVAValidator(),
            DateValidator(date_reference=self.date_reference),
            RIBValidator(),
        ]
        
        # Initialiser le détecteur ML
        self.anomaly_detector: Optional[AnomalyDetector] = None
        if use_ml:
            self.anomaly_detector = get_anomaly_detector()
        
        logger.info(f"ValidationEngine initialisé avec {len(self.validators)} validateurs, ML={use_ml}")
    
    def add_validator(self, validator: BaseValidator) -> None:
        """Ajoute un validateur personnalisé"""
        self.validators.append(validator)
        logger.info(f"Validateur ajouté: {validator.name}")
    
    def validate(self, dossier: DossierFournisseur) -> ResultatValidation:
        """
        Valide un dossier fournisseur complet.
        
        Args:
            dossier: Le dossier à valider
            
        Returns:
            ResultatValidation avec toutes les anomalies détectées
        """
        start_time = time.time()
        all_anomalies: List[AnomalieDetectee] = []
        
        logger.info(f"Validation du dossier {dossier.dossier_id}...")
        
        # 1. Exécuter tous les validateurs de règles
        for validator in self.validators:
            try:
                if validator.can_validate(dossier):
                    anomalies = validator.validate(dossier)
                    all_anomalies.extend(anomalies)
                    logger.debug(f"{validator.name}: {len(anomalies)} anomalie(s)")
            except Exception as e:
                logger.error(f"Erreur dans {validator.name}: {e}")
                # Continuer avec les autres validateurs
        
        # 2. Détection ML (si activée)
        if self.use_ml and self.anomaly_detector:
            try:
                ml_anomalies = self.anomaly_detector.detect(
                    dossier,
                    threshold=self.ml_threshold
                )
                
                # Éviter les doublons avec les règles
                for ml_anomalie in ml_anomalies:
                    # Si le ML détecte quelque chose de nouveau
                    if not self._is_already_detected(ml_anomalie, all_anomalies):
                        all_anomalies.append(ml_anomalie)
                
                logger.debug(f"ML Detector: {len(ml_anomalies)} anomalie(s)")
            except Exception as e:
                logger.error(f"Erreur détection ML: {e}")
        
        # 3. Construire le résultat
        duree_ms = (time.time() - start_time) * 1000
        
        result = ResultatValidation(
            dossier_id=dossier.dossier_id,
            est_valide=True,  # Sera recalculé
            score_confiance=1.0,  # Sera recalculé
            anomalies=all_anomalies,
            documents_analyses=dossier.get_documents_presents(),
            documents_manquants=self._get_documents_manquants(dossier),
            duree_validation_ms=round(duree_ms, 2),
        )
        
        # Calculer les statistiques
        result.compute_stats()
        
        logger.info(
            f"Validation terminée: {result.nb_anomalies} anomalie(s), "
            f"valide={result.est_valide}, score={result.score_confiance:.2f}"
        )
        
        return result
    
    def _is_already_detected(
        self,
        new_anomalie: AnomalieDetectee,
        existing: List[AnomalieDetectee]
    ) -> bool:
        """Vérifie si une anomalie similaire existe déjà"""
        for a in existing:
            # Considérer comme doublon si même type et mêmes documents
            if (a.type_anomalie == new_anomalie.type_anomalie and
                set(a.documents_concernes) == set(new_anomalie.documents_concernes)):
                return True
        return False
    
    def _get_documents_manquants(self, dossier: DossierFournisseur) -> List[str]:
        """Identifie les documents manquants"""
        presents = set(dossier.get_documents_presents())
        tous_documents = {"facture", "devis", "attestation_urssaf", "kbis", "rib"}
        return list(tous_documents - presents)
    
    def validate_batch(
        self,
        dossiers: List[DossierFournisseur]
    ) -> List[ResultatValidation]:
        """
        Valide un lot de dossiers.
        
        Args:
            dossiers: Liste des dossiers à valider
            
        Returns:
            Liste des résultats de validation
        """
        logger.info(f"Validation batch de {len(dossiers)} dossiers...")
        
        results = []
        for i, dossier in enumerate(dossiers):
            result = self.validate(dossier)
            results.append(result)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Progression: {i + 1}/{len(dossiers)} dossiers traités")
        
        # Statistiques globales
        nb_valides = sum(1 for r in results if r.est_valide)
        nb_invalides = len(results) - nb_valides
        
        logger.info(
            f"Batch terminé: {nb_valides} valides, {nb_invalides} invalides "
            f"({nb_invalides/len(results)*100:.1f}% d'anomalies)"
        )
        
        return results
    
    def get_stats(self, results: List[ResultatValidation]) -> dict:
        """
        Calcule des statistiques sur les résultats de validation.
        
        Returns:
            Dict avec les statistiques agrégées
        """
        if not results:
            return {}
        
        total = len(results)
        valides = sum(1 for r in results if r.est_valide)
        
        # Comptage par type d'anomalie
        anomalies_par_type = {}
        for r in results:
            for a in r.anomalies:
                t = a.type_anomalie
                if t not in anomalies_par_type:
                    anomalies_par_type[t] = 0
                anomalies_par_type[t] += 1
        
        # Score moyen
        score_moyen = sum(r.score_confiance for r in results) / total
        
        return {
            "total_dossiers": total,
            "dossiers_valides": valides,
            "dossiers_invalides": total - valides,
            "taux_validite": round(valides / total * 100, 2),
            "score_confiance_moyen": round(score_moyen, 3),
            "anomalies_par_type": anomalies_par_type,
            "total_anomalies": sum(r.nb_anomalies for r in results),
        }


# Instance singleton
_engine_instance: Optional[ValidationEngine] = None


def get_validation_engine(
    date_reference: date = None,
    use_ml: bool = True
) -> ValidationEngine:
    """Retourne l'instance singleton du moteur de validation"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ValidationEngine(
            date_reference=date_reference,
            use_ml=use_ml
        )
    return _engine_instance
