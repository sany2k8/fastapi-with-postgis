import { useEffect } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  useMapEvents,
} from "react-leaflet";
import type { LatLngBounds } from "leaflet";

import type { NeighborhoodFeature, PlaceFeature } from "../api";
import { CATEGORY_COLOR } from "../constants";
import type { Filters } from "../App";

export type Mode = "places" | "routing";

interface Props {
  mode: Mode;
  places: PlaceFeature[];
  neighborhoods: NeighborhoodFeature[];
  filters: Filters;
  // routing overlay
  routeStart: [number, number] | null;
  routeEnd: [number, number] | null;
  routeCoords: [number, number][] | null; // [lat, lng] pairs
  // Desired map view. Changing center/zoom remounts the map at that location.
  view: { center: [number, number]; zoom: number };
  onBoundsChange: (b: LatLngBounds) => void;
  onMapClick: (lat: number, lng: number) => void;
  onSelectNeighborhood: (id: number) => void;
}

// Bridges Leaflet map events up to React state.
function MapController({
  onBoundsChange,
  onMapClick,
}: {
  onBoundsChange: (b: LatLngBounds) => void;
  onMapClick: (lat: number, lng: number) => void;
}) {
  const map = useMapEvents({
    moveend: () => onBoundsChange(map.getBounds()),
    click: (e) => onMapClick(e.latlng.lat, e.latlng.lng),
  });
  // The map often mounts before its flex container has its final height, so
  // Leaflet computes a tiny viewport. Recompute the size on the next frame,
  // then emit the (now correct) initial viewport.
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      map.invalidateSize();
      onBoundsChange(map.getBounds());
    });
    return () => cancelAnimationFrame(id);
  }, [map, onBoundsChange]);
  return null;
}

export default function MapView({
  mode,
  places,
  neighborhoods,
  filters,
  routeStart,
  routeEnd,
  routeCoords,
  view,
  onBoundsChange,
  onMapClick,
  onSelectNeighborhood,
}: Props) {
  return (
    // key remounts the map when the target view changes (mode/city switch),
    // mounting it directly at the new center — robust across large jumps.
    <MapContainer
      key={`${view.center[0]},${view.center[1]},${view.zoom}`}
      center={view.center}
      zoom={view.zoom}
      className="h-full w-full"
      preferCanvas
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapController onBoundsChange={onBoundsChange} onMapClick={onMapClick} />

      {/* ---------- PLACES MODE ---------- */}
      {mode === "places" && (
        <>
          {filters.showNeighborhoods &&
            neighborhoods.map((n) => {
              const ring = n.geometry.coordinates[0].map(
                ([lon, lat]) => [lat, lon] as [number, number],
              );
              const selected = filters.selectedNeighborhood === n.properties.id;
              return (
                <Polygon
                  key={n.properties.id}
                  positions={ring}
                  pathOptions={{
                    color: selected ? "#f59e0b" : "#38bdf8",
                    weight: selected ? 3 : 1.5,
                    fillOpacity: selected ? 0.15 : 0.05,
                  }}
                  eventHandlers={{ click: () => onSelectNeighborhood(n.properties.id) }}
                >
                  <Popup>{n.properties.name}</Popup>
                </Polygon>
              );
            })}

          {filters.radiusMode && filters.center && (
            <Circle
              center={filters.center}
              radius={filters.radiusM}
              pathOptions={{ color: "#22d3ee", fillOpacity: 0.08 }}
            />
          )}

          {places.map((p) => {
            const [lon, lat] = p.geometry.coordinates;
            const props = p.properties;
            return (
              <CircleMarker
                key={props.id}
                center={[lat, lon]}
                radius={6}
                pathOptions={{
                  color: "#0f172a",
                  weight: 1,
                  fillColor: CATEGORY_COLOR[props.category] ?? "#64748b",
                  fillOpacity: 0.9,
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <div className="font-semibold">{props.name}</div>
                    <div className="capitalize text-slate-600">
                      {props.category} · ★ {props.rating} · {"$".repeat(props.price_level)}
                    </div>
                    {props.is_open_24h && (
                      <div className="text-green-700 text-xs">Open 24h</div>
                    )}
                    {props.distance_m != null && (
                      <div className="text-xs text-slate-500">
                        {props.distance_m < 1000
                          ? `${Math.round(props.distance_m)} m away`
                          : `${(props.distance_m / 1000).toFixed(2)} km away`}
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </>
      )}

      {/* ---------- ROUTING MODE ---------- */}
      {mode === "routing" && (
        <>
          {routeCoords && (
            <Polyline
              positions={routeCoords}
              pathOptions={{ color: "#0ea5e9", weight: 5, opacity: 0.85 }}
            />
          )}
          {routeStart && (
            <CircleMarker
              center={routeStart}
              radius={8}
              pathOptions={{ color: "#052e16", weight: 2, fillColor: "#22c55e", fillOpacity: 1 }}
            >
              <Popup>Start</Popup>
            </CircleMarker>
          )}
          {routeEnd && (
            <CircleMarker
              center={routeEnd}
              radius={8}
              pathOptions={{ color: "#450a0a", weight: 2, fillColor: "#ef4444", fillOpacity: 1 }}
            >
              <Popup>Destination</Popup>
            </CircleMarker>
          )}
        </>
      )}
    </MapContainer>
  );
}
