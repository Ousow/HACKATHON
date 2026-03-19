import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav style={styles.nav}>
      <div style={styles.container}>
        <h1 style={styles.title}>Hackathon - Gestion documentaire</h1>

        <div style={styles.links}>
          <Link to="/" style={styles.link}>
            Upload
          </Link>
          <Link to="/result" style={styles.link}>
            Résultat
          </Link>
        </div>
      </div>
    </nav>
  );
}

const styles = {
  nav: {
    backgroundColor: "#111827",
    padding: "16px 24px",
    boxShadow: "0 2px 10px rgba(0,0,0,0.08)",
  },
  container: {
    maxWidth: "1100px",
    margin: "0 auto",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: {
    margin: 0,
    color: "white",
    fontSize: "1.15rem",
  },
  links: {
    display: "flex",
    gap: "18px",
  },
  link: {
    color: "white",
    textDecoration: "none",
    fontWeight: "bold",
  },
};