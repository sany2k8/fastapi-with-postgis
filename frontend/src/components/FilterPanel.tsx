import type { NeighborhoodStat } from "../api";
import { CATEGORIES, CATEGORY_COLOR } from "../constants";
import type { Filters } from "../App";

interface Props {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  resultCount: number;
  status: string;
  stats: NeighborhoodStat[];
  neighborhoodNames: Record<number, string>;
}

export default function FilterPanel({
  filters,
  onChange,
  resultCount,
  status,
  stats,
  neighborhoodNames,
}: Props) {
  const selectedStat =
    filters.selectedNeighborhood != null
      ? stats.find((s) => s.id === filters.selectedNeighborhood)
      : undefined;

  return (
    <div className="space-y-5">
      {/* Category */}
      <div>
        <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
          Category
        </label>
        <select
          className="w-full bg-slate-800 rounded px-2 py-1.5 text-sm"
          value={filters.category}
          onChange={(e) => onChange({ category: e.target.value })}
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {/* Min rating */}
      <div>
        <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
          Min rating: {filters.minRating.toFixed(1)}
        </label>
        <input
          type="range"
          min={0}
          max={5}
          step={0.1}
          value={filters.minRating}
          onChange={(e) => onChange({ minRating: Number(e.target.value) })}
          className="w-full"
        />
      </div>

      {/* Open 24h */}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={filters.open24h}
          onChange={(e) => onChange({ open24h: e.target.checked })}
        />
        Open 24h only
      </label>

      <hr className="border-slate-700" />

      {/* Radius search */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={filters.radiusMode}
            onChange={(e) =>
              onChange({ radiusMode: e.target.checked, center: null })
            }
          />
          Radius search (ST_DWithin)
        </label>
        {filters.radiusMode && (
          <div className="text-xs text-slate-400 space-y-2">
            <p>
              {filters.center
                ? "Center set. Drag the slider to resize."
                : "Click the map to drop a search point."}
            </p>
            <label className="block">
              Radius: {filters.radiusM} m
              <input
                type="range"
                min={200}
                max={3000}
                step={100}
                value={filters.radiusM}
                onChange={(e) => onChange({ radiusM: Number(e.target.value) })}
                className="w-full"
              />
            </label>
          </div>
        )}
      </div>

      <hr className="border-slate-700" />

      {/* Neighborhoods */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={filters.showNeighborhoods}
            onChange={(e) =>
              onChange({
                showNeighborhoods: e.target.checked,
                selectedNeighborhood: e.target.checked
                  ? filters.selectedNeighborhood
                  : null,
              })
            }
          />
          Show neighborhoods
        </label>
        {filters.selectedNeighborhood != null && (
          <div className="text-xs bg-slate-800 rounded p-2 space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {neighborhoodNames[filters.selectedNeighborhood]}
              </span>
              <button
                className="text-slate-400 hover:text-white"
                onClick={() => onChange({ selectedNeighborhood: null })}
              >
                clear ✕
              </button>
            </div>
            {selectedStat && (
              <>
                <div>
                  {selectedStat.place_count} places · avg ★
                  {selectedStat.avg_rating.toFixed(2)}
                </div>
                <div className="flex flex-wrap gap-1 pt-1">
                  {Object.entries(selectedStat.by_category).map(([c, n]) => (
                    <span
                      key={c}
                      className="px-1.5 py-0.5 rounded text-[10px]"
                      style={{ backgroundColor: CATEGORY_COLOR[c] }}
                    >
                      {c} {n}
                    </span>
                  ))}
                </div>
              </>
            )}
            <p className="text-slate-400 pt-1">
              Point-in-polygon via ST_Contains
            </p>
          </div>
        )}
      </div>

      <hr className="border-slate-700" />

      {/* Legend + status */}
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">
          Legend
        </div>
        <div className="grid grid-cols-2 gap-1 text-xs">
          {CATEGORIES.map((c) => (
            <div key={c} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ backgroundColor: CATEGORY_COLOR[c] }}
              />
              {c}
            </div>
          ))}
        </div>
      </div>

      <div className="text-sm">
        <span className="font-semibold">{resultCount}</span> places shown
        <div className="text-xs text-slate-400">{status}</div>
      </div>
    </div>
  );
}
