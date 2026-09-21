import { useState } from 'react';
import type { Company } from '../../types/company';
import { CheckCircle2, AlertTriangle, AlertCircle, ExternalLink, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';
import { cn } from '../../lib/utils';

interface CompanyCardProps {
  company: Company;
  isNew?: boolean;
}

export function CompanyCard({ company, isNew = false }: CompanyCardProps) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  
  const getICPScoreColor = (score: number) => {
    if (score >= 0.8) return 'bg-success/15 text-success border border-success/30';
    if (score >= 0.65) return 'bg-warning/15 text-warning border border-warning/30';
    return 'bg-danger/15 text-danger border border-danger/30';
  };

  const getValidationIcon = (status?: string) => {
    switch (status) {
      case 'validated':
        return (
          <span title="Fully Validated Domain">
            <CheckCircle2 className="h-4 w-4 text-success" />
          </span>
        );
      case 'partial':
        return (
          <span title="Partially Verified Firmographics">
            <AlertTriangle className="h-4 w-4 text-warning" />
          </span>
        );
      default:
        return (
          <span title="Unverified Profile">
            <AlertCircle className="h-4 w-4 text-text-disabled" />
          </span>
        );
    }
  };

  const formatFunding = (amount?: number) => {
    if (!amount) return '';
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`;
    return `$${amount}`;
  };

  const dimScores = company.dimension_scores || {};
  const dimensions = [
    { key: 'industry', label: 'Industry', match: dimScores.industry === 1.0 },
    { key: 'headcount', label: 'Headcount', match: dimScores.headcount === 1.0 },
    { key: 'funding_stage', label: 'Funding', match: dimScores.funding_stage === 1.0 },
    { key: 'geography', label: 'Geo', match: dimScores.geography === 1.0 },
    { key: 'revenue', label: 'Revenue', match: dimScores.revenue === 1.0 },
    { key: 'tech_stack', label: 'Tech', match: dimScores.tech_stack === 1.0 },
  ];

  return (
    <div
      className={cn(
        "p-4 glass-card hover:bg-surface/85 hover:border-border-hover transition-all duration-300 border-l-4",
        (company.icp_match_score ?? 0) >= 0.8 ? "border-l-success" : (company.icp_match_score ?? 0) >= 0.65 ? "border-l-warning" : "border-l-danger",
        isNew ? "animate-in slide-in-from-right fade-in duration-300" : ""
      )}
    >
      <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
        {/* Profile info */}
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-bold text-white leading-none truncate max-w-[200px]" title={company.name}>
              {company.name}
            </h4>
            
            {/* Domain URL */}
            {company.domain && (
              <a
                href={`https://${company.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-text-muted hover:text-primary inline-flex items-center gap-0.5 text-[11px] font-medium"
              >
                <span>{company.domain}</span>
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Industry */}
            {company.industry && (
              <span className="text-[10px] bg-secondaryBg px-2 py-0.5 rounded border border-border text-text-secondary">
                {company.industry}
              </span>
            )}
            {/* Headcount */}
            {company.headcount != null && (
              <span className="text-[10px] text-text-muted">
                {(company.headcount as number).toLocaleString()} employees
              </span>
            )}
            {/* Funding stage */}
            {company.funding_stage && (
              <span className="text-[10px] bg-accent/10 border border-accent/25 text-accent px-2 py-0.5 rounded-full font-semibold">
                {company.funding_stage} {formatFunding(company.funding_amount_usd)}
              </span>
            )}
            {/* Confidence pill */}
            {company.confidence_score != null && (
              <span className="text-[10px] text-text-muted inline-flex items-center gap-1 border border-border/50 px-1.5 py-0.5 rounded">
                <ShieldCheck className="h-3 w-3 text-primary" />
                {Math.round(company.confidence_score * 100)}% conf
              </span>
            )}
          </div>

          {/* Triggers Matched pills */}
          {company.triggers_matched && company.triggers_matched.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {company.triggers_matched.map((trigger) => (
                <span
                  key={trigger}
                  className="text-[9px] bg-surface/50 border border-border px-1.5 py-0.5 rounded text-text-muted font-mono"
                >
                  #{trigger}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Scoring & Validation Badges */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Validation Dot */}
          {getValidationIcon(company.validation_status)}

          {/* ICP Score & toggle */}
          <button
            onClick={() => setShowBreakdown(!showBreakdown)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-bold font-mono tracking-wide flex items-center gap-1 cursor-pointer transition-opacity hover:opacity-90",
              getICPScoreColor(company.icp_match_score ?? 0)
            )}
            title="Click to view score breakdown"
          >
            <span>{((company.icp_match_score ?? 0) * 100).toFixed(0)}% ICP</span>
            {showBreakdown ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Expandable Score Breakdown */}
      {showBreakdown && (
        <div className="mt-3 pt-2.5 border-t border-border/40 grid grid-cols-3 sm:grid-cols-6 gap-1.5 text-[11px] animate-in slide-in-from-top-1 duration-200">
          {dimensions.map((dim) => (
            <div
              key={dim.key}
              className={cn(
                "p-1.5 rounded border text-center transition-colors",
                dim.match
                  ? "bg-success/10 border-success/30 text-success"
                  : "bg-surface/40 border-border/50 text-text-muted"
              )}
            >
              <div className="font-semibold text-[10px]">{dim.label}</div>
              <div className="font-mono text-[9px] mt-0.5">
                {dim.match ? "✓ Match" : "— Miss"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CompanyCard;
