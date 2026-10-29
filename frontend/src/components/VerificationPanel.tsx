import React, { useState } from 'react';
import { 
  ChevronDown, ChevronUp, CheckCircle2, AlertTriangle, 
  ShieldCheck, Sliders, Cpu, GitCompare, BookCheck, CheckSquare, ShieldAlert 
} from 'lucide-react';
import type { StageMetrics } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface VerificationPanelProps {
  metrics?: StageMetrics;
  unresolvedCount?: number;
  failedPagesCount?: number;
  lang: Language;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({ 
  metrics, 
  unresolvedCount = 0, 
  failedPagesCount = 0, 
  lang 
}) => {
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
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">अस्पष्टता माप (Laplacian)</span>
            <span className="font-bold text-stone-900 text-sm">{metrics.stage1?.laplacian_variance}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">विरोधाभास (Contrast)</span>
            <span className="font-bold text-stone-900 text-sm">{metrics.stage1?.contrast_rating}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">झुकाव कोण (Deskew)</span>
            <span className="font-bold text-stone-900 text-sm">{metrics.stage1?.detected_skew_angle}°</span>
          </div>
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">आयाम (Dimensions)</span>
            <span className="font-bold text-stone-900 text-sm">
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
          <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-stone-400 block text-[10px]">कुल निष्कर्षित शब्द</span>
            <span className="font-bold text-stone-900 text-sm">{metrics.stage2?.word_count}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200">
            <span className="text-emerald-700 block text-[10px]">उच्च विश्वास (≥82%)</span>
            <span className="font-bold text-emerald-950 text-sm">{metrics.stage2?.high_conf_words}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
            <span className="text-amber-700 block text-[10px]">मध्यम विश्वास (60-82%)</span>
            <span className="font-bold text-amber-950 text-sm">{metrics.stage2?.med_conf_words}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200">
            <span className="text-rose-700 block text-[10px]">अल्प विश्वास (&lt;60%)</span>
            <span className="font-bold text-rose-950 text-sm">{metrics.stage2?.low_conf_words}</span>
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
      badge: `सहमति: ${metrics.stage3?.agreement_rate_pct}% (${metrics.stage3?.disagreements || 0} भेद)`,
      details: (
        <div className="pt-2 text-xs text-stone-600 font-devanagari space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
              <span className="text-stone-400 block text-[10px]">द्वितीयक मॉडल (Secondary Pass)</span>
              <span className="font-bold text-stone-900 truncate block text-xs">
                {metrics.stage3?.secondary_engine || 'Tesseract Script/Devanagari (PSM 3)'}
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200">
              <span className="text-emerald-700 block text-[10px]">सहमति शब्द</span>
              <span className="font-bold text-emerald-950 text-sm">{metrics.stage3?.agreements}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
              <span className="text-amber-700 block text-[10px]">संदेहास्पद मतभेद</span>
              <span className="font-bold text-amber-950 text-sm">{metrics.stage3?.disagreements}</span>
            </div>
          </div>
          {metrics.stage3?.discrepancy_breakdown && Object.keys(metrics.stage3.discrepancy_breakdown).length > 0 && (
            <div className="p-2.5 rounded-xl bg-amber-50/50 border border-amber-200 text-xs">
              <span className="font-bold text-amber-950 block mb-1">पहचाने गए मतभेद:</span>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(metrics.stage3.discrepancy_breakdown).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 rounded-lg bg-white border border-amber-200 text-amber-900 text-[11px] font-medium">
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
      badge: `${metrics.stage4?.historical_forms_preserved || 0} प्राचीन संरक्षित | ${metrics.stage4?.unicode_anomalies_detected || 0} विसंगति`,
      details: (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 text-xs text-stone-600 font-devanagari">
          <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200">
            <span className="text-emerald-700 block text-[10px]">प्राचीन अवधी/ब्रज वर्तनी संरक्षित</span>
            <span className="font-bold text-emerald-950 text-sm">{metrics.stage4?.historical_forms_preserved}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-purple-50 border border-purple-200">
            <span className="text-purple-700 block text-[10px]">यूनिकोड/मात्रा विसंगति</span>
            <span className="font-bold text-purple-950 text-sm">{metrics.stage4?.unicode_anomalies_detected}</span>
          </div>
          <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
            <span className="text-amber-700 block text-[10px]">परामर्श सुझाव</span>
            <span className="font-bold text-amber-950 text-sm">{metrics.stage4?.advisory_suggestions_generated}</span>
          </div>
        </div>
      ),
    },
    {
      num: 5,
      title: t.stage5Name,
      desc: t.stage5Desc,
      icon: <CheckSquare className="w-4 h-4 text-indigo-700" />,
      status: (metrics.stage5?.flagged_words_count || 0) === 0 ? 'passed' : 'warning',
      badge: `${metrics.stage5?.flagged_words_count || 0} ध्वजांकित कटआउट`,
      details: (
        <div className="pt-2 text-xs text-stone-600 font-devanagari space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-200">
              <span className="text-stone-400 block text-[10px]">कुल शब्द</span>
              <span className="font-bold text-stone-900 text-sm">{metrics.stage5?.total_words}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
              <span className="text-amber-700 block text-[10px]">कटआउट युक्त ध्वजांकित शब्द</span>
              <span className="font-bold text-amber-950 text-sm">{metrics.stage5?.flagged_words_count}</span>
            </div>
          </div>
          {metrics.stage5?.line_warnings && metrics.stage5.line_warnings.length > 0 && (
            <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-900">
              {metrics.stage5.line_warnings.map((w, idx) => (
                <div key={idx}>⚠️ {w}</div>
              ))}
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <section aria-labelledby="verification-heading" className="bg-white rounded-2xl border border-stone-200/90 p-3 sm:p-5 shadow-2xs">
      <div className="flex flex-wrap items-center justify-between gap-2.5 pb-3 mb-3 sm:mb-4 border-b border-stone-100">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-vedic-700" />
          <h2 id="verification-heading" className="text-sm font-bold text-stone-900 font-devanagari">
            {t.stagesTitle}
          </h2>
        </div>
        
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          {unresolvedCount > 0 && (
            <span className="text-[11px] sm:text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-devanagari">
              {unresolvedCount} संदेहास्पद शब्द
            </span>
          )}
          {failedPagesCount > 0 && (
            <span className="text-[11px] sm:text-xs font-semibold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-900 border border-rose-300 font-devanagari">
              {failedPagesCount} पृष्ठ विफल
            </span>
          )}
          <span className="text-[11px] sm:text-xs font-semibold px-2.5 py-0.5 rounded-full bg-vedic-50 text-vedic-950 border border-vedic-200 font-devanagari">
            {metrics.stage5?.overall_status_hi || metrics.stage5?.overall_status || 'समीक्षा अपेक्षित'}
          </span>
        </div>
      </div>

      <div className="space-y-2">
        {stages.map((st) => (
          <div 
            key={`stage-${st.num}`}
            className="rounded-xl border border-stone-200/90 overflow-hidden transition-all duration-150"
          >
            <button
              type="button"
              onClick={() => toggleStage(st.num)}
              className="w-full flex items-center justify-between p-2.5 sm:p-3 bg-stone-50/80 hover:bg-stone-100/70 text-left transition-colors gap-2"
              aria-expanded={expandedStage === st.num}
              aria-controls={`stage-content-${st.num}`}
            >
              <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-white border border-stone-200 flex items-center justify-center shrink-0 shadow-2xs">
                  {st.icon}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-stone-900 font-devanagari truncate">
                      {st.title}
                    </span>
                    {st.status === 'passed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    )}
                  </div>
                  <p className="text-[11px] text-stone-500 font-devanagari hidden sm:block truncate">
                    {st.desc}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] font-semibold text-stone-700 bg-white px-2 py-0.5 sm:py-1 rounded-md border border-stone-200 font-devanagari shadow-2xs hidden xs:inline-block">
                  {st.badge}
                </span>
                {expandedStage === st.num ? (
                  <ChevronUp className="w-4 h-4 text-stone-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-stone-500" />
                )}
              </div>
            </button>

            {expandedStage === st.num && (
              <div 
                id={`stage-content-${st.num}`}
                className="p-3 bg-white border-t border-stone-200 animate-in fade-in duration-100"
              >
                {st.details}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Mandatory Accuracy & Transparency Notice */}
      <div className="mt-3.5 p-3 rounded-xl bg-amber-50/80 border border-amber-200/90 flex items-start gap-2.5 text-xs text-amber-950 font-devanagari">
        <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          {t.transparencyNotice}
        </p>
      </div>
    </section>
  );
};
