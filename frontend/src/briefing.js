const BRIEFING_METRICS = [
  ["distance_km", "Whole trip", "km"],
  ["hours", "Travel time", "hours"],
  ["oxygen_remaining_hours", "Oxygen remaining", "hours"],
  ["battery_remaining_wh", "Battery remaining", "Wh"],
];

export function getBriefingMetrics(metrics) {
  if (!metrics || typeof metrics !== "object") return [];
  return BRIEFING_METRICS.filter(([key]) => Number.isFinite(metrics[key])).map(
    ([key, label, unit]) => ({ label, value: metrics[key].toFixed(2), unit }),
  );
}
