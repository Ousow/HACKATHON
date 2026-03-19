import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../services/api";
import {
  FileText, Image, Folder, Upload, FolderOpen, X, AlertTriangle, Search,
} from "lucide-react";
import { styles } from "./UploadPage.styles";

// ~~formats acceptes par l application
const ACCEPTED = [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"];
const ACCEPTED_MIME = "application/pdf,image/*";

// ~~injection du keyframe pour le spinner
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(style);
}

// ~~icone selon l extension du fichier
function FileIcon({ name, ...props }) {
  const ext = name.split(".").pop().toLowerCase();
  if (ext === "pdf") return <FileText {...props} />;
  if (["png", "jpg", "jpeg", "webp", "bmp", "tiff"].includes(ext)) return <Image {...props} />;
  return <Folder {...props} />;
}

// ~~spinner d attente pendant l upload
function Spinner() {
  return <span style={styles.spinner} />;
}

// ~~formatage lisible de la taille du fichier
function formatSize(bytes) {
  if (bytes < 1024)      return `${bytes} o`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / 1024 ** 2).toFixed(1)} Mo`;
}

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragging,     setDragging]     = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // ~~validation locale avant upload
  const validate = (file) => {
    if (!file) return "Aucun fichier selectionne.";
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ACCEPTED.includes(ext))
      return `Format non supporte (${ext}). Acceptes : ${ACCEPTED.join(", ")}`;
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

  // ~~gestion du drag and drop
  const onDragOver  = useCallback((e) => { e.preventDefault(); setDragging(true);  }, []);
  const onDragLeave = useCallback((e) => { e.preventDefault(); setDragging(false); }, []);
  const onDrop      = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) setFile(file);
  }, []);

  // ~~envoi du fichier au serveur Flask
  const handleUpload = async () => {
    if (!selectedFile) { setError("Veuillez selectionner un fichier."); return; }
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

  // ~~reinitialisation de la selection
  const reset = () => { setSelectedFile(null); setError(""); };

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>

        {/* titre et description */}
        <div style={styles.cardHeader}>
          <h2 style={styles.title}>Analyser un document</h2>
          <p style={styles.subtitle}>
            Deposez une <strong>facture</strong>, un <strong>devis</strong>,
            un <strong>RIB</strong>, un <strong>Kbis</strong> ou
            une <strong>attestation</strong>.<br />
            L'OCR extraira automatiquement les champs cles.
          </p>
        </div>

        {/* zone de depot */}
        <div
          style={{
            ...styles.dropzone,
            ...(dragging                ? styles.dropzoneDrag    : {}),
            ...(selectedFile            ? styles.dropzoneSuccess : {}),
            ...(error && !selectedFile  ? styles.dropzoneError   : {}),
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
            // ~~apercu du fichier selectionne
            <div style={styles.filePreview}>
              <FileIcon name={selectedFile.name} size={28} strokeWidth={1.5} style={styles.fileIcon} />
              <div style={styles.fileInfo}>
                <strong style={styles.fileName}>{selectedFile.name}</strong>
                <span style={styles.fileSize}>{formatSize(selectedFile.size)}</span>
              </div>
              <button style={styles.removeBtn} onClick={(e) => { e.stopPropagation(); reset(); }}>
                <X size={16} />
              </button>
            </div>
          ) : (
            // ~~indication visuelle pour le depot
            <div style={styles.dropHint}>
              {dragging
                ? <FolderOpen size={32} strokeWidth={1.5} style={{ color: "#2563eb" }} />
                : <Upload size={32} strokeWidth={1.5} style={{ color: "#9ca3af" }} />
              }
              <p style={styles.dropText}>
                {dragging ? "Relacher pour deposer" : "Glissez-deposez votre document ici"}
              </p>
              <span style={styles.dropOr}>ou</span>
              <span style={styles.dropBrowse}>Parcourir les fichiers</span>
              <span style={styles.dropFormats}>{ACCEPTED.join("  ·  ")}</span>
            </div>
          )}
        </div>

        {/* message d erreur */}
        {error && (
          <div style={styles.errorBox}>
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* bouton de lancement */}
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
            <span style={styles.btnInner}><Spinner /> Analyse en cours...</span>
          ) : (
            <span style={styles.btnInner}>
              <Search size={16} /> Lancer l'analyse OCR
            </span>
          )}
        </button>

      </div>
    </div>
  );
}