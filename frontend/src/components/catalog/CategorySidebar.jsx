/**
 * CategorySidebar
 * Desktop left-nav for the catalog page.
 * Data is entirely API-driven from GET /api/categories/:businessId.
 * Supports expandable sub-categories and scroll-spy highlighting.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

const CategoryItem = ({ category, isActive, onCategoryClick }) => {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = category.children && category.children.length > 0;

  const handleClick = () => {
    onCategoryClick(category.category_id);
    if (hasChildren) setExpanded(prev => !prev);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`w-full flex items-center justify-between px-4 py-2.5 text-left
          transition-colors duration-150 group
          ${isActive
            ? 'border-l-2 border-[#4A3B32] bg-[#FAF8F5] text-[#2C2420] font-semibold'
            : 'border-l-2 border-transparent text-[#786A60] hover:text-[#2C2420] hover:bg-[#FAF8F5]'
          }`}
        aria-current={isActive ? 'true' : undefined}
        data-testid={`sidebar-cat-${category.category_id}`}
      >
        <span className="flex items-center gap-2 text-sm leading-tight">
          {category.icon_emoji && (
            <span className="text-base" aria-hidden="true">{category.icon_emoji}</span>
          )}
          <span className="line-clamp-2">{category.display_name}</span>
        </span>
        <span className="flex items-center gap-1 flex-shrink-0 ml-2">
          {category.product_count > 0 && (
            <span className="text-[10px] text-[#786A60] tabular-nums">
              {category.product_count}
            </span>
          )}
          {hasChildren && (
            expanded
              ? <ChevronDown size={12} className="text-[#786A60]" />
              : <ChevronRight size={12} className="text-[#786A60]" />
          )}
        </span>
      </button>

      {/* Sub-categories */}
      {hasChildren && expanded && (
        <div className="pl-4">
          {category.children.map(child => (
            <button
              key={child.category_id}
              onClick={() => onCategoryClick(child.category_id)}
              className={`w-full flex items-center justify-between px-4 py-2 text-left text-xs
                transition-colors
                ${isActive
                  ? 'text-[#4A3B32] font-medium'
                  : 'text-[#786A60] hover:text-[#2C2420]'
                }`}
              data-testid={`sidebar-subcat-${child.category_id}`}
            >
              <span>{child.display_name}</span>
              {child.product_count > 0 && (
                <span className="text-[10px] text-[#786A60] tabular-nums">
                  {child.product_count}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const CategorySidebar = ({ categories, activeCategory, onCategoryClick }) => {
  if (!categories || categories.length === 0) return null;

  // Build tree: group children under parents
  const topLevel = categories.filter(c => !c.parent_category_id);
  const withChildren = topLevel.map(cat => ({
    ...cat,
    children: categories.filter(c => c.parent_category_id === cat.category_id),
  }));

  return (
    <aside
      className="w-64 flex-shrink-0 sticky top-[120px] h-[calc(100vh-120px)]
                 overflow-y-auto border-r border-[#E8E0D5] bg-white"
      aria-label="Menu categories"
      data-testid="category-sidebar"
    >
      <p className="text-xs uppercase tracking-[0.2em] text-[#786A60] px-4 py-3 font-semibold border-b border-[#E8E0D5]">
        Menu
      </p>
      <nav>
        {withChildren.map(cat => (
          <CategoryItem
            key={cat.category_id}
            category={cat}
            isActive={activeCategory === cat.category_id}
            onCategoryClick={onCategoryClick}
          />
        ))}
      </nav>
    </aside>
  );
};

export default CategorySidebar;
