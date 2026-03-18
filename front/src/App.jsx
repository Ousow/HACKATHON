import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import UploadPage from "./pages/UploadPage";
import ResultPage from "./pages/ResultPage";

export default function App() {
  return (
    <div style={styles.app}>
      <Navbar />
      <main style={styles.main}>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/result" element={<ResultPage />} />
        </Routes>
      </main>
    </div>
  );
}

const styles = {
  app: {
    minHeight: "100vh",
    background: "#f5f7fb",
    color: "#111827",
    fontFamily: "Arial, sans-serif",
  },
  main: {
    maxWidth: "1100px",
    margin: "0 auto",
    padding: "24px",
  },
};