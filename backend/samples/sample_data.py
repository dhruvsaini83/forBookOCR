import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from core.config import DATA_DIR
from core.stage1_preprocessing import rotate_image

SAMPLES_DIR = DATA_DIR / "sample_images"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

def create_parchment_background(width: int, height: int) -> Image.Image:
    """Generates an aged, slightly warm parchment paper texture with subtle grain."""
    # Base warm ivory/parchment color (RGB 246, 241, 230)
    arr = np.random.normal(loc=244.0, scale=3.5, size=(height, width, 3))
    # Tint towards warm golden-yellow paper
    arr[:, :, 0] += 5.0 # R
    arr[:, :, 1] += 2.0 # G
    arr[:, :, 2] -= 8.0 # B
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def get_hindi_font(size: int = 34):
    """Loads Nirmala UI or standard Windows Devanagari font."""
    font_paths = [
        "C:/Windows/Fonts/Nirmala.ttc",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/aparaj.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def generate_samples():
    """Generates 3 representative historical Hindi scanned page samples."""
    samples = []
    
    # 1. Ramcharitmanas Chaupai
    bg1 = create_parchment_background(1200, 520)
    draw1 = ImageDraw.Draw(bg1)
    font1_title = get_hindi_font(36)
    font1_text = get_hindi_font(32)
    
    # Header
    draw1.text((360, 40), "॥ श्री रामचरितमानस — बालकाण्ड ॥", fill=(148, 66, 23), font=font1_title)
    draw1.line([(340, 90), (860, 90)], fill=(186, 83, 20), width=2)
    
    # Verses with traditional Awadhi orthography
    lines1 = [
        "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।",
        "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥",
        "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।",
        "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
    ]
    y_start = 130
    for line in lines1:
        draw1.text((120, y_start), line, fill=(28, 25, 23), font=font1_text)
        y_start += 75
        
    path1 = SAMPLES_DIR / "ramcharitmanas_doha.png"
    bg1.save(str(path1))
    samples.append({
        "id": "sample-1",
        "title": "श्री रामचरितमानस — बालकाण्ड दोहा",
        "filename": "ramcharitmanas_doha.png",
        "path": str(path1),
        "collection": "धार्मिक काव्य (Religious Poetry)",
        "desc": "गोस्वामी तुलसीदास कृत अवधी दोहावली (अवधी वर्तनी: बरनउँ, मुकुरु, सुधारि)"
    })
    
    # 2. Kabir Doha & Bhajan
    bg2 = create_parchment_background(1200, 520)
    draw2 = ImageDraw.Draw(bg2)
    font2_title = get_hindi_font(36)
    font2_text = get_hindi_font(32)
    
    draw2.text((420, 40), "॥ कबीर साखी एवं भजन संग्रह ॥", fill=(148, 66, 23), font=font2_title)
    draw2.line([(400, 90), (820, 90)], fill=(186, 83, 20), width=2)
    
    lines2 = [
        "माला फेरत जुग भया, फिरा न मन का फेर।",
        "कर का मनका डारि दे, मन का मनका फेर॥",
        "साधु भूखा भाव का, धन का भूखा नाहिं।",
        "धन का भूखा जो फिरै, सो तो साधु नाहिं॥"
    ]
    y_start = 130
    for line in lines2:
        draw2.text((140, y_start), line, fill=(38, 35, 30), font=font2_text)
        y_start += 75
        
    path2 = SAMPLES_DIR / "kabir_bhajan.png"
    bg2.save(str(path2))
    samples.append({
        "id": "sample-2",
        "title": "कबीर साखी एवं चेतावनी भजन",
        "filename": "kabir_bhajan.png",
        "path": str(path2),
        "collection": "संत साहित्य (Sant Literature)",
        "desc": "संत कबीर सधुक्कड़ी भाषा (यमक अलंकार 'मनका' एवं 'मन का')"
    })

    # 3. Shrimad Bhagavad Gita Stotra
    bg3 = create_parchment_background(1250, 460)
    draw3 = ImageDraw.Draw(bg3)
    font3_title = get_hindi_font(36)
    font3_text = get_hindi_font(30)
    
    draw3.text((430, 40), "॥ श्रीमद्भगवद्गीता — द्वितीयोऽध्यायः ॥", fill=(148, 66, 23), font=font3_title)
    draw3.line([(410, 90), (870, 90)], fill=(186, 83, 20), width=2)
    
    lines3 = [
        "कार्पण्यदोषोपहतस्वभावः पृच्छामि त्वां धर्मसंमूढचेताः।",
        "यच्छ्रेयः स्यान्निश्चितं ब्रूहि तन्मे शिष्यस्तेऽहं शाधि मां त्वां प्रपन्नम्॥"
    ]
    y_start = 145
    for line in lines3:
        draw3.text((100, y_start), line, fill=(25, 23, 20), font=font3_text)
        y_start += 90
        
    path3 = SAMPLES_DIR / "gita_stotra.png"
    bg3.save(str(path3))
    samples.append({
        "id": "sample-3",
        "title": "श्रीमद्भगवद्गीता — द्वितीय अध्याय श्लोक",
        "filename": "gita_stotra.png",
        "path": str(path3),
        "collection": "संस्कृत/हिन्दी ग्रन्थ (Scriptures)",
        "desc": "जटिल संयुक्ताक्षर, विसर्ग एवं वैदिक देवनागरी मुद्रण"
    })
    
    return samples

if __name__ == "__main__":
    generated = generate_samples()
    print(f"Generated {len(generated)} authentic Hindi manuscript samples.")
