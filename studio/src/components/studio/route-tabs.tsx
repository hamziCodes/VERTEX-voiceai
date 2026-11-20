"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface RouteTab {
  href: string;
  label: string;
  /** Also active on child routes, for example list → detail. */
  matchNested?: boolean;
}

export function RouteTabs({ items, label }: { items: ReadonlyArray<RouteTab>; label: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label={label} className="route-tabs">
      {items.map((item) => {
        const active = pathname === item.href || (item.matchNested === true && pathname.startsWith(`${item.href}/`));
        return (
          <Link aria-current={active ? "page" : undefined} className="route-tabs__link" href={item.href} key={item.href}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
