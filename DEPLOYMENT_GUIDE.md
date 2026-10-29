# वाणीसंशोधक (VaniScript) — Render.com एवं Vercel डिप्लॉयमेंट मार्गदर्शिका

इस मार्गदर्शिका में वाणीसंशोधक (Hindi Heritage OCR & Digital Granth Preservation Platform) को **Render.com (Docker Backend)** एवं **Vercel (React Frontend)** पर 100% मुफ़्त में लाइव डिप्लॉय करने की विस्तृत चरणबद्ध प्रक्रिया समझाई गई है।

---

## 📌 डिप्लॉयमेंट आर्किटेक्चर (Deployment Architecture)

प्रोजेक्ट दो समर्थित आर्किटेक्चर प्रदान करता है:

### 1. हाइब्रिड आर्किटेक्चर (Hybrid Architecture — अनुशंसित 🌟)
- **फ्रंटएंड:** [Vercel](https://vaniscript.vercel.app/) पर लाइव (अल्ट्रा-फास्ट ग्लोबल CDN, मुफ़्त SSL).
- **बैकएंड:** [Render.com](https://render.com/) पर Docker Web Service (FastAPI + Tesseract OCR + EasyOCR + PyTorch CPU).
- **कनेक्शन:** Vercel में `VITE_API_URL=https://<your-render-app>.onrender.com` सेट करने पर फ्रंटएंड सीधे रेंडर बैकएंड से बात करता है।

### 2. ऑल-इन-वन डॉकर आर्किटेक्चर (All-in-One Docker Architecture)
- रिपॉजिटरी में स्थित मल्टी-स्टेज `Dockerfile` पहले React 19 फ्रंटएंड को कंपाइल करता है और फिर Python 3.11 बैकएंड के अंदर एम्बेड कर देता है।
- Render.com पर केवल एक ही सर्विस डिप्लॉय करके आपको एक सिंगल URL मिलता है जहाँ UI और API दोनों साथ चलते हैं।

---

## 🚀 चरणबद्ध डिप्लॉयमेंट प्रक्रिया: Render.com पर बैकएंड लाइव करें

### चरण १: Render.com पर लॉगिन करें
1. [render.com](https://render.com/) पर जाएँ।
2. **"Sign in with GitHub"** पर क्लिक करें और अपने GitHub अकाउंट (`dhruvsaini83`) से ऑथराइज करें।

### चरण २: नई Web Service बनाएँ
1. Render Dashboard पर ऊपर दाएँ कोने में **"New +"** बटन दबाएँ और **"Web Service"** चुनें।
2. **"Build and deploy from a Git repository"** चुनें और Next दबाएँ।
3. GitHub रिपॉजिटरी लिस्ट में से **`forBookOCR`** (`dhruvsaini83/forBookOCR`) चुनें और **"Connect"** पर क्लिक करें।

### चरण ३: सर्विस सेटिंग्स कॉन्फ़िगर करें
फॉर्म में निम्नलिखित विवरण भरें:
- **Name:** `vaniscript-hindi-ocr` (या अपनी पसंद का नाम)
- **Region:** `Singapore` (एशिया के लिए सबसे तेज़) या `Oregon`
- **Branch:** `master`
- **Runtime:** `Docker` (Render अपने आप Dockerfile पहचान लेगा)
- **Instance Type:** **Free ($0/month)**
- **Health Check Path:** `/api/health`

### चरण ४: पर्यावरण चर (Environment Variables) जोड़ें
**Advanced** सेक्शन खोलें और **Add Environment Variable** पर क्लिक करें:
| Key | Value | विवरण |
| :--- | :--- | :--- |
| `PORT` | `8000` | एप्लिकेशन पोर्ट (Dockerfile स्वतः `$PORT` पहचानता है) |
| `PYTHONIOENCODING` | `utf-8` | देवनागरी यूनीकोड लॉगिंग के लिए आवश्यक |
| `ARCHIVAL_STORAGE_POLICY` | `retain_all` | दुर्लभ पांडुलिपियों की पूर्ण सुरक्षा नीति |
| `EASYOCR_MODULE_PATH` | `/app/models/easyocr` | प्री-कैश्ड EasyOCR देवनागरी मॉडल डायरेक्टरी |

### चरण ५: डिप्लॉय करें
- सबसे नीचे **"Deploy Web Service"** बटन पर क्लिक करें।
- Render का बिल्ड इंजन Dockerfile की मदद से:
  1. React फ्रंटएंड बिल्ड करेगा।
  2. लिनक्स Tesseract (Hindi, Sanskrit, English) इंस्टॉल करेगा।
  3. PyTorch CPU और EasyOCR मॉडल्स को बिल्ड-टाइम पर कैश करेगा।
  4. कंटेनर चालू करके हेल्थ चेक पास करेगा।
- 3 से 5 मिनट में आपकी सर्विस **Live** हो जाएगी और आपको पब्लिक URL मिलेगा:  
  👉 `https://vaniscript-hindi-ocr.onrender.com`

---

## 🌐 Vercel फ्रंटएंड को Render बैकएंड से जोड़ना

यदि आप अपने पहले से डिप्लॉय किए हुए Vercel फ्रंटएंड ([https://vaniscript.vercel.app](https://vaniscript.vercel.app)) का उपयोग करना चाहते हैं:

1. Render डैशबोर्ड से अपना लाइव बैकएंड URL कॉपी करें (उदा. `https://vaniscript-hindi-ocr.onrender.com`).
2. [Vercel Dashboard](https://vercel.com/) पर जाएँ और अपने प्रोजेक्ट `vaniscript` को खोलें।
3. **Settings** -> **Environment Variables** में जाएँ।
4. नया वेरिएबल जोड़ें / अपडेट करें:
   - **Key:** `VITE_API_URL`
   - **Value:** `https://vaniscript-hindi-ocr.onrender.com` (बिना ट्रेलिंग स्लैश के)
5. **Deployments** टैब में जाकर नवीनतम डिप्लॉयमेंट के सामने तीन बिंदुओं (`...`) पर क्लिक करके **Redeploy** दबाएँ।

अब आपका Vercel फ्रंटएंड सीधे आपके Render बैकएंड से जुड़कर काम करेगा!

---

## 💾 डेटाबेस एवं स्टोरेज सुरक्षा नीति (Render Free Tier Ephemeral Notice)

> ⚠️ **महत्वपूर्ण सूचना:** Render.com के मुफ़्त टियर पर कंटेनर का लोकल डिस्क **अस्थायी (Ephemeral)** होता है।
> यदि ऐप इनएक्टिविटी के बाद रीस्टार्ट होता है या नया कोड पुश होता है, तो `backend/storage/uploads` और लोकल SQLite फ़ाइलें इनिशियल स्टेट में रीसेट हो जाती हैं।

### ग्रन्थों को स्थायी रूप से सुरक्षित रखने की कार्यप्रणाली:
1. **एक्सपोर्ट (Export) सुविधा का उपयोग:** जब भी आप किसी दुर्लभ ग्रन्थ, पृष्ठ, या भजन का ओसीआर और प्रूफरीडिंग पूर्ण करें, ऊपर स्थित **"निर्यात एवं डाउनलोड"** विंडो से Word (.docx), JSON, या TXT फ़ाइल तुरंत अपने कंप्यूटर पर डाउनलोड कर लें।
2. **स्थायी स्टोरेज (वैकल्पिक / भविष्य के लिए):**
   - Render पर $1/महीने में 1GB Persistent Disk जोड़ी जा सकती है।
   - हमारे कोड में `STORAGE_DIR` एनवायरनमेंट वेरिएबल का पूर्ण समर्थन है। अगर आप `/var/data` जैसी माउंटेड डिस्क जोड़ते हैं, तो सिर्फ `STORAGE_DIR=/var/data` सेट करने पर सारा डेटा हमेशा सुरक्षित रहेगा।

---

## 🩺 समस्या निवारण एवं चेकलिस्ट (Troubleshooting Checklist)

| समस्या | संभावित कारण | समाधान |
| :--- | :--- | :--- |
| **Render Port Binding Error** | पोर्ट मिसमैच | `Dockerfile` में `CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` सेट है, जिससे Render द्वारा दिया गया कोई भी पोर्ट स्वतः कनेक्ट हो जाता है। |
| **Health Check Timed Out** | `/api/health` का उत्तर न मिलना | `render.yaml` और `backend/main.py` में `/api/health` और `/health` दोनों एंडपॉइंट्स JSON लौटाते हैं। |
| **Cold Boot Delay (~50s)** | Render Free टियर 15 मिनट बाद स्लीप हो जाता है | पहली रिक्वेस्ट पर कंटेनर को जगने में 30–50 सेकंड लगते हैं। यह मुफ़्त टियर का सामान्य व्यवहार है। |
| **Memory Limit (512MB RAM)** | बड़े PDF या EasyOCR पर OOM खतरा | Tesseract डिफ़ॉल्ट इंजन है और मात्र ~150 MB RAM में काम करता है। EasyOCR लेज़ी-लोडेड है। यदि मेमोरी कम पड़े तो Tesseract इंजन का उपयोग करें। |
| **Tesseract missing hin data** | लिनक्स पर फ़ॉन्ट या मॉडल न मिलना | `Dockerfile` में `tesseract-ocr-hin`, `tesseract-ocr-san`, `fonts-deva` प्री-इन्स्टॉल्ड हैं और `config.py` पाथ स्वतः डिटेक्ट करता है। |
| **Permission Denied (Errno 13)** | नॉन-रूट यूज़र फ़ाइल नहीं लिख पा रहा | `Dockerfile` में `chmod -R 777 /app/backend/storage /app/models` सुनिश्चित है। |

---

*वाणीसंशोधक ग्रन्थ संरक्षण परियोजना — सर्वजन हिताय, सर्वजन सुखाय।*
