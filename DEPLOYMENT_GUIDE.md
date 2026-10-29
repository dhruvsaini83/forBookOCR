# वाणीसंशोधक (VaniScript) — पूर्ण डिप्लॉयमेंट मार्गदर्शिका (Deployment Guide)

इस मार्गदर्शिका में वाणीसंशोधक (Hindi Heritage OCR & Digital Granth Preservation Platform) को लाइव इंटरनेट पर डिप्लॉय करने की संपूर्ण प्रक्रिया समझाई गई है।

---

## 📌 डिप्लॉयमेंट से पहले महत्वपूर्ण तकनीकी तथ्य (Important Architecture Note)

### क्या यह पूरा प्रोजेक्ट केवल Vercel पर चल सकता है?
- **फ्रंटएंड (React 19):** ✅ **हाँ**, Vercel पर बहुत आसानी से और मुफ्त में चल सकता है।
- **बैकएंड (Python FastAPI + Tesseract + EasyOCR + PyTorch):** ❌ **केवल Vercel पर नहीं चल सकता।**
  - **कारण:** 
    1. Vercel एक **Serverless Jamstack** प्लेटफ़ॉर्म है जहाँ फ़ंक्शन का आकार अधिकतम 250 MB और निष्पादन समय 10–60 सेकंड तक सीमित होता है।
    2. इस प्रोजेक्ट में **Tesseract C++ बाइनरी**, **PyTorch**, **EasyOCR डीप लर्निंग मॉडल (300 MB)**, तथा **OpenCV** शामिल हैं, जिनका कुल आकार 1.5 GB से अधिक है।
    3. Vercel में कोई स्थायी डिस्क (Persistent Disk) नहीं होती, जबकि इस ऐप को पुरानी पुस्तकों के स्कैन और SQLite डेटाबेस को डिस्क पर सुरक्षित रखना होता है।

---

## 🚀 डिप्लॉयमेंट के २ सबसे आसान और लोकप्रिय तरीके (Top 2 Deployment Options)

---

### विकल्प १: All-in-One Docker डिप्लॉयमेंट (सर्वाधिक अनुशंसित / Most Recommended)
> **इस विकल्प में एक ही URL पर फ्रंटएंड और बैकएंड दोनों स्वतः डिप्लॉय हो जाते हैं। CORS या API URL कॉन्फ़िगर करने का कोई झंझट नहीं होता।**

#### A. Render.com पर डिप्लॉय (Free & Simple)
1. [Render.com](https://render.com/) पर जाएँ और अपने GitHub अकाउंट से लॉग इन करें।
2. डैशबोर्ड पर **New +** बटन पर क्लिक करें और **Web Service** चुनें।
3. अपनी रिपॉजिटरी कनेक्ट करें: `dhruvsaini83/forBookOCR`
4. सेटिंग्स भरें:
   - **Name:** `vaniscript-hindi-ocr` (या अपनी पसंद का नाम)
   - **Region:** `Singapore` या `Oregon`
   - **Runtime:** **Docker** (प्रोजेक्ट में मौजूद `Dockerfile` स्वतः डिटेक्ट हो जाएगी)
   - **Instance Type:** `Free`
5. **Create Web Service** पर क्लिक करें।
6. 3-5 मिनट में आपकी साइट लाइव हो जाएगी और आपको एक लाइव लिंक मिलेगा (उदा. `https://vaniscript-hindi-ocr.onrender.com`)।

---

#### B. Hugging Face Spaces पर डिप्लॉय (100% Free • 16 GB RAM • 2 vCPU)
> *EasyOCR और PyTorch के लिए Hugging Face Spaces सबसे शक्तिशाली मुफ़्त विकल्प है।*
1. [huggingface.co](https://huggingface.co/) पर अकाउंट बनाएँ।
2. **Spaces** टैब में जाकर **Create new Space** पर क्लिक करें।
3. **Space SDK** में **Docker** चुनें (Blank Docker)।
4. अपने स्पेस की Git रिपॉजिटरी को क्लोन करें या GitHub रिपॉजिटरी को जोड़ें।
5. प्रोजेक्ट की सभी फ़ाइलें पुश करते ही Hugging Face डॉकर कंटेनर बनाकर 16 GB रैम के साथ ऐप को हमेशा के लिए मुफ्त में लाइव कर देगा।

---

#### C. Railway.app पर डिप्लॉय
1. [Railway.app](https://railway.app/) पर जाएँ और GitHub से लॉग इन करें।
2. **New Project** -> **Deploy from GitHub repo** चुनें।
3. `dhruvsaini83/forBookOCR` चुनें।
4. Railway स्वतः `Dockerfile` पहचान कर ऐप को डिप्लॉय कर देगा और आपको पब्लिक डोमेन प्रदान करेगा।

---

### विकल्प २: स्प्लिट डिप्लॉयमेंट (Frontend on Vercel + Backend on Render/Railway)
> *यदि आप फ्रंटएंड को Vercel की अत्यधिक तीव्र ग्लोबल CDN पर और बैकएंड को Render/Railway पर अलग-अलग रखना चाहते हैं:*

#### चरण १: बैकएंड को Render या Railway पर डिप्लॉय करें
- ऊपर दिए गए **विकल्प १** के अनुसार बैकएंड को Render पर डिप्लॉय करें और उसका URL प्राप्त करें (उदा. `https://my-backend.onrender.com`)।

#### चरण २: फ्रंटएंड को Vercel पर डिप्लॉय करें
1. [Vercel.com](https://vercel.com/) पर जाएँ और GitHub से लॉग इन करें।
2. **Add New...** -> **Project** पर क्लिक करें।
3. `dhruvsaini83/forBookOCR` रिपॉजिटरी चुनें।
4. **Project Settings:**
   - **Framework Preset:** `Vite`
   - **Root Directory:** Edit पर क्लिक करें और `frontend` चुनें।
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. **Environment Variables:**
   - Name: `VITE_API_URL`
   - Value: `https://my-backend.onrender.com` (आपके बैकएंड का लाइव URL)
6. **Deploy** पर क्लिक करें।
7. Vercel 1 मिनट में आपका फ्रंटएंड लाइव कर देगा (उदा. `https://for-book-ocr.vercel.app`)।

---

## 💻 अपने खुद के सर्वर या VPS पर चलाना (Self-Hosted / VPS)

यदि आपके पास कोई Linux VPS (Ubuntu / Debian / AWS EC2 / DigitalOcean) है:

```bash
# 1. रिपॉजिटरी क्लोन करें
git clone https://github.com/dhruvsaini83/forBookOCR.git
cd forBookOCR

# 2. डॉकर इमेज बिल्ड करें
docker build -t vaniscript .

# 3. बैकग्राउंड में कंटेनर चलाएँ
docker run -d -p 8000:8000 --restart always --name vaniscript-app vaniscript
```

अब आपका ऐप सर्वर के IP या डोमेन पर पोर्ट 8000 पर लाइव रहेगा।

---

## 🛠️ प्रोजेक्ट में जोड़ी गई डिप्लॉयमेंट फ़ाइलें
- [Dockerfile](file:///d:/project/forBook%20new/Dockerfile): बहु-स्तरीय (Multi-stage) प्रोडक्शन डॉकर कॉन्फ़िगरेशन।
- [requirements.txt](file:///d:/project/forBook%20new/requirements.txt): क्लाउड कंटेनर हेतु पायथन निर्भरताएँ।
- [render.yaml](file:///d:/project/forBook%20new/render.yaml): Render पर 1-क्लिक ऑटो डिप्लॉय ब्लूप्रिंट।
- [frontend/vercel.json](file:///d:/project/forBook%20new/frontend/vercel.json): Vercel SPA रूटिंग रीराइट्स।

