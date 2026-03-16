"""
Module de dégradation d'images simulant des scans de mauvaise qualité.
Applique : bruit, flou, rotation, pixelisation, jaunissement, ombres.
"""
import random
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw


def add_gaussian_noise(img: Image.Image, intensity: float = 0.05) -> Image.Image:
    """Ajoute du bruit gaussien."""
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def add_blur(img: Image.Image, radius: float = None) -> Image.Image:
    """Applique un flou gaussien."""
    if radius is None:
        radius = random.uniform(0.5, 2.5)
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def rotate_image(img: Image.Image, angle: float = None) -> Image.Image:
    """Rotation légère simulant un scan de travers."""
    if angle is None:
        angle = random.uniform(-5, 5)
    bg_color = (255, 255, 255) if img.mode == "RGB" else 255
    return img.rotate(angle, expand=False, fillcolor=bg_color)


def pixelize(img: Image.Image, factor: int = None) -> Image.Image:
    """Réduit la résolution pour simuler une mauvaise qualité."""
    if factor is None:
        factor = random.randint(3, 6)
    w, h = img.size
    small = img.resize((w // factor, h // factor), Image.BILINEAR)
    return small.resize((w, h), Image.NEAREST)


def add_yellowing(img: Image.Image, strength: float = None) -> Image.Image:
    """Simule un jaunissement du papier."""
    if strength is None:
        strength = random.uniform(0.05, 0.25)
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb).astype(np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + strength * 60, 0, 255)   # rouge +
    arr[:, :, 1] = np.clip(arr[:, :, 1] + strength * 30, 0, 255)   # vert +
    arr[:, :, 2] = np.clip(arr[:, :, 2] - strength * 30, 0, 255)   # bleu -
    return Image.fromarray(arr.astype(np.uint8))


def add_shadow(img: Image.Image) -> Image.Image:
    """Ajoute une ombre simulant un coin de page."""
    img_rgb = img.convert("RGBA")
    shadow = Image.new("RGBA", img_rgb.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    w, h = img_rgb.size
    # Ombre dans un coin aléatoire
    corner = random.choice(["tl", "tr", "bl", "br"])
    radius = random.randint(min(w, h) // 6, min(w, h) // 3)
    opacity = random.randint(40, 120)
    if corner == "tl":
        draw.ellipse([-radius, -radius, radius, radius], fill=(0, 0, 0, opacity))
    elif corner == "tr":
        draw.ellipse([w - radius, -radius, w + radius, radius], fill=(0, 0, 0, opacity))
    elif corner == "bl":
        draw.ellipse([-radius, h - radius, radius, h + radius], fill=(0, 0, 0, opacity))
    else:
        draw.ellipse([w - radius, h - radius, w + radius, h + radius], fill=(0, 0, 0, opacity))
    combined = Image.alpha_composite(img_rgb, shadow)
    return combined.convert("RGB")


def lower_contrast(img: Image.Image) -> Image.Image:
    """Réduit le contraste."""
    factor = random.uniform(0.5, 0.85)
    return ImageEnhance.Contrast(img).enhance(factor)


def smartphone_effect(img: Image.Image) -> Image.Image:
    """
    Combine plusieurs effets pour simuler une photo prise avec un smartphone
    (flou, rotation, bruit, ombre, légère surexposition).
    """
    img = rotate_image(img, angle=random.uniform(-8, 8))
    img = add_blur(img, radius=random.uniform(0.8, 2.0))
    img = add_gaussian_noise(img, intensity=random.uniform(0.03, 0.08))
    img = add_shadow(img)
    img = add_yellowing(img, strength=random.uniform(0.05, 0.15))
    img = lower_contrast(img)
    return img


# Profils de dégradation prédéfinis
DEGRADATION_PROFILES = {
    "clean": lambda img: img,
    "light_scan": lambda img: add_blur(add_gaussian_noise(img, 0.02), 0.5),
    "medium_scan": lambda img: add_blur(add_gaussian_noise(rotate_image(img), 0.04), 1.0),
    "heavy_scan": lambda img: add_yellowing(add_blur(
        add_gaussian_noise(rotate_image(img, random.uniform(-3, 3)), 0.07), 1.8)),
    "pixelized": lambda img: pixelize(img),
    "smartphone": smartphone_effect,
    "shadow_scan": lambda img: add_shadow(add_blur(add_gaussian_noise(img, 0.03), 0.8)),
}


def degrade_image(img: Image.Image, profile: str = None) -> tuple[Image.Image, str]:
    """
    Applique un profil de dégradation à une image.

    Args:
        img: image PIL source
        profile: nom du profil (None = aléatoire parmi les dégradés)

    Returns:
        (image dégradée, nom du profil utilisé)
    """
    if profile is None:
        profile = random.choice(list(DEGRADATION_PROFILES.keys()))
    fn = DEGRADATION_PROFILES.get(profile, DEGRADATION_PROFILES["clean"])
    return fn(img.convert("RGB")), profile
