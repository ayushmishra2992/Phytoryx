"""Classical (non-learned) leaf measurements and colour-based visible-condition flags.

These are MEASUREMENTS of the photograph. They are not validated against labelled masks or pathology, so:
  * morphology  -> AVAILABLE as pixel-space measurements only (no physical scale),
  * health      -> EXPERIMENTAL colour heuristics, "disease-like" wording only, never a diagnosis,
  * dust        -> NOT_SUPPORTED (no labelled dust/deposition masks were acquired).
"""
import numpy as np
from PIL import Image
from skimage import color, measure, morphology

from . import AVAILABLE, EXPERIMENTAL, NOT_SUPPORTED, UNAVAILABLE, section

MAX_SIDE = 512


def _prep(img: Image.Image):
    img = img.convert("RGB")
    s = MAX_SIDE / max(img.size)
    if s < 1:
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
    return np.asarray(img)


def leaf_mask(rgb):
    """Foreground = pixels more saturated / greener than the background (Otsu on an excess-green+saturation score)."""
    from skimage.filters import threshold_otsu
    f = rgb.astype(float) / 255.0
    exg = 2 * f[..., 1] - f[..., 0] - f[..., 2]
    sat = color.rgb2hsv(rgb)[..., 1]
    score = 0.6 * (exg - exg.min()) / (np.ptp(exg) + 1e-9) + 0.4 * sat
    m = score > threshold_otsu(score)
    m = morphology.remove_small_objects(m, max_size=200)
    m = morphology.closing(m, morphology.disk(3)).astype(bool)
    lab = measure.label(m)
    if lab.max() == 0:
        return None
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == sizes.argmax()


def morphology_section(img, pixels_per_cm=None):
    """Leaf measurements of the largest colour-segmented region, reported in ORIGINAL image pixels (the analysis copy is downscaled to
    <= 512 px and every length/area is scaled back). Physical units appear only if the caller supplies a valid scale (pixels_per_cm)."""
    if pixels_per_cm is not None and not (0 < float(pixels_per_cm) <= 100000):
        raise ValueError("pixels_per_cm must be a positive number (pixels per centimetre at the leaf plane).")
    rgb = _prep(img)
    m = leaf_mask(rgb)
    if m is None or m.mean() < 0.02:
        return section(UNAVAILABLE, "No leaf-like foreground region could be segmented from this image.")
    frac = float(m.mean())
    if frac > 0.95:
        return section(UNAVAILABLE, "Foreground covers almost the whole frame; leaf outline cannot be separated from background.")
    sx, sy = img.width / rgb.shape[1], img.height / rgb.shape[0]
    sl, sa = (sx + sy) / 2, sx * sy              # length and area scale factors back to original pixels
    p = measure.regionprops(m.astype(np.uint8))[0]
    h, w = m.shape
    minr, minc, maxr, maxc = p.bbox
    area, per = float(p.area) * sa, float(p.perimeter) * sl
    length, width = float(p.axis_major_length) * sl, float(p.axis_minor_length) * sl
    hsv = color.rgb2hsv(rgb)
    flags = []
    if minr == 0 or minc == 0 or maxr == h or maxc == w:
        flags.append("the segmented region touches the image border (leaf may be cropped; area/length are lower bounds)")
    if frac < 0.05:
        flags.append("the segmented region is very small in the frame")
    if frac > 0.8:
        flags.append("the segmented region fills most of the frame (background may be included)")
    if p.solidity < 0.8:
        flags.append("low solidity: a deeply lobed/compound leaf, a fragmented mask or several leaves")
    out = dict(
        units="pixels (original image resolution)", image_size_px=[img.width, img.height],
        area_px=round(area), perimeter_px=round(per, 1), length_px=round(length, 1), width_px=round(width, 1),
        bbox_width_px=round((maxc - minc) * sx), bbox_height_px=round((maxr - minr) * sy),
        leaf_area_fraction=round(frac, 4), aspect_ratio=round(length / max(width, 1e-6), 3),
        solidity=round(float(p.solidity), 3), eccentricity=round(float(p.eccentricity), 3),
        extent=round(float(p.extent), 3), circularity=round(min(1.0, 4 * np.pi * area / max(per, 1e-6) ** 2), 3),
        touches_image_border=bool(minr == 0 or minc == 0 or maxr == h or maxc == w),
        mean_rgb_in_leaf=[int(x) for x in rgb[m].mean(axis=0)], std_rgb_in_leaf=[round(float(x), 1) for x in rgb[m].std(axis=0)],
        mean_hsv_in_leaf={"hue_deg": round(float(hsv[..., 0][m].mean() * 360), 1), "saturation": round(float(hsv[..., 1][m].mean()), 3),
                          "value": round(float(hsv[..., 2][m].mean()), 3)},
        segmentation_reliability="approximate", reliability_flags=flags,
        caveat="Segmentation is a colour threshold on one photograph: cluttered backgrounds, shadows, multiple leaves, perspective and lens distortion "
               "make all values approximate. Colour statistics depend on lighting and camera.")
    if pixels_per_cm:
        k = float(pixels_per_cm)
        out["physical"] = {"area_cm2": round(area / k ** 2, 2), "perimeter_cm": round(per / k, 2), "length_cm": round(length / k, 2),
                           "width_cm": round(width / k, 2),
                           "basis": f"user-supplied scale of {k:g} pixels/cm; valid only if the scale object lies in the leaf plane and the photo is not oblique"}
        reason = "Measurements in original image pixels; physical units are derived from the scale you supplied."
    else:
        reason = "Measurements in original image pixels. No scale was supplied, so no cm/mm values are reported."
    return section(AVAILABLE, reason, **out)


def health_section(img):
    rgb = _prep(img)
    m = leaf_mask(rgb)
    if m is None or m.mean() < 0.02:
        return section(UNAVAILABLE, "No leaf region segmented, so visible condition cannot be assessed.")
    hsv = color.rgb2hsv(rgb)
    hh, ss, vv = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    n = float(m.sum())
    healthy = m & (hh >= 70) & (hh <= 170) & (ss > 0.2)
    yellow = m & (hh >= 35) & (hh < 70) & (ss > 0.25) & (vv > 0.45)
    brown = m & (hh >= 10) & (hh < 45) & (ss > 0.25) & (vv <= 0.55)
    dark = m & (vv < 0.2)
    fr = {k: round(float(v.sum() / n), 4) for k, v in
          dict(green=healthy, yellowish=yellow, brownish=brown, very_dark=dark).items()}
    flags = []
    if fr["yellowish"] > 0.15:
        flags.append("noticeable yellowish area (possible chlorosis, senescence or lighting)")
    if fr["brownish"] > 0.08:
        flags.append("noticeable brownish area (possible drying, necrosis or soil/background)")
    if fr["very_dark"] > 0.05:
        flags.append("very dark patches (possible spots, shadow or occlusion)")
    return section(EXPERIMENTAL, "Colour-fraction heuristics inside the segmented leaf. Not validated against labelled leaf-health data; "
                   "colour alone cannot establish disease, pathogen, nutrient status or pollution exposure.",
                   colour_fractions=fr, flags=flags, wording="disease-like / condition-like appearance only")


def dust_section():
    return section(NOT_SUPPORTED, "Visible dust/deposition needs labelled segmentation masks, which have not been acquired or validated. "
                   "No coverage %, particle count, PM2.5 value or chemical composition is reported or can be inferred from an RGB photograph.")


def species_section():
    return section(NOT_SUPPORTED, "No licensed, labelled species dataset has been acquired and validated yet (see v2/data_registry). "
                   "No species name or confidence is shown rather than a guess.")


def biological_section():
    from . import DISABLED
    return section(DISABLED, "Bacterial/fungal identity cannot be determined from an ordinary RGB leaf photograph. "
                   "This module stays disabled until laboratory/microscopy evidence and a labelled dataset exist.")


def leaf_like(img):
    """Does the photo contain a large, mostly-green foreground region? Used ONLY to word an unfamiliar-image answer honestly
    (it never overrides the classifier into ACCEPT)."""
    rgb = _prep(img)
    m = leaf_mask(rgb)
    if m is None:
        return {"leaf_like": False, "area_fraction": 0.0, "green_fraction": 0.0}
    hsv = color.rgb2hsv(rgb)
    hh, ss = hsv[..., 0] * 360, hsv[..., 1]
    green = float((m & (hh >= 60) & (hh <= 175) & (ss > 0.2)).sum() / max(1, m.sum()))
    area = float(m.mean())
    return {"leaf_like": bool(0.05 <= area <= 0.97 and green >= 0.5), "area_fraction": round(area, 4), "green_fraction": round(green, 4)}