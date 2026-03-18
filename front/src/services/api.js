const API_BASE_URL = "http://localhost:5000";

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Erreur upload (${response.status}) : ${errorText || "réponse inconnue"}`
    );
  }

  return response.json();
}