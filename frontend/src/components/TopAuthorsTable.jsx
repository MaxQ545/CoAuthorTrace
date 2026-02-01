import { Link } from 'react-router-dom';
import { Trophy, ArrowRight } from 'lucide-react';
import { cn } from '../lib/utils';

function TopAuthorsTable({ authors, title = '高产作者排行' }) {
  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <Trophy className="text-amber-500" size={18} />
          {title}
        </h3>
      </div>
      <div className="divide-y divide-border/50">
        {authors.map((author, index) => (
          <div
            key={author.id}
            className="px-6 py-3 flex items-center justify-between hover:bg-accent/50 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <span
                className={cn(
                  "flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold border",
                  index < 3
                    ? "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800"
                    : "bg-secondary text-muted-foreground border-transparent"
                )}
              >
                {index + 1}
              </span>
              <div className="flex flex-col">
                <Link
                  to={`/author/${author.id}`}
                  className="font-medium text-foreground hover:text-primary transition-colors flex items-center gap-1"
                >
                  {author.display_name}
                  <ArrowRight size={12} className="opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                </Link>
                <span className="text-xs text-muted-foreground truncate max-w-[150px]">
                  {author.primary_institution_name || '未知机构'}
                </span>
              </div>
            </div>
            <div className="text-sm font-medium tabular-nums bg-secondary/50 px-2 py-0.5 rounded text-foreground/80">
              {author.paper_count || author.collaboration_count} {author.paper_count ? '篇' : '次'}
            </div>
          </div>
        ))}
        {authors.length === 0 && (
          <div className="p-6 text-center text-muted-foreground text-sm">
            暂无数据
          </div>
        )}
      </div>
    </div>
  );
}

export default TopAuthorsTable;
