import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Building2, Receipt, Euro, BadgeDollarSign, BarChart2,
  CalendarDays, CalendarClock, Landmark, KeyRound,
  FileQuestion, AlertTriangle, Search, Wrench, ArrowLeft,
  FolderOpen, CheckCircle, XCircle, Send,
} from "lucide-react";
import { styles } from "./ResultPage.styles";

// ~~correspondance champ -> label + icone
const FIELD_LABELS = {
  siret:           { label: "SIRET",                 Icon: Building2 },
  tva:             { label: "TVA intracommunautaire", Icon: Receipt },
  montant_ht:      { label: "Montant HT",            Icon: Euro },
  montant_ttc:     { label: "Montant TTC",           Icon: BadgeDollarSign },
  montant_tva:     { label: "Montant TVA",           Icon: BarChart2 },
  date_emission:   { label: "Date d'emission",       Icon: CalendarDays },
  date_expiration: { label: "Date d'expiration",     Icon: CalendarClock },
  iban:            { label: "IBAN",                  Icon: Landmark },
  bic:             { label: "BIC",                   Icon: KeyRound },
};

// ~~correspondance type de document -> label lisible
const DOC_TYPE_LABELS = {
  facture:         "Facture",
  devis:           "Devis",
  attestation:     "Attestation",
  bon_de_commande: "Bon de commande",
  rib:             "RIB",
  inconnu:         "Type inconnu",
};

// ~~badge de confiance colore selon le pourcentage
function confidenceBadge(confidence) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 90 ? "#16a34a" : pct >= 70 ? "#d97706" : "#dc2626";
  return (
    <span style={{ ...styles.badge, backgroundColor: color + "18", color }}>
      {pct}%
    </span>
  );
}

// ~~ligne du formulaire : input editable avec icone et label
function FieldInput({ name, field, value, onChange }) {
  const meta = FIELD_LABELS[name] || { label: name, Icon: FileQuestion };
  const { Icon } = meta;

  return (
    <div style={styles.fieldRow}>
      <Icon size={18} strokeWidth={1.8} style={styles.fieldIcon} />
      <div style={styles.fieldBody}>
        <label style={styles.fieldLabel}>{meta.label}</label>
        <input
          style={styles.fieldInput}
          type="text"
          value={value ?? ""}
          placeholder="Non detecte"
          onChange={(e) => onChange(name, e.target.value)}
        />
      </div>
      {field?.confidence > 0 && confidenceBadge(field.confidence)}
    </div>
  );
}

// ~~construction du DossierFournisseur selon le type de document
function buildDossier(docType, formValues, fileName) {
  const dossierId = `DOSSIER-${Date.now()}`;
  const base = {
    fichier_source: fileName || "document.pdf",
    confiance_ocr: 0.85,
  };

  const toFloat = (v) => parseFloat(v) || 0;
  const toDate  = (v) => v || new Date().toISOString().split("T")[0];

  if (docType === "facture") {
    return {
      dossier_id: dossierId,
      facture: {
        ...base,
        type_document: "facture",
        numero_facture: `FAC-${Date.now()}`,
        siret_emetteur: formValues.siret || "00000000000000",
        tva_intracommunautaire: formValues.tva || null,
        montant_ht:  toFloat(formValues.montant_ht),
        taux_tva:    0.20,
        montant_tva: toFloat(formValues.montant_tva),
        montant_ttc: toFloat(formValues.montant_ttc),
        date_emission: toDate(formValues.date_emission),
        date_echeance: formValues.date_expiration || null,
        iban: formValues.iban || null,
        bic:  formValues.bic  || null,
      },
    };
  }

  if (docType === "devis") {
    return {
      dossier_id: dossierId,
      devis: {
        ...base,
        type_document: "devis",
        numero_devis: `DEV-${Date.now()}`,
        siret_emetteur: formValues.siret || "00000000000000",
        montant_ht:  toFloat(formValues.montant_ht),
        taux_tva:    0.20,
        montant_tva: toFloat(formValues.montant_tva),
        montant_ttc: toFloat(formValues.montant_ttc),
        date_emission: toDate(formValues.date_emission),
        date_validite: formValues.date_expiration || null,
      },
    };
  }

  if (docType === "rib") {
    return {
      dossier_id: dossierId,
      rib: {
        ...base,
        type_document: "rib",
        iban:      formValues.iban || "",
        bic:       formValues.bic  || "",
        titulaire: fileName || "Inconnu",
        siret:     formValues.siret || null,
      },
    };
  }

  // ~~fallback : on envoie une facture avec ce qu on a
  return {
    dossier_id: dossierId,
    facture: {
      ...base,
      type_document: "facture",
      numero_facture: `DOC-${Date.now()}`,
      siret_emetteur: formValues.siret || "00000000000000",
      montant_ht:  toFloat(formValues.montant_ht),
      taux_tva:    0.20,
      montant_tva: toFloat(formValues.montant_tva),
      montant_ttc: toFloat(formValues.montant_ttc),
      date_emission: toDate(formValues.date_emission),
    },
  };
}

// ~~affichage du resultat de validation
function ValidationResult({ result }) {
  const isValid = result.est_valide;
  const color   = isValid ? "#16a34a" : "#dc2626";
  const bg      = isValid ? "#f0fdf4" : "#fef2f2";
  const border  = isValid ? "#bbf7d0" : "#fecaca";

  return (
    <div style={{ ...styles.validationBox, backgroundColor: bg, border: `1px solid ${border}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
        {isValid
          ? <CheckCircle size={22} color={color} />
          : <XCircle    size={22} color={color} />
        }
        <strong style={{ color, fontSize: "1rem" }}>
          {isValid ? "Dossier valide" : "Anomalies detectees"}
        </strong>
        <span style={{ ...styles.badge, backgroundColor: color + "18", color, marginLeft: "auto" }}>
          Score : {Math.round(result.score_confiance * 100)}%
        </span>
      </div>

      {result.anomalies?.length > 0 && (
        <ul style={styles.anomalieList}>
          {result.anomalies.map((a, i) => (
            <li key={i} style={styles.anomalieItem}>
              <span style={{
                ...styles.gravityBadge,
                backgroundColor:
                  a.gravite === "critical" ? "#fee2e2" :
                  a.gravite === "error"    ? "#ffedd5" :
                  a.gravite === "warning"  ? "#fefce8" : "#f0f9ff",
                color:
                  a.gravite === "critical" ? "#991b1b" :
                  a.gravite === "error"    ? "#9a3412" :
                  a.gravite === "warning"  ? "#854d0e" : "#0369a1",
              }}>
                {a.gravite}
              </span>
              {a.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ~~page principale
export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const result   = location.state?.result;
  const fileName = location.state?.fileName;

  // ~~initialisation du formulaire avec les valeurs extraites par l OCR
  const initFormValues = (fields) => {
    const vals = {};
    Object.entries(fields || {}).forEach(([key, field]) => {
      vals[key] = field?.value != null ? String(field.value) : "";
    });
    return vals;
  };

  const [formValues,       setFormValues]       = useState(() => initFormValues(result?.fields));
  const [validating,       setValidating]       = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [validationError,  setValidationError]  = useState("");

  // ~~cas ou on arrive directement sur /result sans donnees
  if (!result) {
    return (
      <div style={styles.emptyCard}>
        <FolderOpen size={40} strokeWidth={1.5} style={{ color: "#9ca3af" }} />
        <h2 style={{ marginTop: 8 }}>Aucun resultat disponible</h2>
        <p style={{ color: "#6b7280", marginBottom: 24 }}>
          Commencez par envoyer un document depuis la page d'upload.
        </p>
        <Link to="/" style={styles.backBtn}>
          <ArrowLeft size={16} /> Retour a l'upload
        </Link>
      </div>
    );
  }

  const { document_type_guess, fields, warnings, extracted_text_preview } = result;
  const docLabel = DOC_TYPE_LABELS[document_type_guess] ?? document_type_guess;

  const handleFieldChange = (name, value) => {
    setFormValues((prev) => ({ ...prev, [name]: value }));
  };

  // ~~envoi du dossier au service de validation
  const handleValidate = async () => {
    setValidating(true);
    setValidationError("");
    setValidationResult(null);

    try {
      const dossier = buildDossier(document_type_guess, formValues, fileName);

      const response = await fetch("http://localhost:8001/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dossier, use_ml: true }),
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(`Erreur validation (${response.status}) : ${err}`);
      }

      const data = await response.json();
      setValidationResult(data);

    } catch (err) {
      setValidationError(err.message || "Erreur inconnue.");
    } finally {
      setValidating(false);
    }
  };

  return (
    <div style={styles.wrapper}>

      {/* header */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Resultat de l'extraction</h2>
          <p style={styles.fileChip}>{fileName || "Fichier inconnu"}</p>
        </div>
        <span style={styles.docTypeBadge}>{docLabel}</span>
      </div>

      {/* avertissements OCR */}
      {warnings?.length > 0 && (
        <div style={styles.warningBox}>
          <strong style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <AlertTriangle size={16} /> Avertissements
          </strong>
          <ul style={styles.warningList}>
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* formulaire des champs extraits */}
      <div style={styles.card}>
        <h3 style={styles.sectionTitle}>Champs extraits — corrigez si necessaire</h3>
        <div style={styles.fieldGrid}>
          {Object.entries(fields || {}).map(([name, field]) => (
            <FieldInput
              key={name}
              name={name}
              field={field}
              value={formValues[name]}
              onChange={handleFieldChange}
            />
          ))}
        </div>

        {/* bouton de validation */}
        <button
          onClick={handleValidate}
          disabled={validating}
          style={{
            ...styles.validateBtn,
            opacity: validating ? 0.6 : 1,
            cursor:  validating ? "not-allowed" : "pointer",
            marginTop: "24px",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
            <Send size={16} />
            {validating ? "Validation en cours..." : "Valider le document"}
          </span>
        </button>

        {/* erreur de validation */}
        {validationError && (
          <div style={{ ...styles.warningBox, marginTop: "16px" }}>
            <AlertTriangle size={16} /> {validationError}
          </div>
        )}
      </div>

      {/* resultat de la validation */}
      {validationResult && <ValidationResult result={validationResult} />}

      {/* apercu OCR brut */}
      {extracted_text_preview && (
        <details style={styles.details}>
          <summary style={styles.summary}>
            <Search size={14} style={{ marginRight: "6px" }} />
            Apercu du texte OCR brut
          </summary>
          <pre style={styles.pre}>{extracted_text_preview}</pre>
        </details>
      )}

      {/* json debug */}
      <details style={styles.details}>
        <summary style={styles.summary}>
          <Wrench size={14} style={{ marginRight: "6px" }} />
          JSON complet (debug)
        </summary>
        <pre style={styles.pre}>{JSON.stringify(result, null, 2)}</pre>
      </details>

      <Link to="/" style={styles.backBtn}>
        <ArrowLeft size={16} /> Nouveau document
      </Link>
    </div>
  );
}