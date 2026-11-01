/** Ignore delayed polls, including responses from a replaced session. */
export function acceptSnapshot(current, incoming, activeId) {
  if (incoming.id !== activeId) return current;
  if (current?.id === incoming.id && current.revision > incoming.revision) return current;
  return incoming;
}
