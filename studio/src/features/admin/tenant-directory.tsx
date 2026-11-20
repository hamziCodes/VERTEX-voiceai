import Link from "next/link";

import { StatePanel } from "@/components/studio/state-panel";
import type { TenantDirectoryPageDto } from "@/data/schema";
import { formatDate, formatNumber } from "@/lib/format";

function directoryHref(query: string | undefined, page: number): string {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  params.set("page", String(page));
  return `/admin/tenants?${params.toString()}`;
}

export function TenantDirectory({ page, query, result }: { page: number; query?: string; result: TenantDirectoryPageDto }) {
  const { items, total, offset, limit } = result;
  const hasPrevious = page > 1;
  const hasNext = offset + items.length < total;

  return (
    <section aria-labelledby="tenant-directory-heading" className="form-panel operate-panel">
      <div className="operate-panel__heading">
        <h2 className="operate-panel__title" id="tenant-directory-heading">Directory</h2>
        {items.length > 0 ? (
          <p className="muted-copy admin-directory__count">
            Showing {formatNumber(offset + 1)}–{formatNumber(offset + items.length)} of {formatNumber(total)} tenants
          </p>
        ) : null}
      </div>
      <form action="/admin/tenants" className="form-field admin-search" method="get" role="search">
        <label htmlFor="tenant-search">Search tenants</label>
        <div className="admin-search__row">
          <input defaultValue={query ?? ""} id="tenant-search" maxLength={255} name="q" placeholder="Name or full tenant ID" type="search" />
          <button className="button button--secondary" type="submit">Search</button>
        </div>
      </form>
      {items.length === 0 ? (
        query ? (
          <StatePanel
            description={`No tenant name or ID matches “${query}”. Check the spelling or search by the full tenant ID.`}
            title="No matching tenants"
          />
        ) : total > 0 ? (
          <StatePanel
            actions={<Link className="button button--secondary" href="/admin/tenants">Back to the first page</Link>}
            description="This page is past the end of the directory."
            title="No tenants on this page"
          />
        ) : (
          <StatePanel description="Tenants appear here once customers create a workspace." title="No tenants yet" />
        )
      ) : (
        <table aria-label="Tenant directory" className="data-table">
          <thead>
            <tr>
              <th scope="col">Tenant</th>
              <th scope="col">Members</th>
              <th scope="col">Agents</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {items.map((tenant) => (
              <tr key={tenant.tenant_id}>
                <td data-label="Tenant">
                  <Link className="admin-tenant-link" href={`/admin/tenants/${tenant.tenant_id}`}>{tenant.name}</Link>
                </td>
                <td data-label="Members">{formatNumber(tenant.member_count)}</td>
                <td data-label="Agents">{tenant.agent_count === null ? <span className="muted-copy">Not available</span> : formatNumber(tenant.agent_count)}</td>
                <td data-label="Created"><span className="technical-value">{formatDate(tenant.created_at)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {hasPrevious || hasNext ? (
        <nav aria-label="Tenant directory pages" className="operate-pagination admin-pagination">
          {hasPrevious ? <Link className="button button--secondary" href={directoryHref(query, page - 1)}>Previous page</Link> : null}
          {hasNext ? <Link className="button button--secondary" href={directoryHref(query, page + 1)}>Next page</Link> : null}
        </nav>
      ) : null}
      <p className="muted-copy admin-directory__note">At most {limit} tenants are listed per page.</p>
    </section>
  );
}
