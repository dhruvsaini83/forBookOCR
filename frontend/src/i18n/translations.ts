export type Language = 'hi' | 'en';

export const translations = {
  hi: {
    appTitle: "वाणीसंशोधक",
    appSubtitle: "देवनागरी पाण्डुलिपि एवं दुर्लभ धार्मिक ग्रन्थ OCR संरक्षण प्रणाली",
    tagline: "४-चरणीय स्वतंत्र सत्यापन द्वारा सटीक, संपादन योग्य एवं प्रतिलिपि योग्य डिजिटल पाठ",
    
    // Header
    navUpload: "नया दस्तावेज़ अपलोड करें",
    navHistory: "ग्रन्थ पुस्तकालय (इतिहास)",
    navBenchmark: "सटीकता मानक (CER/WER)",
    navSamples: "परीक्षण नमूने",
    langToggle: "English",
    
    // Upload Modal
    uploadTitle: "प्राचीन ग्रन्थ अथवा पाण्डुलिपि पृष्ठ अपलोड करें",
    uploadDesc: "JPG, PNG, WEBP अथवा बहु-पृष्ठीय PDF संचिकाएँ स्वीकार्य हैं (अधिकतम 50 MB)।",
    dragDropText: "संचिका यहाँ खींचें और छोड़ें",
    orClickText: "अथवा अपने उपकरण से संचिका चुनें",
    cameraButton: "कैमरे से फोटो खींचें",
    docTitleLabel: "ग्रन्थ/दस्तावेज़ का शीर्षक",
    docTitlePlaceholder: "उदा. श्री रामचरितमानस — सुंदरकाण्ड",
    collectionLabel: "संग्रह / श्रेणी",
    collections: {
      general: "सामान्य (General)",
      ramayana: "रामायण / रामकाव्य",
      bhajan: "भजन एवं पद संग्रह",
      sant: "संत साहित्य (कबीर/सूर/तुलसी)",
      vedas: "वेद / उपनिषद् / स्तोत्र",
      manuscript: "दुर्लभ पाण्डुलिपि (Manuscript)"
    },
    autoProcessCheckbox: "अपलोड के साथ तुरंत सत्यापन प्रक्रिया प्रारंभ करें",
    submitUpload: "सत्यापन एवं निष्कर्षण प्रारंभ करें",
    uploadingStatus: "संचिका अपलोड एवं पृष्ठ विश्लेषण हो रहा है...",
    
    // Samples Section
    sampleTitle: "त्वरित परीक्षण हेतु ऐतिहासिक नमूने",
    loadSampleBtn: "यह नमूना लोड करें",
    
    // Split Viewer
    sourceImageTab: "मूल पाण्डुलिपि पृष्ठ (Source Document)",
    verifiedTextTab: "सत्यापित देवनागरी पाठ (Verified Text)",
    pageNavigator: "पृष्ठ संख्या",
    ofPages: "कुल",
    prevPage: "पिछला पृष्ठ",
    nextPage: "अगला पृष्ठ",
    
    // Image Controls
    originalView: "मूल रंग (Original)",
    enhancedView: "उन्नत विरोधाभास (CLAHE)",
    binarizedView: "मात्रा-संरक्षित श्वेत-श्याम (Binarized)",
    zoomIn: "बड़ा करें (+)",
    zoomOut: "छोटा करें (-)",
    resetZoom: "पुनः व्यवस्थित करें",
    rotateRight: "९०° घुमाएँ",
    toggleBboxes: "वर्ण परिसीमाएँ (Bounding Boxes)",
    
    // Text Editor & Verification
    copyVerifiedText: "सत्यापित पाठ कॉपी करें",
    copyRawText: "मूल OCR पाठ कॉपी करें",
    copySuccessToast: "सत्यापित देवनागरी पाठ क्लिपबोर्ड पर सफलतापूर्वक कॉपी किया गया!",
    downloadDoc: "निर्यात एवं डाउनलोड",
    saveChanges: "सुधार सहेजें",
    markConfirmed: "मानवीय रूप से प्रमाणित करें (Confirm)",
    
    // Verification Stages
    stagesTitle: "४-चरणीय OCR सत्यापन एवं भाषाई शुद्धि तंत्र",
    stage1Name: "चरण १: चित्र पूर्व-प्रसंस्करण",
    stage1Desc: "झुकाव सुधार (Deskew), अस्पष्टता माप एवं मात्रा-संरक्षण",
    stage2Name: "चरण २: प्राथमिक देवनागरी OCR",
    stage2Desc: "टेसरेक्ट LSTM तंत्र (हिन्दी + देवनागरी + संस्कृत मॉडल)",
    stage3Name: "चरण ३: स्वतंत्र दोहरा सत्यापन",
    stage3Desc: "द्वि-इंजन मिलान, वर्ण-स्तर विसंगति एवं मात्रा भ्रम पहचान",
    stage4Name: "चरण ४: भाषाई एवं यूनिकोड नियम",
    stage4Desc: "अमान्य मात्रा संयोजन एवं प्राचीन/धार्मिक शब्दावली संरक्षण",
    stage5Name: "चरण ५: समग्र सामंजस्य एवं दृष्टिगत संवीक्षा",
    stage5Desc: "छंद रचना, दोहा-चौपाई चरण समता एवं कटआउट निरीक्षण",
    
    // Status Badges
    statusVerified: "उपलब्ध परीक्षणों द्वारा सत्यापित",
    statusReview: "समीक्षा अपेक्षित (Needs Review)",
    statusConfirmed: "मानवीय रूप से प्रमाणित (Confirmed)",
    statusProcessing: "प्रक्रियाधीन...",
    
    // Word Inspector
    inspectTitle: "वर्ण एवं शब्द संवीक्षा",
    sourcePatchTitle: "मूल पाण्डुलिपि से आवर्धित अंश (Source Image Patch)",
    primaryReading: "प्राथमिक OCR पाठ:",
    secondaryReading: "स्वतंत्र द्वितीयक पाठ:",
    confidenceLabel: "विश्वास स्तर (Confidence):",
    linguisticNote: "भाषाई विश्लेषण:",
    suggestionLabel: "सुझाया गया संशोधन:",
    acceptSuggestion: "सुझाव स्वीकार करें",
    manualCorrectionLabel: "स्वयं सुधार दर्ज करें:",
    applyCorrection: "सुधार लागू करें",
    closeInspector: "बंद करें",
    
    // Audit Trail
    changeHistoryTitle: "सुधार एवं संशोधन इतिहास (Audit Trail)",
    noChangesYet: "अभी तक कोई मानवीय संशोधन नहीं किया गया है।",
    
    // Benchmark
    benchmarkTitle: "देवनागरी OCR ऐतिहासिक सटीकता मानक (Benchmark Suite)",
    benchmarkDesc: "प्राचीन मुद्रित ग्रन्थों एवं पाण्डुलिपियों के प्रामाणिक संदर्भ पाठ पर CER एवं WER का परीक्षण",
    cerLabel: "वर्ण त्रुटि दर (CER):",
    werLabel: "शब्द त्रुटि दर (WER):",
    accuracyLabel: "सटीकता दर (Accuracy):",
    runTestBtn: "सटीकता जाँचें",
    
    // Export Modal
    exportModalTitle: "दस्तावेज़ निर्यात एवं डाउनलोड",
    exportTxt: "शुद्ध देवनागरी पाठ (.TXT, UTF-8)",
    exportDocx: "माइक्रोसॉफ्ट वर्ड प्रारूप (.DOCX)",
    exportJson: "संरचित आँकड़े (.JSON, निर्देशांक सहित)",
    exportHtml: "मुद्रण योग्य पृष्ठ / PDF (.HTML)",
    downloadBtn: "डाउनलोड करें",
    
    // Transparency Disclaimer
    transparencyNotice: "महत्वपूर्ण ध्यातव्य: यह प्रणाली स्वचालित बहु-स्तरीय सत्यापन करती है; यह १००% अचूकता का मिथ्या दावा नहीं करती। प्राचीन धार्मिक ग्रन्थों के संरक्षण हेतु मूल पाण्डुलिपि से दृष्टिगत मिलान सदैव अनुशंसित है।"
  },
  
  en: {
    appTitle: "VaniScript",
    appSubtitle: "Devanagari Manuscript & Rare Religious Literature OCR Preservation Platform",
    tagline: "4-Stage Independent Verification Pipeline for Accurate, Editable, and Copyable Digital Text",
    
    // Header
    navUpload: "Upload Document",
    navHistory: "Document Library",
    navBenchmark: "Accuracy Benchmark",
    navSamples: "Sample Granths",
    langToggle: "हिंदी",
    
    // Upload Modal
    uploadTitle: "Upload Rare Hindi Book or Manuscript Page",
    uploadDesc: "Supports JPG, PNG, WEBP, and multi-page PDF documents (up to 50 MB).",
    dragDropText: "Drag and drop your file here",
    orClickText: "or click to browse from device",
    cameraButton: "Take Photo with Camera",
    docTitleLabel: "Document / Book Title",
    docTitlePlaceholder: "e.g., Shri Ramcharitmanas — Sundarkand",
    collectionLabel: "Collection / Category",
    collections: {
      general: "General Literature",
      ramayana: "Ramayana / Rama Kavya",
      bhajan: "Bhajan & Pad Collection",
      sant: "Sant Literature (Kabir/Sur/Tulsi)",
      vedas: "Vedas / Upanishads / Stotras",
      manuscript: "Rare Manuscript / Lithograph"
    },
    autoProcessCheckbox: "Start verification pipeline immediately upon upload",
    submitUpload: "Begin Extraction & Verification",
    uploadingStatus: "Uploading and analyzing document pages...",
    
    // Samples Section
    sampleTitle: "Authentic Historical Manuscript Samples",
    loadSampleBtn: "Load This Sample",
    
    // Split Viewer
    sourceImageTab: "Source Manuscript Page",
    verifiedTextTab: "Verified Devanagari Text",
    pageNavigator: "Page",
    ofPages: "of",
    prevPage: "Previous Page",
    nextPage: "Next Page",
    
    // Image Controls
    originalView: "Original Scan",
    enhancedView: "CLAHE Enhanced",
    binarizedView: "Matra-Preserving B/W",
    zoomIn: "Zoom In (+)",
    zoomOut: "Zoom Out (-)",
    resetZoom: "Reset View",
    rotateRight: "Rotate 90°",
    toggleBboxes: "Word Bounding Boxes",
    
    // Text Editor & Verification
    copyVerifiedText: "Copy Verified Text",
    copyRawText: "Copy Raw OCR Text",
    copySuccessToast: "Verified Devanagari text copied to clipboard successfully!",
    downloadDoc: "Export & Download",
    saveChanges: "Save Changes",
    markConfirmed: "Manually Confirm",
    
    // Verification Stages
    stagesTitle: "4-Stage OCR Verification & Linguistic Validation System",
    stage1Name: "Stage 1: Image Preprocessing",
    stage1Desc: "Devanagari deskew, blur/contrast metrics & thin-stroke preservation",
    stage2Name: "Stage 2: Primary Devanagari OCR",
    stage2Desc: "Tesseract LSTM engine with hin+Devanagari+san language models",
    stage3Name: "Stage 3: Independent Cross-Verification",
    stage3Desc: "Dual-engine cross-verification, alignment & glyph confusion detector",
    stage4Name: "Stage 4: Linguistic & Unicode Rules",
    stage4Desc: "Devanagari Unicode integrity & historical orthography preservation",
    stage5Name: "Stage 5: Structural Consistency Audit",
    stage5Desc: "Verse boundary balance, doha meter symmetry & word crop inspection",
    
    // Status Badges
    statusVerified: "Verified by Available Checks",
    statusReview: "Needs Review",
    statusConfirmed: "Manually Confirmed",
    statusProcessing: "Processing...",
    
    // Word Inspector
    inspectTitle: "Character & Word Inspector",
    sourcePatchTitle: "Magnified Source Image Cutout",
    primaryReading: "Primary Engine Reading:",
    secondaryReading: "Secondary Engine Reading:",
    confidenceLabel: "Confidence Score:",
    linguisticNote: "Linguistic Note:",
    suggestionLabel: "Suggested Reading:",
    acceptSuggestion: "Accept Suggestion",
    manualCorrectionLabel: "Enter Manual Correction:",
    applyCorrection: "Apply Correction",
    closeInspector: "Close",
    
    // Audit Trail
    changeHistoryTitle: "Correction Log & Audit Trail",
    noChangesYet: "No manual changes recorded yet.",
    
    // Benchmark
    benchmarkTitle: "Devanagari OCR Accuracy Benchmark Suite",
    benchmarkDesc: "Evaluating Character Error Rate (CER) and Word Error Rate (WER) against manually verified historical reference texts",
    cerLabel: "Character Error Rate (CER):",
    werLabel: "Word Error Rate (WER):",
    accuracyLabel: "Overall Accuracy:",
    runTestBtn: "Evaluate Accuracy",
    
    // Export Modal
    exportModalTitle: "Export Document",
    exportTxt: "Clean Text (.TXT, UTF-8)",
    exportDocx: "Microsoft Word Document (.DOCX)",
    exportJson: "Structured JSON with Coordinates",
    exportHtml: "Printable Page / PDF View (.HTML)",
    downloadBtn: "Download",
    
    // Transparency Disclaimer
    transparencyNotice: "Important Note: This system performs multi-stage automated verification and never claims 100% correctness. Comparison against the original manuscript is essential for historical preservation."
  }
};
