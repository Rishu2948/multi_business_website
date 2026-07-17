/**
 * VegNonVegBadge
 * Small colored square indicator matching Indian food labeling standards.
 * Green = veg, Red = non-veg, null = renders nothing.
 */
const VegNonVegBadge = ({ isVeg, size = 'sm' }) => {
  if (isVeg === null || isVeg === undefined) return null;

  const dim = size === 'lg' ? 'w-5 h-5' : 'w-4 h-4';
  const dot = size === 'lg' ? 'w-2.5 h-2.5' : 'w-2 h-2';
  const color = isVeg ? 'border-green-600' : 'border-red-600';
  const dotColor = isVeg ? 'bg-green-600' : 'bg-red-600';
  const label = isVeg ? 'Vegetarian' : 'Non-vegetarian';

  return (
    <div
      className={`${dim} ${color} border-2 flex items-center justify-center flex-shrink-0`}
      aria-label={label}
      title={label}
      data-testid={`veg-badge-${isVeg ? 'veg' : 'nonveg'}`}
    >
      <div className={`${dot} ${dotColor} rounded-full`} />
    </div>
  );
};

export default VegNonVegBadge;
