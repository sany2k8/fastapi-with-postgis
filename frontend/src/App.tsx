import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { LatLngBounds } from "leaflet";

import {
  fetchNeighborhoodPlaces,
  fetchNeighborhoods,
  fetchPlaces,
  fetchRoute,
  fetchRouteCities,
  fetchStats,
  type CityInfo,
  type NeighborhoodFeature,
  type NeighborhoodStat,
  type PlaceFeature,
  type PlaceQuery,
} from "./api";
import FilterPanel from "./components/FilterPanel";
import MapView, { type Mode } from "./components/MapView";
import RoutingPanel, { type RoutingState } from "./components/RoutingPanel";
import { SF_CENTER, SF_ZOOM } from "./constants";

export interface Filters {
  category: string;
  minRating: number;
  open24h: boolean;
  radiusMode: boolean;
  center: [number, number] | null; // [lat, lng]
  radiusM: number;
  showNeighborhoods: boolean;
  selectedNeighborhood: number | null;
}

const INITIAL_FILTERS: Filters = {
  category: "",
  minRating: 0,
  open24h: false,
  radiusMode: false,
  center: null,
  radiusM: 800,
  showNeighborhoods: false,
  selectedNeighborhood: null,
};

const INITIAL_ROUTING: RoutingState = {
  city: "",
  cost: "time",
  start: null,
  end: null,
  route: null,
  status: "Pick a city, then click two points.",
};

export default function App() {
  const [mode, setMode] = useState<Mode>("places");

  // ----- places state -----
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [places, setPlaces] = useState<PlaceFeature[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<NeighborhoodFeature[]>([]);
  const [stats, setStats] = useState<NeighborhoodStat[]>([]);
  const [status, setStatus] = useState("Loading…");
  const boundsRef = useRef<LatLngBounds | null>(null);

  // ----- routing state -----
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [routing, setRouting] = useState<RoutingState>(INITIAL_ROUTING);

  const onChange = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
  }, []);
  const onRoutingChange = useCallback((patch: Partial<RoutingState>) => {
    setRouting((r) => {
      // Changing city invalidates the picked points (different network).
      if (patch.city && patch.city !== r.city) {
        return { ...r, ...patch, start: null, end: null, route: null };
      }
      return { ...r, ...patch };
    });
  }, []);

  // Static data, loaded once.
  useEffect(() => {
    fetchNeighborhoods().then((fc) => setNeighborhoods(fc.features)).catch(() => {});
    fetchStats().then(setStats).catch(() => {});
    fetchRouteCities()
      .then((cs) => {
        setCities(cs);
        if (cs.length) setRouting((r) => ({ ...r, city: r.city || cs[0].city }));
      })
      .catch(() => {});
  }, []);

  // ---------- places fetching ----------
  const loadPlaces = useCallback(async () => {
    try {
      if (filters.selectedNeighborhood != null) {
        const fc = await fetchNeighborhoodPlaces(filters.selectedNeighborhood, {
          category: filters.category || undefined,
          min_rating: filters.minRating || undefined,
        });
        setPlaces(fc.features);
        setStatus(`ST_Contains · neighborhood #${filters.selectedNeighborhood}`);
        return;
      }
      const q: PlaceQuery = {
        category: filters.category || undefined,
        min_rating: filters.minRating || undefined,
        open_24h: filters.open24h || undefined,
        limit: 2000,
      };
      if (filters.radiusMode && filters.center) {
        q.lat = filters.center[0];
        q.lng = filters.center[1];
        q.radius_m = filters.radiusM;
        q.sort = "nearest";
        const fc = await fetchPlaces(q);
        setPlaces(fc.features);
        setStatus(`ST_DWithin · ${filters.radiusM} m radius`);
        return;
      }
      const b = boundsRef.current;
      if (!b) return;
      q.bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
      const fc = await fetchPlaces(q);
      setPlaces(fc.features);
      setStatus("ST_MakeEnvelope · map viewport (GiST index)");
    } catch (e) {
      setStatus(String(e));
    }
  }, [filters]);

  // On any mode switch the map remounts at a new location; drop the old
  // viewport so a stale bbox from the other mode isn't queried. The freshly
  // mounted map reports its real bounds, which triggers the load.
  useEffect(() => {
    boundsRef.current = null;
  }, [mode]);

  useEffect(() => {
    if (mode === "places") void loadPlaces();
  }, [mode, loadPlaces]);

  // ---------- routing fetching ----------
  useEffect(() => {
    if (mode !== "routing" || !routing.city || !routing.start || !routing.end) return;
    let cancelled = false;
    setRouting((r) => ({ ...r, status: "Routing (A*)…" }));
    fetchRoute({
      city: routing.city,
      from_lat: routing.start[0],
      from_lng: routing.start[1],
      to_lat: routing.end[0],
      to_lng: routing.end[1],
      cost: routing.cost,
    })
      .then((route) => {
        if (!cancelled) setRouting((r) => ({ ...r, route, status: "Route found." }));
      })
      .catch((e) => {
        if (!cancelled) setRouting((r) => ({ ...r, route: null, status: String(e) }));
      });
    return () => {
      cancelled = true;
    };
  }, [mode, routing.city, routing.cost, routing.start, routing.end]);

  // ---------- map interaction ----------
  const onBoundsChange = useCallback(
    (b: LatLngBounds) => {
      if (b.getWest() >= b.getEast() || b.getSouth() >= b.getNorth()) return;
      boundsRef.current = b;
      if (
        mode === "places" &&
        filters.selectedNeighborhood == null &&
        !(filters.radiusMode && filters.center)
      ) {
        void loadPlaces();
      }
    },
    [mode, filters.selectedNeighborhood, filters.radiusMode, filters.center, loadPlaces],
  );

  const onMapClick = useCallback(
    (lat: number, lng: number) => {
      if (mode === "places") {
        if (filters.radiusMode) onChange({ center: [lat, lng], selectedNeighborhood: null });
        return;
      }
      // routing: 1st click = start, 2nd = end, 3rd = restart.
      setRouting((r) => {
        if (!r.start || (r.start && r.end)) {
          return { ...r, start: [lat, lng], end: null, route: null };
        }
        return { ...r, end: [lat, lng] };
      });
    },
    [mode, filters.radiusMode, onChange],
  );

  const onSelectNeighborhood = useCallback(
    (id: number) => onChange({ selectedNeighborhood: id, center: null }),
    [onChange],
  );

  const neighborhoodNames = useMemo(
    () => Object.fromEntries(neighborhoods.map((n) => [n.properties.id, n.properties.name])),
    [neighborhoods],
  );

  // Map view: SF for places, the selected city for routing. Changing this
  // remounts the map at the new location (see MapView's key).
  const selectedCity = cities.find((c) => c.city === routing.city);
  const view = useMemo(() => {
    if (mode === "routing" && selectedCity) {
      return {
        center: [selectedCity.center_lat, selectedCity.center_lng] as [number, number],
        zoom: 14,
      };
    }
    return { center: SF_CENTER, zoom: SF_ZOOM };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selectedCity?.center_lat, selectedCity?.center_lng]);

  const routeCoords = useMemo(
    () =>
      routing.route
        ? routing.route.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])
        : null,
    [routing.route],
  );

  return (
    <div className="flex h-full">
      <aside className="w-80 shrink-0 h-full overflow-y-auto bg-slate-900 text-slate-100 p-4 space-y-5">
        <div>
          <h1 className="text-lg font-semibold">Places Finder</h1>
          <p className="text-xs text-slate-400">PostGIS spatial demo</p>
        </div>
        {/* Mode switch */}
        <div className="flex rounded overflow-hidden border border-slate-700 text-sm">
          {(["places", "routing"] as const).map((m) => (
            <button
              key={m}
              className={`flex-1 py-1.5 capitalize ${
                mode === m ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"
              }`}
              onClick={() => setMode(m)}
            >
              {m === "places" ? "Places (SF)" : "Routing (BD)"}
            </button>
          ))}
        </div>

        {mode === "places" ? (
          <FilterPanel
            filters={filters}
            onChange={onChange}
            resultCount={places.length}
            status={status}
            stats={stats}
            neighborhoodNames={neighborhoodNames}
          />
        ) : (
          <RoutingPanel
            cities={cities}
            state={routing}
            onChange={onRoutingChange}
            onClear={() => setRouting((r) => ({ ...INITIAL_ROUTING, city: r.city, cost: r.cost }))}
          />
        )}
      </aside>

      <main className="flex-1 h-full">
        <MapView
          mode={mode}
          places={places}
          neighborhoods={neighborhoods}
          filters={filters}
          routeStart={routing.start}
          routeEnd={routing.end}
          routeCoords={routeCoords}
          view={view}
          onBoundsChange={onBoundsChange}
          onMapClick={onMapClick}
          onSelectNeighborhood={onSelectNeighborhood}
        />
      </main>
    </div>
  );
}
