// Typed client for the Places Finder API. All requests go through /api,
// which Vite proxies to the FastAPI backend.

export interface PlaceProperties {
  id: number;
  name: string;
  category: string;
  rating: number;
  price_level: number;
  is_open_24h: boolean;
  distance_m: number | null;
}

export interface PlaceFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] }; // [lon, lat]
  properties: PlaceProperties;
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: PlaceFeature[];
}

export interface NeighborhoodFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: { id: number; name: string };
}

export interface NeighborhoodCollection {
  type: "FeatureCollection";
  features: NeighborhoodFeature[];
}

export interface NeighborhoodStat {
  id: number;
  name: string;
  place_count: number;
  avg_rating: number;
  by_category: Record<string, number>;
}

export interface PlaceQuery {
  bbox?: [number, number, number, number];
  lat?: number;
  lng?: number;
  radius_m?: number;
  category?: string;
  min_rating?: number;
  max_price?: number;
  open_24h?: boolean;
  sort?: "id" | "nearest";
  limit?: number;
}

function toQueryString(q: PlaceQuery): string {
  const p = new URLSearchParams();
  if (q.bbox) p.set("bbox", q.bbox.join(","));
  if (q.lat !== undefined) p.set("lat", String(q.lat));
  if (q.lng !== undefined) p.set("lng", String(q.lng));
  if (q.radius_m !== undefined) p.set("radius_m", String(q.radius_m));
  if (q.category) p.set("category", q.category);
  if (q.min_rating !== undefined) p.set("min_rating", String(q.min_rating));
  if (q.max_price !== undefined) p.set("max_price", String(q.max_price));
  if (q.open_24h !== undefined) p.set("open_24h", String(q.open_24h));
  if (q.sort) p.set("sort", q.sort);
  if (q.limit !== undefined) p.set("limit", String(q.limit));
  return p.toString();
}

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export function fetchPlaces(q: PlaceQuery): Promise<FeatureCollection> {
  return getJSON<FeatureCollection>(`/api/places?${toQueryString(q)}`);
}

export function fetchNeighborhoods(): Promise<NeighborhoodCollection> {
  return getJSON<NeighborhoodCollection>("/api/neighborhoods");
}

export function fetchNeighborhoodPlaces(
  id: number,
  q: Pick<PlaceQuery, "category" | "min_rating"> = {},
): Promise<FeatureCollection> {
  const p = new URLSearchParams();
  if (q.category) p.set("category", q.category);
  if (q.min_rating !== undefined) p.set("min_rating", String(q.min_rating));
  return getJSON<FeatureCollection>(`/api/neighborhoods/${id}/places?${p.toString()}`);
}

export function fetchStats(): Promise<NeighborhoodStat[]> {
  return getJSON<NeighborhoodStat[]>("/api/neighborhoods/stats");
}

// ----- routing -----

export interface CityInfo {
  city: string;
  nodes: number;
  edges: number;
  center_lat: number;
  center_lng: number;
}

export interface SnappedPoint {
  lat: number;
  lng: number;
  snap_distance_m: number;
}

export interface RouteResponse {
  city: string;
  cost: "time" | "distance";
  distance_m: number;
  duration_s: number;
  geometry: { type: "LineString"; coordinates: [number, number][] }; // [lon, lat]
  node_count: number;
  start: SnappedPoint;
  end: SnappedPoint;
}

export function fetchRouteCities(): Promise<CityInfo[]> {
  return getJSON<CityInfo[]>("/api/route/cities");
}

export function fetchRoute(params: {
  city: string;
  from_lat: number;
  from_lng: number;
  to_lat: number;
  to_lng: number;
  cost: "time" | "distance";
}): Promise<RouteResponse> {
  const p = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  );
  return getJSON<RouteResponse>(`/api/route?${p.toString()}`);
}
