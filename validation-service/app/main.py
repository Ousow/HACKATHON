"""
API REST FastAPI pour le service de validation intelligent.

Endpoints:
- POST /validate : Valider un dossier fournisseur
- POST /validate/batch : Valider plusieurs dossiers
- GET /health : Health check
- GET /stats : Statistiques du service
"""

from datetime import date
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from app.models.schemas import (
    DossierFournisseur,
    ResultatValidation,
    FactureExtrait,
    AttestationURSSAFExtrait,
    DevisExtrait,
    KbisExtrait,
    RIBExtrait,
    TypeAnomalie,
    NiveauGravite,
)
from app.services.validation_engine import ValidationEngine, get_validation_engine


# ─────────────────────────────────────────────────────────────
# Configuration et lifecycle
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    logger.info("🚀 Démarrage du service de validation...")
    
    # Initialiser le moteur de validation
    engine = get_validation_engine(use_ml=True)
    logger.info(f"✅ Moteur de validation prêt ({len(engine.validators)} validateurs)")
    
    yield
    
    logger.info("🛑 Arrêt du service de validation")


app = FastAPI(
    title="Service de Validation Intelligent",
    description="""
    ## API de détection d'incohérences documentaires
    
    Ce service analyse les dossiers fournisseurs et détecte :
    - **Incohérences SIRET** entre documents
    - **Erreurs de TVA** (calculs incorrects)
    - **Attestations expirées** (URSSAF hors validité)
    - **Fraude RIB** (substitution de coordonnées bancaires)
    - **Documents manquants**
    - **Anomalies par ML** (Isolation Forest)
    
    ### Workflow typique
    1. Extraire les données des documents via OCR/NLP
    2. Structurer les données selon les schémas Pydantic
    3. Appeler POST /validate avec le dossier complet
    4. Analyser les anomalies retournées
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS pour le front-end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Modèles de requête/réponse
# ─────────────────────────────────────────────────────────────

class ValidationRequest(BaseModel):
    """Requête de validation d'un dossier"""
    dossier: DossierFournisseur
    use_ml: bool = Field(default=True, description="Activer la détection ML")
    date_reference: Optional[date] = Field(default=None, description="Date de référence pour les calculs")


class BatchValidationRequest(BaseModel):
    """Requête de validation batch"""
    dossiers: List[DossierFournisseur]
    use_ml: bool = True


class BatchValidationResponse(BaseModel):
    """Réponse de validation batch"""
    resultats: List[ResultatValidation]
    stats: dict


class HealthResponse(BaseModel):
    """Réponse du health check"""
    status: str
    version: str
    validators_count: int


class StatsResponse(BaseModel):
    """Statistiques du service"""
    total_validations: int
    total_anomalies_detectees: int
    types_anomalies: dict
    uptime_seconds: float


# ─────────────────────────────────────────────────────────────
# Variables globales pour les stats
# ─────────────────────────────────────────────────────────────

import time
_start_time = time.time()
_total_validations = 0
_total_anomalies = 0
_anomalies_par_type = {}


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    """Vérifie que le service est opérationnel"""
    engine = get_validation_engine()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        validators_count=len(engine.validators)
    )


@app.get("/stats", response_model=StatsResponse, tags=["Monitoring"])
async def get_stats():
    """Retourne les statistiques du service"""
    global _total_validations, _total_anomalies, _anomalies_par_type
    
    return StatsResponse(
        total_validations=_total_validations,
        total_anomalies_detectees=_total_anomalies,
        types_anomalies=_anomalies_par_type,
        uptime_seconds=round(time.time() - _start_time, 2)
    )


@app.post("/validate", response_model=ResultatValidation, tags=["Validation"])
async def validate_dossier(request: ValidationRequest):
    """
    Valide un dossier fournisseur et retourne les anomalies détectées.
    
    Le dossier peut contenir :
    - Une facture (obligatoire pour paiement)
    - Une attestation URSSAF (obligatoire pour conformité)
    - Un devis, Kbis, RIB (optionnels mais recommandés)
    
    **Types d'anomalies détectées :**
    - `siret_incoherent` : SIRET différent entre documents
    - `tva_incoherente` : Calcul TVA incorrect
    - `montant_falsifie` : TTC ≠ HT + TVA
    - `attestation_expiree` : Attestation hors validité
    - `rib_incoherent` : IBAN facture ≠ RIB
    - `document_manquant` : Pièce justificative absente
    """
    global _total_validations, _total_anomalies, _anomalies_par_type
    
    try:
        # Créer un moteur avec les paramètres de la requête
        engine = ValidationEngine(
            date_reference=request.date_reference,
            use_ml=request.use_ml
        )
        
        # Valider
        result = engine.validate(request.dossier)
        
        # Mettre à jour les stats
        _total_validations += 1
        _total_anomalies += result.nb_anomalies
        for anomalie in result.anomalies:
            t = anomalie.type_anomalie
            _anomalies_par_type[t] = _anomalies_par_type.get(t, 0) + 1
        
        return result
    
    except Exception as e:
        logger.error(f"Erreur validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate/batch", response_model=BatchValidationResponse, tags=["Validation"])
async def validate_batch(request: BatchValidationRequest):
    """
    Valide un lot de dossiers fournisseurs.
    
    Utile pour le traitement de masse (import, migration, audit).
    """
    global _total_validations, _total_anomalies, _anomalies_par_type
    
    try:
        engine = ValidationEngine(use_ml=request.use_ml)
        
        results = engine.validate_batch(request.dossiers)
        stats = engine.get_stats(results)
        
        # Mettre à jour les stats globales
        _total_validations += len(results)
        for r in results:
            _total_anomalies += r.nb_anomalies
            for a in r.anomalies:
                t = a.type_anomalie
                _anomalies_par_type[t] = _anomalies_par_type.get(t, 0) + 1
        
        return BatchValidationResponse(
            resultats=results,
            stats=stats
        )
    
    except Exception as e:
        logger.error(f"Erreur validation batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anomalies/types", tags=["Reference"])
async def list_anomaly_types():
    """Liste tous les types d'anomalies détectables"""
    return {
        "types": [
            {
                "code": t.value,
                "description": _get_anomaly_description(t)
            }
            for t in TypeAnomalie
        ]
    }


@app.get("/validators", tags=["Reference"])
async def list_validators():
    """Liste tous les validateurs actifs"""
    engine = get_validation_engine()
    return {
        "validators": [
            {
                "name": v.name,
                "description": v.description
            }
            for v in engine.validators
        ]
    }


def _get_anomaly_description(anomaly_type: TypeAnomalie) -> str:
    """Retourne la description d'un type d'anomalie"""
    descriptions = {
        TypeAnomalie.SIRET_INCOHERENT: "SIRET différent entre les documents du même fournisseur",
        TypeAnomalie.TVA_INCOHERENTE: "Montant de TVA ne correspond pas au calcul HT × taux",
        TypeAnomalie.MONTANT_FALSIFIE: "Montant TTC ne correspond pas à HT + TVA",
        TypeAnomalie.ATTESTATION_EXPIREE: "Attestation URSSAF hors période de validité",
        TypeAnomalie.RIB_INCOHERENT: "IBAN du RIB différent de celui sur la facture",
        TypeAnomalie.DOCUMENT_MANQUANT: "Document obligatoire ou recommandé absent",
        TypeAnomalie.SIRET_INVALIDE: "Format ou clé de contrôle SIRET invalide",
        TypeAnomalie.TVA_INTRACOMMUNAUTAIRE_INVALIDE: "Format TVA intracommunautaire incorrect",
        TypeAnomalie.IBAN_INVALIDE: "Format ou clé de contrôle IBAN invalide",
        TypeAnomalie.DATE_FUTURE: "Date incohérente (future, ordre incorrect)",
        TypeAnomalie.MONTANT_NEGATIF: "Montant négatif détecté",
        TypeAnomalie.MULTI_ANOMALIES: "Plusieurs anomalies détectées par ML",
    }
    return descriptions.get(anomaly_type, "Description non disponible")


# ─────────────────────────────────────────────────────────────
# Endpoint de test/démo
# ─────────────────────────────────────────────────────────────

@app.post("/demo/validate", tags=["Demo"])
async def demo_validate():
    """
    Endpoint de démonstration avec un dossier exemple.
    Utile pour tester l'API sans préparer de données.
    """
    from datetime import timedelta
    
    # Créer un dossier de test avec une incohérence
    dossier_test = DossierFournisseur(
        dossier_id="DEMO-001",
        fournisseur_nom="ACME SARL",
        facture=FactureExtrait(
            fichier_source="facture_demo.pdf",
            numero_facture="FAC-2026-0001",
            siret_emetteur="12345678901234",  # SIRET facture
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,
            montant_ttc=1200.00,
            date_emission=date.today() - timedelta(days=5),
            date_echeance=date.today() + timedelta(days=30),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation_demo.pdf",
            numero_attestation="ATT-123456",
            siret="98765432109876",  # SIRET différent ! (incohérence)
            date_edition=date.today() - timedelta(days=100),
            date_expiration=date.today() - timedelta(days=10),  # Expirée !
        ),
    )
    
    # Valider
    engine = ValidationEngine(use_ml=True)
    result = engine.validate(dossier_test)
    
    return {
        "message": "Démonstration avec un dossier contenant des anomalies intentionnelles",
        "anomalies_attendues": ["siret_incoherent", "attestation_expiree"],
        "resultat": result
    }


# ─────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
