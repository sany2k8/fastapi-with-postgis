export const CATEGORIES = [
  "cafe",
  "restaurant",
  "shop",
  "park",
  "bar",
  "hotel",
] as const;

export type Category = (typeof CATEGORIES)[number];

// Color per category, used for map markers and the legend.
export const CATEGORY_COLOR: Record<string, string> = {
  cafe: "#b45309", // amber-700
  restaurant: "#dc2626", // red-600
  shop: "#2563eb", // blue-600
  park: "#16a34a", // green-600
  bar: "#7c3aed", // violet-600
  hotel: "#db2777", // pink-600
};

// San Francisco.
export const SF_CENTER: [number, number] = [37.773, -122.41];
export const SF_ZOOM = 13;
