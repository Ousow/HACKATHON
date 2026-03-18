import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../services/api";

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    setSelectedFile(file || null);
    setError("");
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Veuillez sélectionner un fichier.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const result = await uploadDocument(selectedFile);

      navigate("/result", {
        state: {
          result,
          fileName: selectedFile.name,
        },
      });
    } catch (err) {
      setError(err.message || "Erreur pendant l'upload.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>Envoyer un document</h2>
        <p style={styles.subtitle}>
          Déposez une facture, un devis, un RIB, un Kbis ou une attestation.
        </p>

        <input
          type="file"
          accept=".pdf,image/*"
          onChange={handleFileChange}
          style={styles.input}
        />

        {selectedFile && (
          <div style={styles.fileBox}>
            <strong>Fichier sélectionné :</strong> {selectedFile.name}
          </div>
        )}

        {error && <div style={styles.error}>{error}</div>}

        <button
          onClick={handleUpload}
          disabled={loading}
          style={{
            ...styles.button,
            opacity: loading ? 0.7 : 1,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Envoi en cours..." : "Uploader le document"}
        </button>
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    display: "flex",
    justifyContent: "center",
    paddingTop: "40px",
  },
  card: {
    width: "100%",
    maxWidth: "720px",
    backgroundColor: "black",
    borderRadius: "16px",
    padding: "32px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
  },
  title: {
    marginTop: 0,
    marginBottom: "12px",
  },
  subtitle: {
    marginTop: 0,
    marginBottom: "24px",
    color: "#4b5563",
  },
  input: {
    marginBottom: "16px",
  },
  fileBox: {
    backgroundColor: "#4537dc",
    padding: "12px",
    borderRadius: "10px",
    marginBottom: "16px",
  },
  error: {
    backgroundColor: "#4537dc",
    color: "#991b1b",
    padding: "12px",
    borderRadius: "10px",
    marginBottom: "16px",
  },
  button: {
    border: "none",
    backgroundColor: "#2563eb",
    color: "white",
    padding: "12px 18px",
    borderRadius: "10px",
    fontWeight: "bold",
    fontSize: "1rem",
  },
};