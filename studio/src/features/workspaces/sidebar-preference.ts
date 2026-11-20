export const SIDEBAR_PREFERENCE_KEY = "wavia:studio:sidebar:v1";
const SIDEBAR_PREFERENCE_EVENT = "wavia:studio:sidebar-change";

type SidebarPreference = "collapsed" | "expanded";

export function readSidebarPreference(storage: Pick<Storage, "getItem">): boolean {
  try {
    return storage.getItem(SIDEBAR_PREFERENCE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function writeSidebarPreference(
  storage: Pick<Storage, "setItem">,
  collapsed: boolean,
): void {
  const preference: SidebarPreference = collapsed ? "collapsed" : "expanded";
  try {
    storage.setItem(SIDEBAR_PREFERENCE_KEY, preference);
  } catch {
    // Storage can be unavailable in hardened browsers; the control still works.
  }
}

export function getSidebarPreferenceSnapshot(): boolean {
  return typeof window === "undefined"
    ? false
    : readSidebarPreference(window.localStorage);
}

export function subscribeSidebarPreference(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const onStorage = (event: StorageEvent) => {
    if (event.key === SIDEBAR_PREFERENCE_KEY) onStoreChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(SIDEBAR_PREFERENCE_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(SIDEBAR_PREFERENCE_EVENT, onStoreChange);
  };
}

export function setSidebarPreference(collapsed: boolean): void {
  if (typeof window === "undefined") return;
  writeSidebarPreference(window.localStorage, collapsed);
  window.dispatchEvent(new Event(SIDEBAR_PREFERENCE_EVENT));
}
