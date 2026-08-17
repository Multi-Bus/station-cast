import "./EstimateBadge.css";

/** README Interactions: every congestion number must carry this badge or a
 * confidence range nearby -- the value is always an estimate, never measured.
 *
 * `tone` picks the backdrop the badge sits on: "on-color" for the congestion
 * hero (translucent white over a saturated fill), "surface" for cards and list
 * rows, where that same translucent white would disappear. */
export function EstimateBadge({ tone = "on-color" }: { tone?: "on-color" | "surface" }) {
  return <span className={`estimate-badge estimate-badge-${tone}`}>추정</span>;
}
