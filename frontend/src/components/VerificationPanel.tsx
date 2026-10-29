import React, { useState } from 'react';
import { 
  ChevronDown, ChevronUp, CheckCircle2, AlertTriangle, 
  ShieldCheck, Sliders, Cpu, GitCompare, BookCheck, ShieldAlert 
} from 'lucide-react';
import type { StageMetrics } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface VerificationPanelProps {
  metrics?: StageMetrics;
  lang: Language;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({ metrics, lang }) => {
  const t = translations[lang];
  const [expandedStage, setExpandedStage] = useState<number | null>(null);

  if (!metrics) return null;

  const toggleStage = (stageNum: number) => {
    setExpandedStage(expandedStage === stageNum ? null : stageNum);
  };

  const stages = [
    {
      num: 1,
      title: t.stage1Name,
      desc: t.stage1Desc,
      icon: <Sliders className="w-4 h-4 text-vedic-700" />,
      status: metrics.stage1?.is_quality_acceptable ? 'passed' : 'warning',
      badge: `${metrics.stage1?.blur_rating || 'Sharp'} | झुकाव: ${metrics.stage1?.detected_skew_angle || 0}°`,
      details: (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-xs text-stone-600 font-devanagari">
          <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">अस्पष्टता माप (Laplacian)</span>
            <span className="font-bold text-stone-800">{metrics.stage1?.laplacian_variance}</span>
          </div>
          <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">विरोधाभास (Contrast)</span>
            <span className="font-bold text-stone-800">{metrics.stage1?.contrast_rating}</span>
          </div>
          <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">झुकाव कोण (Deskew Angle)</span>
            <span className="font-bold text-stone-800">{metrics.stage1?.detected_skew_angle}°</span>
          </div>
          <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">आयाम (Dimensions)</span>
            <span className="font-bold text-stone-800">
              {metrics.stage1?.dimensions?.width}×{metrics.stage1?.dimensions?.height}
            </span>
          </div>
        </div>
      ),
    },
    {
      num: 2,
      title: t.stage2Name,
      desc: t.stage2Desc,
      icon: <Cpu className="w-4 h-4 text-blue-700" />,
      status: 'passed',
      badge: `औसत विश्वास: ${metrics.stage2?.average_confidence}%`,
      details: (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-xs text-stone-600 font-devanagari">
          <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">कुल निष्कर्षित शब्द</span>
            <span className="font-bold text-stone-800">{metrics.stage2?.word_count}</span>
          </div>
          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200">
            <span className="text-emerald-700 block text-[10px]">उच्च विश्वास (≥82%)</span>
            <span className="font-bold text-emerald-900">{metrics.stage2?.high_conf_words}</span>
          </div>
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
            <span className="text-amber-700 block text-[10px]">मध्यम विश्वास (60-82%)</span>
            <span className="font-bold text-amber-900">{metrics.stage2?.med_conf_words}</span>
          </div>
          <div className="p-2 rounded-lg bg-rose-50 border border-rose-200">
            <span className="text-rose-700 block text-[10px]">अल्प विश्वास (&lt;60%)</span>
            <span className="font-bold text-rose-900">{metrics.stage2?.low_conf_words}</span>
          </div>
        </div>
      ),
    },
    {
      num: 3,
      title: t.stage3Name,
      desc: t.stage3Desc,
      icon: <GitCompare className="w-4 h-4 text-purple-700" />,
      status: (metrics.stage3?.agreement_rate_pct || 0) >= 80 ? 'passed' : 'warning',
      badge: `सहमति दर: ${metrics.stage3?.agreement_rate_pct}% (${metrics.stage3?.disagreements || 0} मतभेद)`,
      details: (
        <div className="pt-2 text-xs text-stone-600 font-devanagari space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded-lg bg-stone-50 border border-stone-200">
              <span className="text-stone-400 block text-[10px]">द्वितीयक इंजन</span>
              <span className="font-bold text-stone-800 truncate block">
                {metrics.stage3?.secondary_engine || 'Tesseract Script/Devanagari'}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200">
              <span className="text-emerald-700 block text-[10px]">सहमति शब्द</span>
              <span className="font-bold text-emerald-900">{metrics.stage3?.agreements}</span>
            </div>
            <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
              <span className="text-amber-700 block text-[10px]">मतभेद शब्द</span>
              <span className="font-bold text-amber-900">{metrics.stage3?.disagreements}</span>
            </div>
          </div>
          {metrics.stage3?.discrepancy_breakdown && Object.keys(metrics.stage3.discrepancy_breakdown).length > 0 && (
            <div className="p-2 rounded-lg bg-amber-50/50 border border-amber-200 text-[11px]">
              <span className="font-bold text-amber-900 block mb-1">मतभेद वर्गीकरण:</span>
              <div className="flex flex-wrap gap-2">
                {Object.entries(metrics.stage3.discrepancy_breakdown).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 rounded bg-white border border-amber-200 text-amber-900">
                    {k}: {v}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ),
    },
    {
      num: 4,
      title: t.stage4Name,
      desc: t.stage4Desc,
      icon: <BookCheck className="w-4 h-4 text-emerald-700" />,
      status: metrics.stage4?.unicode_anomalies_detected === 0 ? 'passed' : 'warning',
      badge: `${metrics.stage4?.historical_forms_preserved || 0} प्राचीन शब्द संरक्षित | ${metrics.stage4?.unicode_anomalies_detected || 0} विसंगति`,
      details: (
        <div className="grid grid-cols-3 gap-2 pt-2 text-xs text-stone-600 font-devanagari">
          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200">
            <span className="text-emerald-700 block text-[10px]">प्राचीन वर्तनी संरक्षित</span>
            <span className="font-bold text-emerald-900">{metrics.stage4?.historical_forms_preserved}</span>
          </div>
          <div className="p-2 rounded-lg bg-purple-50 border border-purple-200">
            <span className="text-purple-700 block text-[10px]">यूनिकोड/मात्रा विसंगति</span>
            <span className="font-bold text-purple-900">{metrics.stage4?.unicode_anomalies_detected}</span>
          </div>
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
            <span className="text-amber-700 block text-[10px]">उपलब्ध परामर्श सुझाव</span>
            <span className="font-bold text-amber-900">{metrics.stage4?.advisory_suggestions_generated}</span>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-stone-100">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-vedic-600" />
          <h2 className="text-sm font-bold text-stone-900 font-devanagari">
            {t.stagesTitle}
          </h2>
        </div>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-vedic-50 text-vedic-900 border border-vedic-200 font-devanagari">
          {metrics.stage5?.overall_status_hi || metrics.stage5?.overall_status || 'समीक्षा अपेक्षित'}
        </span>
      </div>

      <div className="space-y-2.5">
        {stages.map((st) => (
          <div 
            key={`stage-${st.num}`}
            className="rounded-xl border border-stone-200/90 overflow-hidden transition-all duration-150"
          >
            <button
              onClick={() => toggleStage(st.num)}
              className="w-full flex items-center justify-between p-3 bg-stone-50 hover:bg-stone-100/70 text-left transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-white border border-stone-200 flex items-center justify-center shrink-0">
                  {st.icon}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-stone-900 font-devanagari">
                      {st.title}
                    </span>
                    {st.status === 'passed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    )}
                  </div>
                  <p className="text-[11px] text-stone-500 font-devanagari hidden sm:block">
                    {st.desc}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-stone-600 bg-white px-2.5 py-1 rounded-md border border-stone-200 font-devanagari">
                  {st.badge}
                </span>
                {expandedStage === st.num ? (
                  <ChevronUp className="w-4 h-4 text-stone-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-stone-400" />
                )}
              </div>
            </button>

            {expandedStage === st.num && (
              <div className="p-3 bg-white border-t border-stone-200 animate-in fade-in duration-100">
                {st.details}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Mandatory Accuracy & Transparency Notice */}
      <div className="mt-4 p-3 rounded-xl bg-amber-50/70 border border-amber-200/90 flex items-start gap-2.5 text-xs text-amber-900 font-devanagari">
        <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          {t.transparencyNotice}
        </p>
      </div>
    </div>
  );
};
