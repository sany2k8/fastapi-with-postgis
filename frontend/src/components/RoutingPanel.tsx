import type { CityInfo, RouteResponse } from "../api";

export interface RoutingState {
  city: string;
  cost: "time" | "distance";
  start: [number, number] | null; // [lat, lng]
  end: [number, number] | null;
  route: RouteResponse | null;
  status: string;
}

interface Props {
  cities: CityInfo[];
  state: RoutingState;
  onChange: (patch: Partial<RoutingState>) => void;
  onClear: () => void;
}

function fmtDuration(s: number): string {
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export default function RoutingPanel({ cities, state, onChange, onClear }: Props) {
  const selected = cities.find((c) => c.city === state.city);
  return (
    <div className="space-y-5">
      <div>
        <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
          City network
        </label>
        <select
          className="w-full bg-slate-800 rounded px-2 py-1.5 text-sm capitalize"
          value={state.city}
          onChange={(e) => onChange({ city: e.target.value })}
        >
          {cities.map((c) => (
            <option key={c.city} value={c.city} className="capitalize">
              {c.city}
            </option>
          ))}
        </select>
        {selected && (
          <p className="text-xs text-slate-500 mt-1">
            {selected.nodes.toLocaleString()} nodes ·{" "}
            {selected.edges.toLocaleString()} road segments (OpenStreetMap)
          </p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
          Optimize for
        </label>
        <div className="flex rounded overflow-hidden border border-slate-700 text-sm">
          {(["time", "distance"] as const).map((c) => (
            <button
              key={c}
              className={`flex-1 py-1.5 capitalize ${
                state.cost === c ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"
              }`}
              onClick={() => onChange({ cost: c })}
            >
              {c === "time" ? "Fastest" : "Shortest"}
            </button>
          ))}
        </div>
      </div>

      <div className="text-sm bg-slate-800 rounded p-3 space-y-1">
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full bg-green-500" />
          {state.start ? "Start set" : "Click the map to set start"}
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full bg-red-500" />
          {state.end ? "End set" : "Click again to set destination"}
        </div>
      </div>

      {state.route && (
        <div className="rounded bg-sky-950/60 border border-sky-800 p-3 text-sm space-y-1">
          <div className="text-2xl font-semibold">
            {fmtDuration(state.route.duration_s)}
          </div>
          <div className="text-slate-300">
            {(state.route.distance_m / 1000).toFixed(2)} km ·{" "}
            {state.route.node_count} points
          </div>
          <div className="text-xs text-slate-400 pt-1">
            A* over {selected?.city} · optimizing{" "}
            {state.route.cost === "time" ? "travel time" : "distance"}
          </div>
          <div className="text-xs text-slate-500">
            snapped to road: start {state.route.start.snap_distance_m} m, end{" "}
            {state.route.end.snap_distance_m} m
          </div>
        </div>
      )}

      <div className="text-xs text-slate-400">{state.status}</div>

      <button
        className="w-full bg-slate-800 hover:bg-slate-700 rounded py-1.5 text-sm"
        onClick={onClear}
      >
        Clear route
      </button>
    </div>
  );
}
