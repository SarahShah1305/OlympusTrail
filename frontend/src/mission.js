export const presets = {
  short: { label: "Short outing", oxygen: 2, battery: 600 },
  standard: { label: "Standard", oxygen: 4, battery: 1000 },
  long: { label: "Long trek", oxygen: 8, battery: 2000 },
};
export function tripVerdict(status) {
  if (status === "ok")
    return {
      title: "Within the modeled limits",
      text: "The estimate fits the supplies and terrain rules you selected.",
      tone: "go",
      icon: "✓",
    };
  if (status === "search_limit")
    return {
      title: "Check incomplete",
      text: "The planner stopped before it could confirm a route. Try a closer destination.",
      tone: "caution",
      icon: "!",
    };
  if (status === "error")
    return {
      title: "Planner unavailable",
      text: "The route could not be checked. Try again or choose another destination.",
      tone: "caution",
      icon: "!",
    };
  return {
    title: "No route found",
    text: "The selected terrain rules and destination produced no feasible route. Try a closer site or review the exclusions.",
    tone: "no-go",
    icon: "×",
  };
}
