# वाणीसंशोधक (VaniScript) — पूर्ण डिप्लॉयमेंट मार्गदर्शिका (Deployment Guide)

इस मार्गदर्शिका में वाणीसंशोधक (Hindi Heritage OCR & Digital Granth Preservation Platform) को **Hugging Face Spaces (Docker)** एवं **Vercel** पर लाइव डिप्लॉय करने की विस्तृत चरणबद्ध प्रक्रिया समझाई गई है।

---

## 📌 डिप्लॉयमेंट आर्किटेक्चर (Deployment Architecture)

### क्या यह पूरा प्रोजेक्ट केवल Vercel पर चल सकता है?
- **फ्रंटएंड (React 19):** ✅ **हाँ**, Vercel पर बहुत आसानी से और मुफ्त में चल सकता है।
- **बैकएंड (Python FastAPI + Tesseract + EasyOCR + PyTorch):** ❌ **केवल Vercel पर नहीं चल सकता।**
  - **कारण:** 
    1. Vercel एक **Serverless Jamstack** प्लेटफ़ॉर्म है जहाँ फ़ंक्शन का आकार अधिकतम 250 MB और निष्पादन समय 10–60 सेकंड तक सीमित होता है।
    2. इस प्रोजेक्ट में **Tesseract C++ बाइनरी**, **PyTorch**, **EasyOCR डीप लर्निंग मॉडल (300 MB)**, तथा **OpenCV** शामिल हैं, जिनका कुल आकार 1.5 GB से अधिक है।
    3. Vercel में कोई स्थायी डिस्क (Persistent Disk) नहीं होती।

---

## 🚀 विकल्प १: Hugging Face Spaces (Docker) पर डिप्लॉय (अनुशंसित / Free 16GB RAM)

Hugging Face Spaces मुफ़्त CPU टियर पर **16 GB RAM** और **2 vCPU** प्रदान करता है, जो PyTorch और EasyOCR के लिए अत्यंत उपयुक्त है।

### चरण १: Hugging Face पर Space बनाएँ
1. [Hugging Face](https://huggingface.co/) पर अकाउंट बनाएँ या लॉग इन करें।
2. टॉप-राइट प्रोफ़ाइल आइकन पर क्लिक करें और **New Space** चुनें (या [huggingface.co/new-space](https://huggingface.co/new-space) पर जाएँ)।
3. सेटिंग्स भरें:
   - **Space name:** `vaniscript-hindi-ocr`
   - **License:** `apache-2.0`
   - **Select the Space SDK:** **Docker** 🐳 (Blank)
   - **Space hardware:** **Free CPU basic • 2 vCPU • 16GB RAM** (मुफ़्त)
   - **Visibility:** `Public`
4. **Create Space** बटन दबाएँ।

---

### चरण २: GitHub से Hugging Face Space को जोड़ें

Hugging Face Space पर कोड पहुँचाने के २ आसान तरीके हैं:

#### तरीक़ा A: GitHub Actions द्वारा ऑटो-सिंक (श्रेष्ठ तरीक़ा)
Hugging Face Space सेटिंग्स में जाकर अपना Access Token (`write` अनुमति वाला) निकालें और GitHub रिपॉजिटरी की Secrets में जोड़ दें। इसके बाद हर GitHub पुश स्वतः Hugging Face पर डिप्लॉय हो जाएगा।

#### तरीक़ा B: लोकल टर्मिनल से सीधे Hugging Face पर Git Push करना
अपने कंप्यूटर के टर्मिनल (PowerShell) में यह कमांड चलाएँ:

```powershell
# 1. Hugging Face रिपॉजिटरी को रिमोट के रूप में जोड़ें
git remote add hf https://huggingface.co/spaces/<YOUR_HF_USERNAME>/vaniscript-hindi-ocr

# 2. कोड को Hugging Face पर पुश करें
git push -u hf master:main
```
*(जब पासवर्ड माँगे, तो अपना Hugging Face User Access Token (Write) डालें)*

---

### चरण ३: डॉकर बिल्ड एवं रन प्रक्रिया
पुश करते ही Hugging Face Space स्वतः बिल्ड शुरू कर देगा:
1. React 19 फ्रंटएंड का प्रोडक्शन बंडल बनाएगा।
2. लिनक्स Tesseract (हिन्दी, संस्कृत, अंग्रेज़ी) और देवनागरी फ़ॉन्ट्स इंस्टॉल करेगा।
3. PyTorch CPU और EasyOCR 300 MB मॉडल्स को `/app/models/easyocr` में डाउनलोड करके कैश करेगा।
4. पोर्ट **`7860`** पर FastAPI सर्वर चालू करेगा।
5. 3 से 5 मिनट में आपका Space **Running** स्थिति में आ जाएगा और आपको पब्लिक लिंक मिलेगा:  
   👉 `https://<YOUR_HF_USERNAME>-vaniscript-hindi-ocr.hf.space`

---

## 🌐 विकल्प २: Vercel फ्रंटएंड को Hugging Face बैकएंड से जोड़ना (Hybrid Architecture)

यदि आप अपने पहले से डिप्लॉय किए हुए Vercel फ्रंटएंड ([https://vaniscript.vercel.app](https://vaniscript.vercel.app)) का उपयोग करना चाहते हैं:

1. Hugging Face Space का पब्लिक डायरेक्ट लिंक कॉपी करें:  
   `https://<YOUR_HF_USERNAME>-vaniscript-hindi-ocr.hf.space`
2. [Vercel Dashboard](https://vercel.com/) पर जाएँ और अपने प्रोजेक्ट (`vaniscript`) को खोलें।
3. **Settings** -> **Environment Variables** में जाएँ।
4. नया वेरिएबल जोड़ें:
   - **Key:** `VITE_API_URL`
   - **Value:** `https://<YOUR_HF_USERNAME>-vaniscript-hindi-ocr.hf.space`
5. **Deployments** टैब में जाकर नवीनतम डिप्लॉयमेंट पर **Redeploy** दबाएँ।

अब आपका Vercel फ्रंटएंड सीधे Hugging Face Space के हाई-परफॉर्मेंस बैकएंड से बात करेगा!

---

## 💾 डेटाबेस एवं स्टोरेज सुरक्षा नीति (Storage & Persistence Notice)

> ⚠️ **महत्वपूर्ण चेतावनी:** Hugging Face Spaces का मुफ़्त लोकल फ़ाइलसिस्टम **अस्थायी (Ephemeral)** होता है।
> यदि Space पुनः चालू (Restart), स्लीप, या री-बिल्ड होता है, तो `backend/storage/uploads` और `preservation.db` कंटेनर की मूल स्थिति में रीसेट हो जाते हैं।

### ग्रन्थों को स्थायी रूप से सुरक्षित रखने की कार्यप्रणाली:
1. **एक्सपोर्ट (Export) सुविधा का उपयोग:** जब भी आप किसी धार्मिक ग्रन्थ या भजन का डिजिटलीकरण पूर्ण करें, **"निर्यात एवं डाउनलोड"** विंडो से Word (.docx), JSON, या TXT फ़ाइल तुरंत अपने कंप्यूटर पर डाउनलोड कर लें।
2. **Hugging Face Persistent Storage (भविष्य के लिए):**
   - यदि आप चाहते हैं कि फ़ाइलें कभी डिलीट न हों, तो Space की Settings में जाकर "Persistent Storage" (Tiered Storage) सक्रिय किया जा सकता है जो `/data` डायरेक्टरी प्रदान करता है।
   - हमारे कोड में `STORAGE_DIR` एनवायरनमेंट वेरिएबल को पहले से ही सपोर्ट कर दिया गया है। Settings में `STORAGE_DIR=/data` सेट करते ही डेटाबेस और इमेजेस हमेशा के लिए सुरक्षित रहेंगी।

---

## 🩺 परीक्षण एवं समस्या निवारण (Troubleshooting & Checklist)

| समस्या | संभावित कारण | समाधान |
| :--- | :--- | :--- |
| **Port 7860 error** | ऐप डिफ़ॉल्ट 8000 पर सुन रहा है | `Dockerfile` में `PORT=7860` और `EXPOSE 7860` सुनिश्चित है। |
| **Permission denied (Errno 13)** | गैर-रूट यूज़र `1000` स्टोरेज में नहीं लिख पा रहा | `Dockerfile` में `chmod -R 777 /app/backend/storage` जोड़ा गया है। |
| **Slow startup (Re-downloading weights)** | EasyOCR मॉडल्स कैश नहीं मिले | `ENV EASYOCR_MODULE_PATH=/app/models/easyocr` द्वारा बिल्ड टाइम पर प्री-डाउनलोड सुनिश्चित है। |
| **Health check failure** | `/api/health` का उत्तर न मिलना | `backend/main.py` में `/health` और `/api/health` दोनों एंडपॉइंट्स JSON लौटाते हैं। |
| **Tesseract missing hin data** | Tesseract पाथ त्रुटि | `config.py` लिनक्स पर `/usr/share/tesseract-ocr/5/tessdata` स्वतः डिटेक्ट करता है। |

---

*वाणीसंशोधक ग्रन्थ संरक्षण परियोजना — सर्वजन हिताय, सर्वजन सुखाय।*
