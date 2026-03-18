import { Link, useLocation } from "react-router-dom";

export default function ResultPage() {
  const location = useLocation();
  const result = location.state?.result;
  const fileName = location.state?.fileName;

  if (!result) {
    return (
      <div style={styles.card}>
        <h2>Aucun résultat disponible</h2>
        <p>Commencez par envoyer un document depuis la page d'upload.</p>
        <Link to="/" style={styles.link}>
          Retour à l'upload
        </Link>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>Résultat du traitement</h2>

        <div style={styles.infoBox}>
          <strong>Fichier :</strong> {fileName || "Inconnu"}
        </div>

        <div style={styles.section}>
          <h3>Réponse API</h3>
          <pre style={styles.pre}>{JSON.stringify(result, null, 2)}</pre>
        </div>

        <Link to="/" style={styles.link}>
          Retour à l'upload
        </Link>
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    paddingTop: "20px",
  },
  card: {
    backgroundColor: "white",
    borderRadius: "16px",
    padding: "32px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
  },
  title: {
    marginTop: 0,
  },
  infoBox: {
    backgroundColor: "#ecfeff",
    padding: "12px",
    borderRadius: "10px",
    marginBottom: "24px",
  },
  section: {
    marginBottom: "24px",
  },
  pre: {
    backgroundColor: "#111827",
    color: "#f9fafb",
    padding: "16px",
    borderRadius: "12px",
    overflowX: "auto",
    fontSize: "0.9rem",
  },
  link: {
    color: "#2563eb",
    textDecoration: "none",
    fontWeight: "bold",
  },
};