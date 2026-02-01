import { motion } from 'framer-motion';
import { cn } from '../lib/utils';
import { BookOpen, Users, Share2, Activity } from 'lucide-react';

function StatsCard({ title, value, icon, color = 'blue', delay = 0 }) {
  // Map color names to specific Tailwind classes for light/dark modes
  const colorStyles = {
    blue: {
      bg: "bg-blue-50 dark:bg-blue-900/10",
      border: "border-blue-100 dark:border-blue-800",
      text: "text-blue-600 dark:text-blue-400",
      iconBg: "bg-blue-100 dark:bg-blue-900/30",
      iconText: "text-blue-700 dark:text-blue-300"
    },
    green: {
      bg: "bg-emerald-50 dark:bg-emerald-900/10",
      border: "border-emerald-100 dark:border-emerald-800",
      text: "text-emerald-600 dark:text-emerald-400",
      iconBg: "bg-emerald-100 dark:bg-emerald-900/30",
      iconText: "text-emerald-700 dark:text-emerald-300"
    },
    purple: {
      bg: "bg-purple-50 dark:bg-purple-900/10",
      border: "border-purple-100 dark:border-purple-800",
      text: "text-purple-600 dark:text-purple-400",
      iconBg: "bg-purple-100 dark:bg-purple-900/30",
      iconText: "text-purple-700 dark:text-purple-300"
    },
    orange: {
      bg: "bg-orange-50 dark:bg-orange-900/10",
      border: "border-orange-100 dark:border-orange-800",
      text: "text-orange-600 dark:text-orange-400",
      iconBg: "bg-orange-100 dark:bg-orange-900/30",
      iconText: "text-orange-700 dark:text-orange-300"
    },
  };

  const styles = colorStyles[color];

  // Map icon string names to components if needed, though usually passing component directly is better
  const renderIcon = () => {
    if (typeof icon === 'string') {
      // Fallback for old usage or map strings
      if (icon === '📄') return <BookOpen size={24} />;
      if (icon === '👥') return <Users size={24} />;
      if (icon === '🤝') return <Share2 size={24} />;
      if (icon === '📊') return <Activity size={24} />;
      return icon;
    }
    return icon;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className={cn(
        "relative overflow-hidden rounded-xl border p-6 shadow-sm transition-all hover:shadow-md",
        styles.bg,
        styles.border
      )}
    >
      <div className="flex items-center justify-between space-y-0 pb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <div className={cn("p-2 rounded-lg", styles.iconBg, styles.iconText)}>
          {renderIcon()}
        </div>
      </div>
      <div className="flex items-baseline space-x-2">
        <div className={cn("text-3xl font-bold tracking-tight", styles.text)}>
          {value}
        </div>
      </div>
    </motion.div>
  );
}

export default StatsCard;
