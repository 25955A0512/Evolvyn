export function CommerceMetrics({ data }: { data: any }) {
  const sales = data.kind === "sales",
    currency = data.currency || "currency unspecified",
    netKnown = data.net_revenue !== null;
  return (
    <section
      className="commerce-metrics"
      aria-label="Calculated e-commerce metrics"
    >
      <h3>
        {sales ? "Sales performance" : "Product catalog"} · calculated from your
        upload
      </h3>
      <p>
        {data.source} · {data.citation}
      </p>
      <div className="commerce-metric-grid">
        {(sales
          ? [
              [
                netKnown ? "Net revenue" : "Gross sales",
                (netKnown ? data.net_revenue : data.gross_sales) +
                  " " +
                  currency,
              ],
              ["Distinct orders", data.orders],
              [
                netKnown ? "Average order value" : "Gross average order value",
                (netKnown
                  ? data.average_order_value
                  : data.gross_average_order_value) === null
                  ? "Not available"
                  : (netKnown
                      ? data.average_order_value
                      : data.gross_average_order_value) +
                    " " +
                    currency,
              ],
              ["Ordered units", data.units_sold],
            ]
          : [
              ["Products", data.products],
              ["Reported stockouts", data.out_of_stock],
              [
                "Inventory units",
                data.inventory_units ?? "Incomplete stock data",
              ],
              ["Revenue", "Needs sales data"],
            ]
        ).map(([label, value]) => (
          <div key={String(label)}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      {sales && (
        <p>
          Gross sales {data.gross_sales} − discounts{" "}
          {data.discounts ?? "unavailable"} − refunds{" "}
          {data.refunds ?? "unavailable"} = net revenue{" "}
          {data.net_revenue ?? "unavailable"} ({currency}). Tax/shipping
          excluded; {data.excluded_lines} pending/cancelled/failed lines
          excluded.
        </p>
      )}
      {data.warnings?.map((warning: string) => (
        <p className="fallback-note" key={warning}>
          {warning}
        </p>
      ))}
      {data.period && (
        <p>
          Observed order dates: {data.period.start || "not supplied"} to{" "}
          {data.period.end || "not supplied"}. These dates do not establish
          full-period coverage.
        </p>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              {sales ? (
                <>
                  <th>Units</th>
                  <th>{netKnown ? "Net revenue" : "Gross sales"}</th>
                  <th>Orders containing product</th>
                </>
              ) : (
                <>
                  <th>Catalog price ({currency})</th>
                  <th>Reported inventory</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {(sales ? data.products : data.items).map((p: any) => (
              <tr key={p.product_id}>
                <td>
                  {p.product_name || p.product_id}
                  <small>{p.product_id}</small>
                </td>
                {sales ? (
                  <>
                    <td>{p.units_sold}</td>
                    <td>{netKnown ? p.net_revenue : p.gross_sales}</td>
                    <td>{p.orders}</td>
                  </>
                ) : (
                  <>
                    <td>{p.unit_price}</td>
                    <td>{p.inventory ?? "Not supplied"}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small>
        Up to 50 products shown. Sales totals include every validated, included
        line. Product order counts overlap and must not be added to obtain store
        orders.
      </small>
      <details>
        <summary>Definitions, source and missing metrics</summary>
        <dl>
          {Object.entries(data.definitions).map(([k, v]) => (
            <div key={k}>
              <dt>{k.replaceAll("_", " ")}</dt>
              <dd>{String(v)}</dd>
            </div>
          ))}
        </dl>
        <p>
          {data.calculation_engine}. {data.classification}
        </p>
        {data.unavailable_metrics.map((v: string) => (
          <p key={v}>{v}</p>
        ))}
      </details>
    </section>
  );
}
