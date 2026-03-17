"""
Modèle de Machine Learning pour la détection d'anomalies.
Utilise Isolation Forest pour identifier les dossiers suspects.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from datetime import date
from pathlib import Path
import joblib
from loguru import logger

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.models.schemas import (
    DossierFournisseur,
    AnomalieDetectee,
    TypeAnomalie,
    NiveauGravite,
)


class AnomalyDetector:
    """
    Détecteur d'anomalies basé sur Isolation Forest.
    
    Ce modèle apprend le comportement "normal" des dossiers fournisseurs
    et signale les dossiers qui s'écartent significativement de cette norme.
    
    Features utilisées :
    - Ratio TVA / HT
    - Ratio TTC / HT
    - Écart entre TVA déclarée et calculée
    - Écart entre TTC déclaré et calculé
    - Durée de validité de l'attestation
    - Jours avant expiration attestation
    - Délai de paiement facture
    - Score de complétude du dossier
    """
    
    def __init__(
        self,
        contamination: float = 0.1,  # 10% d'anomalies attendues
        random_state: int = 42,
        model_path: Optional[str] = None
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.model_path = model_path
        
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
            max_samples='auto',
            bootstrap=False,
            n_jobs=-1,
        )
        
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = []
        
        # Charger le modèle s'il existe
        if model_path and Path(model_path).exists():
            self.load_model(model_path)
    
    def extract_features(self, dossier: DossierFournisseur) -> dict:
        """
        Extrait les features numériques d'un dossier pour le ML.
        
        Returns:
            dict avec les features extraites
        """
        features = {}
        
        # Features liées à la facture
        if dossier.facture:
            f = dossier.facture
            
            # Ratios de montants
            if f.montant_ht > 0:
                features["ratio_tva_ht"] = f.montant_tva / f.montant_ht
                features["ratio_ttc_ht"] = f.montant_ttc / f.montant_ht
                
                # Écart TVA
                tva_calculee = f.montant_ht * f.taux_tva
                features["ecart_tva_abs"] = abs(f.montant_tva - tva_calculee)
                features["ecart_tva_pct"] = abs(f.montant_tva - tva_calculee) / f.montant_ht
                
                # Écart TTC
                ttc_calcule = f.montant_ht + f.montant_tva
                features["ecart_ttc_abs"] = abs(f.montant_ttc - ttc_calcule)
                features["ecart_ttc_pct"] = abs(f.montant_ttc - ttc_calcule) / f.montant_ht
            else:
                features["ratio_tva_ht"] = 0
                features["ratio_ttc_ht"] = 0
                features["ecart_tva_abs"] = 0
                features["ecart_tva_pct"] = 0
                features["ecart_ttc_abs"] = 0
                features["ecart_ttc_pct"] = 0
            
            # Taux TVA
            features["taux_tva"] = f.taux_tva
            
            # Délai de paiement
            if f.date_echeance:
                features["delai_paiement_jours"] = (f.date_echeance - f.date_emission).days
            else:
                features["delai_paiement_jours"] = 30  # Valeur par défaut
            
            # Montant (log pour normaliser)
            features["log_montant_ttc"] = np.log1p(f.montant_ttc)
        else:
            # Valeurs par défaut si pas de facture
            features["ratio_tva_ht"] = 0.2
            features["ratio_ttc_ht"] = 1.2
            features["ecart_tva_abs"] = 0
            features["ecart_tva_pct"] = 0
            features["ecart_ttc_abs"] = 0
            features["ecart_ttc_pct"] = 0
            features["taux_tva"] = 0.2
            features["delai_paiement_jours"] = 30
            features["log_montant_ttc"] = 0
        
        # Features liées à l'attestation URSSAF
        if dossier.attestation_urssaf:
            a = dossier.attestation_urssaf
            
            # Durée de validité
            features["duree_validite_jours"] = (a.date_expiration - a.date_edition).days
            
            # Jours avant/après expiration (négatif si expirée)
            today = date.today()
            features["jours_avant_expiration"] = (a.date_expiration - today).days
            features["attestation_expiree"] = 1 if a.date_expiration < today else 0
        else:
            features["duree_validite_jours"] = 90  # Défaut
            features["jours_avant_expiration"] = 45  # Défaut
            features["attestation_expiree"] = 0
        
        # Score de complétude
        docs_presents = dossier.get_documents_presents()
        features["nb_documents"] = len(docs_presents)
        features["has_facture"] = 1 if "facture" in docs_presents else 0
        features["has_attestation"] = 1 if "attestation_urssaf" in docs_presents else 0
        features["has_kbis"] = 1 if "kbis" in docs_presents else 0
        features["has_rib"] = 1 if "rib" in docs_presents else 0
        features["has_devis"] = 1 if "devis" in docs_presents else 0
        
        return features
    
    def _features_to_array(self, features: dict) -> np.ndarray:
        """Convertit les features dict en array numpy"""
        if not self.feature_names:
            self.feature_names = sorted(features.keys())
        
        return np.array([features.get(name, 0) for name in self.feature_names])
    
    def train(self, dossiers: List[DossierFournisseur]) -> None:
        """
        Entraîne le modèle sur une liste de dossiers.
        
        Args:
            dossiers: Liste de dossiers fournisseurs (supposés principalement légitimes)
        """
        logger.info(f"Entraînement du détecteur d'anomalies sur {len(dossiers)} dossiers...")
        
        # Extraire les features
        features_list = []
        for dossier in dossiers:
            features = self.extract_features(dossier)
            features_list.append(features)
        
        # Convertir en DataFrame pour faciliter le traitement
        df = pd.DataFrame(features_list)
        self.feature_names = list(df.columns)
        
        # Normaliser
        X = self.scaler.fit_transform(df.values)
        
        # Entraîner
        self.model.fit(X)
        self.is_trained = True
        
        logger.info(f"Modèle entraîné avec {len(self.feature_names)} features")
    
    def predict_anomaly_score(self, dossier: DossierFournisseur) -> float:
        """
        Calcule le score d'anomalie d'un dossier.
        
        Returns:
            Score entre 0.0 (normal) et 1.0 (très anormal)
        """
        if not self.is_trained:
            logger.warning("Modèle non entraîné, utilisation des règles heuristiques")
            return self._heuristic_score(dossier)
        
        features = self.extract_features(dossier)
        X = self._features_to_array(features).reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        
        # Isolation Forest retourne -1 pour anomalie, 1 pour normal
        # et decision_function retourne le score brut (négatif = anomalie)
        raw_score = self.model.decision_function(X_scaled)[0]
        
        # Convertir en score 0-1 (1 = anomalie)
        # Les scores bruts sont généralement entre -0.5 et 0.5
        normalized_score = max(0.0, min(1.0, 0.5 - raw_score))
        
        return normalized_score
    
    def _heuristic_score(self, dossier: DossierFournisseur) -> float:
        """
        Score heuristique quand le modèle n'est pas entraîné.
        Basé sur des règles simples.
        """
        score = 0.0
        features = self.extract_features(dossier)
        
        # Écart TVA > 1%
        if features.get("ecart_tva_pct", 0) > 0.01:
            score += 0.3
        
        # Écart TTC > 1%
        if features.get("ecart_ttc_pct", 0) > 0.01:
            score += 0.3
        
        # Attestation expirée
        if features.get("attestation_expiree", 0) == 1:
            score += 0.2
        
        # Dossier incomplet
        if features.get("nb_documents", 0) < 2:
            score += 0.2
        
        return min(1.0, score)
    
    def detect(self, dossier: DossierFournisseur, threshold: float = 0.5) -> List[AnomalieDetectee]:
        """
        Détecte les anomalies dans un dossier via ML.
        
        Args:
            dossier: Le dossier à analyser
            threshold: Seuil au-dessus duquel on signale une anomalie
            
        Returns:
            Liste des anomalies ML détectées
        """
        anomalies = []
        
        score = self.predict_anomaly_score(dossier)
        
        if score >= threshold:
            features = self.extract_features(dossier)
            
            # Identifier les features les plus suspectes
            suspects = self._identify_suspect_features(features)
            
            # Déterminer la gravité selon le score
            if score >= 0.8:
                gravite = NiveauGravite.CRITICAL
            elif score >= 0.6:
                gravite = NiveauGravite.ERROR
            else:
                gravite = NiveauGravite.WARNING
            
            anomalies.append(AnomalieDetectee(
                type_anomalie=TypeAnomalie.MULTI_ANOMALIES,
                gravite=gravite,
                message=f"Dossier suspect détecté par ML (score: {score:.2f})",
                documents_concernes=dossier.get_documents_presents(),
                details={
                    "score_anomalie": round(score, 3),
                    "features_suspectes": suspects,
                    "methode": "Isolation Forest",
                },
                score_anomalie=score,
                confiance=0.85
            ))
        
        return anomalies
    
    def _identify_suspect_features(self, features: dict) -> List[str]:
        """Identifie les features qui contribuent le plus à l'anomalie"""
        suspects = []
        
        # Vérifier les écarts de calcul
        if features.get("ecart_tva_pct", 0) > 0.01:
            suspects.append(f"Écart TVA: {features['ecart_tva_pct']*100:.1f}%")
        
        if features.get("ecart_ttc_pct", 0) > 0.01:
            suspects.append(f"Écart TTC: {features['ecart_ttc_pct']*100:.1f}%")
        
        # Vérifier l'attestation
        if features.get("attestation_expiree", 0) == 1:
            suspects.append(f"Attestation expirée ({abs(features.get('jours_avant_expiration', 0))} jours)")
        
        # Vérifier la complétude
        if features.get("nb_documents", 0) < 2:
            suspects.append(f"Dossier incomplet ({features.get('nb_documents', 0)} document(s))")
        
        # Taux TVA inhabituel
        taux = features.get("taux_tva", 0.2)
        taux_normaux = [0.0, 0.021, 0.055, 0.10, 0.20]
        if not any(abs(taux - t) < 0.005 for t in taux_normaux):
            suspects.append(f"Taux TVA inhabituel: {taux*100:.1f}%")
        
        return suspects
    
    def save_model(self, path: str) -> None:
        """Sauvegarde le modèle entraîné"""
        if not self.is_trained:
            logger.warning("Modèle non entraîné, rien à sauvegarder")
            return
        
        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "contamination": self.contamination,
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model_data, path)
        logger.info(f"Modèle sauvegardé: {path}")
    
    def load_model(self, path: str) -> None:
        """Charge un modèle pré-entraîné"""
        try:
            model_data = joblib.load(path)
            self.model = model_data["model"]
            self.scaler = model_data["scaler"]
            self.feature_names = model_data["feature_names"]
            self.contamination = model_data.get("contamination", 0.1)
            self.is_trained = True
            logger.info(f"Modèle chargé: {path}")
        except Exception as e:
            logger.error(f"Erreur chargement modèle: {e}")
            self.is_trained = False


# Instance globale pour réutilisation
_detector_instance: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Retourne l'instance singleton du détecteur"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AnomalyDetector()
    return _detector_instance
