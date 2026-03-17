"""
Tests unitaires et d'intégration pour le service de validation.
"""

import pytest
from datetime import date, timedelta

from app.models.schemas import (
    DossierFournisseur,
    FactureExtrait,
    AttestationURSSAFExtrait,
    DevisExtrait,
    KbisExtrait,
    RIBExtrait,
    TypeAnomalie,
    NiveauGravite,
)
from app.validators import (
    SIRETValidator,
    TVAValidator,
    DateValidator,
    RIBValidator,
    CompletenessValidator,
)
from app.services.validation_engine import ValidationEngine
from app.models.anomaly_detector import AnomalyDetector


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def dossier_valide():
    """Dossier fournisseur complet et valide"""
    return DossierFournisseur(
        dossier_id="TEST-001",
        fournisseur_nom="Entreprise Test SARL",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-001",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,
            montant_ttc=1200.00,
            date_emission=date.today() - timedelta(days=5),
            date_echeance=date.today() + timedelta(days=30),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation.pdf",
            numero_attestation="ATT-123456",
            siret="12345678901234",  # Même SIRET
            date_edition=date.today() - timedelta(days=30),
            date_expiration=date.today() + timedelta(days=60),
        ),
    )


@pytest.fixture
def dossier_siret_incoherent():
    """Dossier avec SIRET incohérent"""
    return DossierFournisseur(
        dossier_id="TEST-002",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-002",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,
            montant_ttc=1200.00,
            date_emission=date.today(),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation.pdf",
            numero_attestation="ATT-999999",
            siret="98765432109876",  # SIRET différent !
            date_edition=date.today() - timedelta(days=10),
            date_expiration=date.today() + timedelta(days=80),
        ),
    )


@pytest.fixture
def dossier_tva_incoherente():
    """Dossier avec TVA mal calculée"""
    return DossierFournisseur(
        dossier_id="TEST-003",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-003",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=300.00,  # Devrait être 200 !
            montant_ttc=1300.00,
            date_emission=date.today(),
        ),
    )


@pytest.fixture
def dossier_attestation_expiree():
    """Dossier avec attestation expirée"""
    return DossierFournisseur(
        dossier_id="TEST-004",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-004",
            siret_emetteur="12345678901234",
            montant_ht=500.00,
            taux_tva=0.20,
            montant_tva=100.00,
            montant_ttc=600.00,
            date_emission=date.today(),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation.pdf",
            numero_attestation="ATT-EXPIRED",
            siret="12345678901234",
            date_edition=date.today() - timedelta(days=200),
            date_expiration=date.today() - timedelta(days=50),  # Expirée !
        ),
    )


@pytest.fixture
def dossier_rib_incoherent():
    """Dossier avec RIB frauduleux"""
    return DossierFournisseur(
        dossier_id="TEST-005",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-005",
            siret_emetteur="12345678901234",
            montant_ht=2000.00,
            taux_tva=0.20,
            montant_tva=400.00,
            montant_ttc=2400.00,
            date_emission=date.today(),
            iban="FR7630001007941234567890185",
        ),
        rib=RIBExtrait(
            fichier_source="rib.pdf",
            iban="FR7612345678901234567890123",  # IBAN différent !
            bic="BNPAFRPP",
            titulaire="Entreprise Test",
        ),
    )


# ─────────────────────────────────────────────────────────────
# Tests SIRET Validator
# ─────────────────────────────────────────────────────────────

class TestSIRETValidator:
    
    def test_siret_valide(self, dossier_valide):
        """Test : SIRET cohérent ne génère pas d'anomalie"""
        validator = SIRETValidator()
        anomalies = validator.validate(dossier_valide)
        
        # Pas d'anomalie de type SIRET_INCOHERENT
        siret_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.SIRET_INCOHERENT]
        assert len(siret_anomalies) == 0
    
    def test_siret_incoherent(self, dossier_siret_incoherent):
        """Test : SIRET incohérent est détecté"""
        validator = SIRETValidator()
        anomalies = validator.validate(dossier_siret_incoherent)
        
        # Doit détecter l'incohérence
        siret_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.SIRET_INCOHERENT]
        assert len(siret_anomalies) >= 1
        assert siret_anomalies[0].gravite == NiveauGravite.CRITICAL
    
    def test_siret_format_invalide(self):
        """Test : SIRET mal formaté est détecté"""
        dossier = DossierFournisseur(
            dossier_id="TEST-FORMAT",
            facture=FactureExtrait(
                fichier_source="test.pdf",
                numero_facture="FAC-001",
                siret_emetteur="1234",  # Trop court !
                montant_ht=100,
                taux_tva=0.2,
                montant_tva=20,
                montant_ttc=120,
                date_emission=date.today(),
            ),
        )
        
        validator = SIRETValidator()
        anomalies = validator.validate(dossier)
        
        format_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.SIRET_INVALIDE]
        assert len(format_anomalies) >= 1


# ─────────────────────────────────────────────────────────────
# Tests TVA Validator
# ─────────────────────────────────────────────────────────────

class TestTVAValidator:
    
    def test_tva_valide(self, dossier_valide):
        """Test : TVA correcte ne génère pas d'anomalie"""
        validator = TVAValidator()
        anomalies = validator.validate(dossier_valide)
        
        tva_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.TVA_INCOHERENTE]
        assert len(tva_anomalies) == 0
    
    def test_tva_incoherente(self, dossier_tva_incoherente):
        """Test : TVA mal calculée est détectée"""
        validator = TVAValidator()
        anomalies = validator.validate(dossier_tva_incoherente)
        
        tva_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.TVA_INCOHERENTE]
        assert len(tva_anomalies) >= 1
        assert tva_anomalies[0].gravite == NiveauGravite.CRITICAL
    
    def test_montant_falsifie(self):
        """Test : TTC falsifié est détecté"""
        dossier = DossierFournisseur(
            dossier_id="TEST-TTC",
            facture=FactureExtrait(
                fichier_source="test.pdf",
                numero_facture="FAC-001",
                siret_emetteur="12345678901234",
                montant_ht=1000.00,
                taux_tva=0.20,
                montant_tva=200.00,
                montant_ttc=1500.00,  # Devrait être 1200 !
                date_emission=date.today(),
            ),
        )
        
        validator = TVAValidator()
        anomalies = validator.validate(dossier)
        
        ttc_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.MONTANT_FALSIFIE]
        assert len(ttc_anomalies) >= 1


# ─────────────────────────────────────────────────────────────
# Tests Date Validator
# ─────────────────────────────────────────────────────────────

class TestDateValidator:
    
    def test_attestation_valide(self, dossier_valide):
        """Test : Attestation valide ne génère pas d'anomalie"""
        validator = DateValidator()
        anomalies = validator.validate(dossier_valide)
        
        expiration_anomalies = [
            a for a in anomalies 
            if a.type_anomalie == TypeAnomalie.ATTESTATION_EXPIREE 
            and a.gravite == NiveauGravite.CRITICAL
        ]
        assert len(expiration_anomalies) == 0
    
    def test_attestation_expiree(self, dossier_attestation_expiree):
        """Test : Attestation expirée est détectée"""
        validator = DateValidator()
        anomalies = validator.validate(dossier_attestation_expiree)
        
        expiration_anomalies = [
            a for a in anomalies 
            if a.type_anomalie == TypeAnomalie.ATTESTATION_EXPIREE
        ]
        assert len(expiration_anomalies) >= 1
        
        # Vérifier qu'au moins une est critique
        critical = [a for a in expiration_anomalies if a.gravite == NiveauGravite.CRITICAL]
        assert len(critical) >= 1


# ─────────────────────────────────────────────────────────────
# Tests RIB Validator
# ─────────────────────────────────────────────────────────────

class TestRIBValidator:
    
    def test_rib_incoherent(self, dossier_rib_incoherent):
        """Test : RIB frauduleux est détecté"""
        validator = RIBValidator()
        anomalies = validator.validate(dossier_rib_incoherent)
        
        rib_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.RIB_INCOHERENT]
        assert len(rib_anomalies) >= 1
        assert rib_anomalies[0].gravite == NiveauGravite.CRITICAL


# ─────────────────────────────────────────────────────────────
# Tests Completeness Validator
# ─────────────────────────────────────────────────────────────

class TestCompletenessValidator:
    
    def test_dossier_complet(self, dossier_valide):
        """Test : Dossier complet ne manque rien d'obligatoire"""
        validator = CompletenessValidator()
        anomalies = validator.validate(dossier_valide)
        
        # Pas d'anomalie critique ou erreur
        critical_errors = [
            a for a in anomalies 
            if a.gravite in [NiveauGravite.CRITICAL, NiveauGravite.ERROR]
        ]
        assert len(critical_errors) == 0
    
    def test_facture_seule(self):
        """Test : Facture sans attestation génère une erreur"""
        dossier = DossierFournisseur(
            dossier_id="TEST-INCOMPLETE",
            facture=FactureExtrait(
                fichier_source="test.pdf",
                numero_facture="FAC-001",
                siret_emetteur="12345678901234",
                montant_ht=100,
                taux_tva=0.2,
                montant_tva=20,
                montant_ttc=120,
                date_emission=date.today(),
            ),
        )
        
        validator = CompletenessValidator()
        anomalies = validator.validate(dossier)
        
        missing_anomalies = [a for a in anomalies if a.type_anomalie == TypeAnomalie.DOCUMENT_MANQUANT]
        assert len(missing_anomalies) >= 1


# ─────────────────────────────────────────────────────────────
# Tests Validation Engine (intégration)
# ─────────────────────────────────────────────────────────────

class TestValidationEngine:
    
    def test_validate_dossier_valide(self, dossier_valide):
        """Test : Dossier valide passe la validation"""
        engine = ValidationEngine(use_ml=False)
        result = engine.validate(dossier_valide)
        
        assert result.est_valide == True
        assert result.nb_critiques == 0
        assert result.nb_erreurs == 0
        assert result.score_confiance > 0.8
    
    def test_validate_dossier_multi_anomalies(self):
        """Test : Dossier avec plusieurs anomalies"""
        dossier = DossierFournisseur(
            dossier_id="TEST-MULTI",
            facture=FactureExtrait(
                fichier_source="test.pdf",
                numero_facture="FAC-001",
                siret_emetteur="12345678901234",
                montant_ht=1000.00,
                taux_tva=0.20,
                montant_tva=300.00,  # TVA fausse
                montant_ttc=1500.00,  # TTC faux
                date_emission=date.today(),
            ),
            attestation_urssaf=AttestationURSSAFExtrait(
                fichier_source="attestation.pdf",
                numero_attestation="ATT-001",
                siret="98765432109876",  # SIRET différent
                date_edition=date.today() - timedelta(days=200),
                date_expiration=date.today() - timedelta(days=30),  # Expirée
            ),
        )
        
        engine = ValidationEngine(use_ml=False)
        result = engine.validate(dossier)
        
        assert result.est_valide == False
        assert result.nb_anomalies >= 3  # SIRET + TVA + expiration
        assert result.nb_critiques >= 1
        assert result.score_confiance < 0.5


# ─────────────────────────────────────────────────────────────
# Tests Anomaly Detector
# ─────────────────────────────────────────────────────────────

class TestAnomalyDetector:
    
    def test_extract_features(self, dossier_valide):
        """Test : Extraction des features fonctionne"""
        detector = AnomalyDetector()
        features = detector.extract_features(dossier_valide)
        
        assert "ratio_tva_ht" in features
        assert "ecart_tva_abs" in features
        assert "jours_avant_expiration" in features
        assert features["ratio_tva_ht"] == pytest.approx(0.2, rel=0.01)
    
    def test_heuristic_score_normal(self, dossier_valide):
        """Test : Score heuristique d'un dossier normal est bas"""
        detector = AnomalyDetector()
        score = detector._heuristic_score(dossier_valide)
        
        assert score < 0.3
    
    def test_heuristic_score_anomalie(self, dossier_tva_incoherente):
        """Test : Score heuristique d'un dossier anormal est élevé"""
        detector = AnomalyDetector()
        score = detector._heuristic_score(dossier_tva_incoherente)
        
        assert score >= 0.3


# ─────────────────────────────────────────────────────────────
# Run tests
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
