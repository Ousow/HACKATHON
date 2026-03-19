import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../services/api";

const ACCEPTED = [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"];
const ACCEPTED_MIME = "application/pdf,image/*";

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragging,     setDragging]     = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // ── file validation ──────────────────────────────────────────────────────
  const validate = (file) => {
    if (!file) return "Aucun fichier sélectionné.";
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ACCEPTED.includes(ext))
      return `Format non supporté (${ext}). Acceptés : ${ACCEPTED.join(", ")}`;
    if (file.size > 20 * 1024 * 1024)
      return "Fichier trop volumineux (max 20 Mo).";
    return null;
  };

  const setFile = (file) => {
    const err = validate(file);
    if (err) { setError(err); setSelectedFile(null); return; }
    setError("");
    setSelectedFile(file);
  };

  // ── drag & drop ──────────────────────────────────────────────────────────
  const onDragOver  = useCallback((e) => { e.preventDefault(); setDragging(true);  }, []);
  const onDragLeave = useCallback((e) => { e.preventDefault(); setDragging(false); }, []);
  const onDrop      = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) setFile(file);
  }, []);

  // ── upload ───────────────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!selectedFile) { setError("Veuillez sélectionner un fichier."); return; }
    try {
      setLoading(true);
      setError("");
      const result = await uploadDocument(selectedFile);
      navigate("/result", { state: { result, fileName: selectedFile.name } });
    } catch (err) {
      setError(err.message || "Erreur pendant l'upload.");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setSelectedFile(null); setError(""); };

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>

        <div style={styles.cardHeader}>
          <h2 style={styles.title}>Analyser un document</h2>
          <p style={styles.subtitle}>
            Déposez une <strong>facture</strong>, un <strong>devis</strong>,
            un <strong>RIB</strong>, un <strong>Kbis</strong> ou
            une <strong>attestation</strong>.<br />
            L'OCR extraira automatiquement les champs clés.
          </p>
        </div>

        {/* Drop zone */}
        <div
          style={{
            ...styles.dropzone,
            ...(dragging        ? styles.dropzoneDrag    : {}),
            ...(selectedFile    ? styles.dropzoneSuccess : {}),
            ...(error && !selectedFile ? styles.dropzoneError : {}),
          }}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !selectedFile && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_MIME}
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files?.[0])}
          />

          {selectedFile ? (
            <div style={styles.filePreview}>
              <span style={styles.fileIcon}>{fileIcon(selectedFile.name)}</span>
              <div style={styles.fileInfo}>
                <strong style={styles.fileName}>{selectedFile.name}</strong>
                <span style={styles.fileSize}>{formatSize(selectedFile.size)}</span>
              </div>
              <button style={styles.removeBtn} onClick={(e) => { e.stopPropagation(); reset(); }}>
                ✕
              </button>
            </div>
          ) : (
            <div style={styles.dropHint}>
              <span style={styles.dropIcon}>{dragging ? "f" : "⬆"}</span>
              <p style={styles.dropText}>
                {dragging
                  ? "Relâchez pour déposer"
                  : "Glissez-déposez votre document ici"}
              </p>
              <span style={styles.dropOr}>ou</span>
              <span style={styles.dropBrowse}>Parcourir les fichiers</span>
              <span style={styles.dropFormats}>{ACCEPTED.join("  ·  ")}</span>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div style={styles.errorBox}>
            <span></span> {error}
          </div>
        )}

        {/* CTA */}
        <button
          onClick={handleUpload}
          disabled={loading || !selectedFile}
          style={{
            ...styles.button,
            opacity: (loading || !selectedFile) ? 0.5 : 1,
            cursor:  (loading || !selectedFile) ? "not-allowed" : "pointer",
          }}
        >
          {loading ? (
            <span style={styles.btnInner}><Spinner /> Analyse en cours…</span>
          ) : (
            <span style={styles.btnInner}>Lancer l'analyse OCR</span>
          )}
        </button>

      </div>
    </div>
  );
}

// ── micro helpers ─────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <span style={styles.spinner} />
  );
}

function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  if (ext === "pdf") return "";
  if (["png","jpg","jpeg","webp","bmp","tiff"].includes(ext)) return "";
  return "";
}

function formatSize(bytes) {
  if (bytes < 1024)       return `${bytes} o`;
  if (bytes < 1024**2)    return `${(bytes/1024).toFixed(1)} Ko`;
  return `${(bytes/1024**2).toFixed(1)} Mo`;
}

// ── styles ────────────────────────────────────────────────────────────────────

const styles = {
  wrapper: {
    display: "flex",
    justifyContent: "center",
    paddingTop: "40px",
    paddingBottom: "40px",
  },
  card: {
    width: "100%",
    maxWidth: "640px",
    backgroundColor: "white",
    borderRadius: "20px",
    padding: "36px",
    boxShadow: "0 8px 32px rgba(0,0,0,0.08)",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  cardHeader: {},
  title: {
    margin: "0 0 10px",
    fontSize: "1.5rem",
    color: "#111827",
  },
  subtitle: {
    margin: 0,
    color: "#6b7280",
    fontSize: "0.9rem",
    lineHeight: "1.6",
  },
  dropzone: {
    border: "2px dashed #d1d5db",
    borderRadius: "14px",
    padding: "32px 20px",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.2s ease",
    backgroundColor: "#f9fafb",
    minHeight: "160px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  dropzoneDrag: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff",
  },
  dropzoneSuccess: {
    borderColor: "#16a34a",
    backgroundColor: "#f0fdf4",
    cursor: "default",
    borderStyle: "solid",
  },
  dropzoneError: {
    borderColor: "#dc2626",
    backgroundColor: "#fef2f2",
  },
  dropHint: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
  },
  dropIcon: {
    fontSize: "2rem",
  },
  dropText: {
    margin: 0,
    color: "#374151",
    fontWeight: "600",
    fontSize: "0.95rem",
  },
  dropOr: {
    color: "#9ca3af",
    fontSize: "0.8rem",
  },
  dropBrowse: {
    color: "#2563eb",
    fontWeight: "700",
    fontSize: "0.9rem",
    textDecoration: "underline",
  },
  dropFormats: {
    color: "#9ca3af",
    fontSize: "0.75rem",
    marginTop: "4px",
  },
  filePreview: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    width: "100%",
    textAlign: "left",
  },
  fileIcon: {
    fontSize: "2rem",
    flexShrink: 0,
  },
  fileInfo: {
    flex: 1,
    overflow: "hidden",
  },
  fileName: {
    display: "block",
    fontSize: "0.95rem",
    color: "#111827",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  fileSize: {
    fontSize: "0.8rem",
    color: "#6b7280",
  },
  removeBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#9ca3af",
    fontSize: "1rem",
    padding: "4px 8px",
    borderRadius: "6px",
    transition: "background 0.15s",
    flexShrink: 0,
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    border: "1px solid #fca5a5",
    color: "#991b1b",
    padding: "12px 16px",
    borderRadius: "10px",
    fontSize: "0.85rem",
    display: "flex",
    gap: "8px",
    alignItems: "center",
  },
  button: {
    border: "none",
    backgroundColor: "#1d4ed8",
    color: "white",
    padding: "14px 20px",
    borderRadius: "12px",
    fontWeight: "700",
    fontSize: "1rem",
    width: "100%",
    transition: "background 0.15s, transform 0.1s",
  },
  btnInner: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
  },
  spinner: {
    display: "inline-block",
    width: "16px",
    height: "16px",
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "white",
    borderRadius: "50%",
    animation: "spin 0.7s linear infinite",
  },
};

// inject keyframe for spinner
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(style);
}