import { memo } from 'react';
import { cn } from '../lib/utils';

/**
 * Research fields display component.
 * Shows research fields as styled badges.
 */
const ResearchFieldsBadges = memo(function ResearchFieldsBadges({ fields, maxDisplay = 3, showCount = false }) {
  if (!fields || fields.length === 0) {
    return null;
  }

  const displayFields = fields.slice(0, maxDisplay);
  const remaining = fields.length - maxDisplay;

  return (
    <div className="flex flex-wrap gap-1.5">
      {displayFields.map((field) => (
        <span
          key={field.id}
          className={cn(
            "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors border",
            "bg-primary/5 text-primary border-primary/20 hover:bg-primary/10"
          )}
          title={showCount ? `${field.count} papers, avg score ${field.score.toFixed(2)}` : field.name}
        >
          {field.name}
          {showCount && (
            <span className="ml-1 opacity-70">({field.count})</span>
          )}
        </span>
      ))}
      {remaining > 0 && (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-secondary text-secondary-foreground border border-secondary hover:bg-secondary/80 transition-colors">
          +{remaining}
        </span>
      )}
    </div>
  );
});

export default ResearchFieldsBadges;
