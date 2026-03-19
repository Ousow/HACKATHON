import { Link, useLocation } from "react-router-dom";

// ── helpers ──────────────────────────────────────────────────────────────────

const FIELD_LABELS = {
  siret:         { label: "SIRET",            icon: "🏢" },
  tva:           { label: "TVA intracommunautaire", icon: "🧾" },
  montant_ht:    { label: "Montant HT",       icon: "💶" },
  montant_ttc:   { label: "Montant TTC",      icon: "💰" },
  montant_tva:   { label: "Montant TVA",      icon: "📊" },
  date_emission: { label: "Date d'émission",  icon: "📅" },
  date_expiration:{ label: "Date d'expiration", icon: "⏳" },
  iban:          { label: "IBAN",             icon: "🏦" },
  bic:           { label: "BIC",              icon: "🔑" },
};

const DOC_TYPE_LABELS = {
  facture:       "Facture",
  devis:         "Devis",
  attestation:   "Attestation",
  bon_de_commande: "Bon de commande",
  rib:           "RIB",
  inconnu:       "Type inconnu",
};

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

function FieldRow({ name, field }) {
  const meta = FIELD_LABELS[name] || { label: name, icon: "•" };
  const hasValue = field?.value != null;

  const displayValue = () => {
    if (!hasValue) return <em style={{ color: "#9ca3af" }}>Non détecté</em>;
    const v = field.value;
    if (typeof v === "number") return `${v.toLocaleString("fr-FR", { minimumFractionDigits: 2 })} €`;
    return String(v);
  };

  return (
    <div style={styles.fieldRow}>
      <span style={styles.fieldIcon}>{meta.icon}</span>
      <div style={styles.fieldBody}>
        <span style={styles.fieldLabel}>{meta.label}</span>
        <span style={{ ...styles.fieldValue, opacity: hasValue ? 1 : 0.5 }}>
          {displayValue()}
        </span>
      </div>
      {hasValue && confidenceBadge(field.confidence)}
    </div>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function ResultPage() {
  const location = useLocation();
  const result   = location.state?.result;
  const fileName = location.state?.fileName;

  if (!result) {
    return (
      <div style={styles.emptyCard}>
        <p style={{ fontSize: "2.5rem", margin: 0 }}>📂</p>
        <h2 style={{ marginTop: 8 }}>Aucun résultat disponible</h2>
        <p style={{ color: "#6b7280", marginBottom: 24 }}>
          Commencez par envoyer un document depuis la page d'upload.
        </p>
        <Link to="/" style={styles.backBtn}>← Retour à l'upload</Link>
      </div>
    );
  }

  const { document_type_guess, fields, warnings, extracted_text_preview } = result;
  const docLabel = DOC_TYPE_LABELS[document_type_guess] ?? document_type_guess;

  return (
    <div style={styles.wrapper}>

      {/* ── Header ── */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Résultat de l'extraction</h2>
          <p style={styles.fileChip}>📄 {fileName || "Fichier inconnu"}</p>
        </div>
        <span style={styles.docTypeBadge}>{docLabel}</span>
      </div>

      {/* ── Warnings ── */}
      {warnings?.length > 0 && (
        <div style={styles.warningBox}>
          <strong>⚠️ Avertissements</strong>
          <ul style={styles.warningList}>
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* ── Fields grid ── */}
      <div style={styles.card}>
        <h3 style={styles.sectionTitle}>Champs extraits</h3>
        <div style={styles.fieldGrid}>
          {Object.entries(fields || {}).map(([name, field]) => (
            <FieldRow key={name} name={name} field={field} />
          ))}
        </div>
      </div>

      {/* ── Raw text preview ── */}
      {extracted_text_preview && (
        <details style={styles.details}>
          <summary style={styles.summary}>🔍 Aperçu du texte OCR brut</summary>
          <pre style={styles.pre}>{extracted_text_preview}</pre>
        </details>
      )}

      {/* ── Raw JSON ── */}
      <details style={styles.details}>
        <summary style={styles.summary}>⚙️ JSON complet (debug)</summary>
        <pre style={styles.pre}>{JSON.stringify(result, null, 2)}</pre>
      </details>

      <Link to="/" style={styles.backBtn}>← Nouveau document</Link>
    </div>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const styles = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    paddingTop: "20px",
    paddingBottom: "40px",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "12px",
  },
  title: {
    margin: 0,
    fontSize: "1.5rem",
    color: "#111827",
  },
  fileChip: {
    margin: "6px 0 0",
    color: "#4b5563",
    fontSize: "0.9rem",
  },
  docTypeBadge: {
    backgroundColor: "#dbeafe",
    color: "#1d4ed8",
    padding: "6px 14px",
    borderRadius: "9999px",
    fontWeight: "700",
    fontSize: "0.85rem",
    whiteSpace: "nowrap",
    alignSelf: "center",
  },
  warningBox: {
    backgroundColor: "#fffbeb",
    border: "1px solid #fcd34d",
    borderRadius: "12px",
    padding: "16px 20px",
    color: "#92400e",
    fontSize: "0.9rem",
  },
  warningList: {
    margin: "8px 0 0",
    paddingLeft: "20px",
  },
  card: {
    backgroundColor: "white",
    borderRadius: "16px",
    padding: "28px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
  },
  sectionTitle: {
    margin: "0 0 20px",
    fontSize: "1rem",
    color: "#374151",
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  fieldGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  fieldRow: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    padding: "12px 14px",
    borderRadius: "10px",
    transition: "background 0.15s",
    cursor: "default",
    ":hover": { backgroundColor: "#f9fafb" },
  },
  fieldIcon: {
    fontSize: "1.2rem",
    width: "26px",
    textAlign: "center",
    flexShrink: 0,
  },
  fieldBody: {
    flex: 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "4px",
  },
  fieldLabel: {
    fontSize: "0.85rem",
    color: "#6b7280",
    fontWeight: "500",
  },
  fieldValue: {
    fontSize: "0.95rem",
    color: "#111827",
    fontWeight: "600",
    textAlign: "right",
  },
  badge: {
    fontSize: "0.75rem",
    fontWeight: "700",
    padding: "2px 8px",
    borderRadius: "9999px",
    flexShrink: 0,
  },
  details: {
    backgroundColor: "white",
    borderRadius: "16px",
    padding: "16px 24px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
  },
  summary: {
    cursor: "pointer",
    fontWeight: "600",
    color: "#374151",
    fontSize: "0.9rem",
  },
  pre: {
    marginTop: "16px",
    backgroundColor: "#0f172a",
    color: "#e2e8f0",
    padding: "16px",
    borderRadius: "10px",
    overflowX: "auto",
    fontSize: "0.8rem",
    lineHeight: "1.6",
  },
  emptyCard: {
    backgroundColor: "white",
    borderRadius: "16px",
    padding: "48px 32px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
    textAlign: "center",
    maxWidth: "480px",
    margin: "40px auto",
  },
  backBtn: {
    display: "inline-block",
    color: "#2563eb",
    fontWeight: "700",
    textDecoration: "none",
    fontSize: "0.95rem",
  },
};