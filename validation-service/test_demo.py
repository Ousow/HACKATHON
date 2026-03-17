"""
Script de test pour vérifier le fonctionnement du module de validation.
Exécutez ce script pour vérifier que toutes les détections fonctionnent.

Usage:
  cd validation-service
  pip install -r requirements.txt
  python test_demo.py
"""

import sys
from datetime import date, timedelta

# Ajouter le chemin pour les imports
sys.path.insert(0, '.')

from app.models.schemas import (
    DossierFournisseur,
    FactureExtrait,
    AttestationURSSAFExtrait,
    RIBExtrait,
    TypeAnomalie,
)
from app.services.validation_engine import ValidationEngine


def print_separator():
    print("\n" + "=" * 60 + "\n")


def print_result(result):
    """Affiche le résultat de validation de manière lisible"""
    status = "✅ VALIDE" if result.est_valide else "❌ INVALIDE"
    print(f"  Statut: {status}")
    print(f"  Score de confiance: {result.score_confiance:.2f}")
    print(f"  Anomalies détectées: {result.nb_anomalies}")
    
    if result.anomalies:
        print("\n  📋 Liste des anomalies:")
        for i, a in enumerate(result.anomalies, 1):
            gravite_emoji = {
                "critical": "🔴",
                "error": "🟠", 
                "warning": "🟡",
                "info": "🔵"
            }.get(a.gravite, "⚪")
            print(f"    {i}. {gravite_emoji} [{a.type_anomalie}] {a.message}")


def test_dossier_valide():
    """Test 1: Dossier complet et valide"""
    print("🧪 TEST 1: Dossier fournisseur VALIDE")
    print("-" * 40)
    
    dossier = DossierFournisseur(
        dossier_id="TEST-VALIDE-001",
        fournisseur_nom="Entreprise Légitime SARL",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-001",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,  # Correct: 1000 × 0.20 = 200
            montant_ttc=1200.00,  # Correct: 1000 + 200 = 1200
            date_emission=date.today() - timedelta(days=5),
            date_echeance=date.today() + timedelta(days=30),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation.pdf",
            numero_attestation="ATT-123456",
            siret="12345678901234",  # Même SIRET ✓
            date_edition=date.today() - timedelta(days=30),
            date_expiration=date.today() + timedelta(days=60),  # Pas expirée ✓
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    return result.est_valide


def test_siret_incoherent():
    """Test 2: SIRET différent entre facture et attestation"""
    print("🧪 TEST 2: SIRET INCOHÉRENT")
    print("-" * 40)
    print("  Scénario: Le SIRET de la facture ≠ SIRET de l'attestation")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-SIRET-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-002",
            siret_emetteur="12345678901234",  # SIRET A
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,
            montant_ttc=1200.00,
            date_emission=date.today(),
        ),
        attestation_urssaf=AttestationURSSAFExtrait(
            fichier_source="attestation.pdf",
            numero_attestation="ATT-999999",
            siret="98765432109876",  # SIRET B différent ! ✗
            date_edition=date.today() - timedelta(days=10),
            date_expiration=date.today() + timedelta(days=80),
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    # Vérifier que l'anomalie SIRET est bien détectée
    siret_detected = any(a.type_anomalie == TypeAnomalie.SIRET_INCOHERENT for a in result.anomalies)
    return siret_detected


def test_tva_incoherente():
    """Test 3: TVA mal calculée"""
    print("🧪 TEST 3: TVA INCOHÉRENTE")
    print("-" * 40)
    print("  Scénario: TVA déclarée = 300€ mais devrait être 200€ (1000 × 20%)")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-TVA-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-003",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=300.00,  # FAUX ! Devrait être 200 ✗
            montant_ttc=1300.00,
            date_emission=date.today(),
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    tva_detected = any(a.type_anomalie == TypeAnomalie.TVA_INCOHERENTE for a in result.anomalies)
    return tva_detected


def test_montant_falsifie():
    """Test 4: Montant TTC falsifié"""
    print("🧪 TEST 4: MONTANT TTC FALSIFIÉ")
    print("-" * 40)
    print("  Scénario: TTC = 1500€ mais devrait être 1200€ (1000 + 200)")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-TTC-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-004",
            siret_emetteur="12345678901234",
            montant_ht=1000.00,
            taux_tva=0.20,
            montant_tva=200.00,  # Correct
            montant_ttc=1500.00,  # FAUX ! Devrait être 1200 (surfacturation +300€) ✗
            date_emission=date.today(),
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    falsifie_detected = any(a.type_anomalie == TypeAnomalie.MONTANT_FALSIFIE for a in result.anomalies)
    return falsifie_detected


def test_attestation_expiree():
    """Test 5: Attestation URSSAF expirée"""
    print("🧪 TEST 5: ATTESTATION EXPIRÉE")
    print("-" * 40)
    print("  Scénario: L'attestation a expiré il y a 50 jours")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-EXPIRED-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-005",
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
            date_expiration=date.today() - timedelta(days=50),  # EXPIRÉE ! ✗
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    expired_detected = any(a.type_anomalie == TypeAnomalie.ATTESTATION_EXPIREE for a in result.anomalies)
    return expired_detected


def test_rib_frauduleux():
    """Test 6: Fraude au RIB (substitution de compte)"""
    print("🧪 TEST 6: FRAUDE AU RIB")
    print("-" * 40)
    print("  Scénario: L'IBAN sur la facture ≠ IBAN du RIB fourni")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-RIB-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-006",
            siret_emetteur="12345678901234",
            montant_ht=2000.00,
            taux_tva=0.20,
            montant_tva=400.00,
            montant_ttc=2400.00,
            date_emission=date.today(),
            iban="FR7630001007941234567890185",  # IBAN A
        ),
        rib=RIBExtrait(
            fichier_source="rib.pdf",
            iban="FR7612345678901234567890123",  # IBAN B différent ! ✗
            bic="BNPAFRPP",
            titulaire="Compte Frauduleux",
        ),
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    rib_detected = any(a.type_anomalie == TypeAnomalie.RIB_INCOHERENT for a in result.anomalies)
    return rib_detected


def test_document_manquant():
    """Test 7: Facture sans attestation"""
    print("🧪 TEST 7: DOCUMENT MANQUANT")
    print("-" * 40)
    print("  Scénario: Facture seule sans attestation URSSAF")
    
    dossier = DossierFournisseur(
        dossier_id="TEST-MISSING-001",
        facture=FactureExtrait(
            fichier_source="facture.pdf",
            numero_facture="FAC-2026-007",
            siret_emetteur="12345678901234",
            montant_ht=100.00,
            taux_tva=0.20,
            montant_tva=20.00,
            montant_ttc=120.00,
            date_emission=date.today(),
        ),
        # Pas d'attestation_urssaf !
    )
    
    engine = ValidationEngine(use_ml=False)
    result = engine.validate(dossier)
    print_result(result)
    
    missing_detected = any(a.type_anomalie == TypeAnomalie.DOCUMENT_MANQUANT for a in result.anomalies)
    return missing_detected


def main():
    print("\n" + "=" * 60)
    print("   🔍 TEST DU MODULE DE VALIDATION INTELLIGENT")
    print("   Étudiant 5 - M2 Hackathon 2026")
    print("=" * 60)
    
    tests = [
        ("Dossier valide", test_dossier_valide),
        ("SIRET incohérent", test_siret_incoherent),
        ("TVA incohérente", test_tva_incoherente),
        ("Montant TTC falsifié", test_montant_falsifie),
        ("Attestation expirée", test_attestation_expiree),
        ("Fraude au RIB", test_rib_frauduleux),
        ("Document manquant", test_document_manquant),
    ]
    
    results = []
    
    for name, test_func in tests:
        print_separator()
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ❌ ERREUR: {e}")
            results.append((name, False))
    
    # Résumé final
    print_separator()
    print("📊 RÉSUMÉ DES TESTS")
    print("-" * 40)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, result in results:
        emoji = "✅" if result else "❌"
        print(f"  {emoji} {name}")
    
    print("-" * 40)
    print(f"  Total: {passed}/{total} tests passés")
    
    if passed == total:
        print("\n  🎉 TOUS LES TESTS SONT PASSÉS !")
        print("  Le module de validation fonctionne correctement.")
    else:
        print(f"\n  ⚠️ {total - passed} test(s) échoué(s)")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
