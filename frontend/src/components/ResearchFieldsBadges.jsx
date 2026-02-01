/**
 * Research fields display component.
 * Shows research fields as purple rounded badges.
 */
function ResearchFieldsBadges({ fields, maxDisplay = 3, showCount = false }) {
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
          className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full"
          title={showCount ? `${field.count} papers, avg score ${field.score.toFixed(2)}` : field.name}
        >
          {field.name}
          {showCount && (
            <span className="ml-1 text-purple-500">({field.count})</span>
          )}
        </span>
      ))}
      {remaining > 0 && (
        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">
          +{remaining}
        </span>
      )}
    </div>
  );
}

export default ResearchFieldsBadges;
