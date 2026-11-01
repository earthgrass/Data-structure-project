export function acceptSnapshot<T extends {id: string; revision: number}>(current: T | null, incoming: T, activeId: string): T | null;
