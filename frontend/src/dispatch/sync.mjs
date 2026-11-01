/** Ignore delayed polls, including responses from a replaced session. */
export function acceptSnapshot(current, incoming, activeId) {
  if (incoming.id !== activeId) return current;
  if (current?.id === incoming.id && current.revision > incoming.revision) return current;
  return incoming;
}

/** A comparison belongs to the exact observed input, not just the selected tab. */
export function bindComparison(snapshot, plans) {
  if (plans.length !== 2 || plans.some(p => p.revision !== snapshot.revision ||
      p.traffic_version !== snapshot.traffic_version || p.fingerprint !== plans[0].fingerprint)) return null;
  return {sessionId:snapshot.id, revision:snapshot.revision, trafficVersion:snapshot.traffic_version,
    fingerprint:plans[0].fingerprint, plans};
}

export function reconcileSnapshot(current, comparison, incoming, activeId) {
  const snapshot = acceptSnapshot(current, incoming, activeId);
  if (snapshot !== incoming) return {snapshot, comparison};
  const keep = comparison?.sessionId === snapshot.id && comparison.revision === snapshot.revision &&
    comparison.trafficVersion === snapshot.traffic_version;
  return {snapshot, comparison:keep ? comparison : null};
}

function actionKey(a) {
  return JSON.stringify([a.vehicle,a.kind,a.source,a.target,a.start,a.end,a.ids,a.batch,a.traffic_version]);
}

/** Evidence from the current action and events AFTER the latest plan application.
 * Never infer completion from the simulation clock, or reuse an earlier plan's events.
 */
export function actionPhase(snapshot, action) {
  if (snapshot.vehicles.some(v => v.current && actionKey(v.current) === actionKey(action))) return 'current';
  let boundary = -1;
  for (let i=0;i<snapshot.events.length;i++) if(snapshot.events[i].kind === 'plan') boundary=i;
  if (snapshot.events.slice(boundary+1).some(e => e.action && actionKey(e.action) === actionKey(action))) return 'completed';
  if (snapshot.needs_replan) return 'paused';
  return snapshot.ready || snapshot.running ? 'pending' : 'unknown';
}
