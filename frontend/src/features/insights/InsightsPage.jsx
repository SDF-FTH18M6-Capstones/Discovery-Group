import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import PageHeader from "../../components/PageHeader";
import { BarChart, EmptyState, Panel, StatStrip } from "../../components/ui";
import { money, shortDate } from "../../format";

const WEEKDAY = new Intl.DateTimeFormat("en-KE", { weekday: "short", day: "numeric" });
const dayLabel = (iso) => WEEKDAY.format(new Date(`${iso}T00:00:00`));

function trend(change, against) {
  if (change === 0) return `Level with ${against}`;
  return `${Math.abs(change)}% ${change > 0 ? "above" : "below"} ${against}`;
}

function comparisonItems(comparisons) {
  return comparisons.map((note) => {
    if (note.key === "yesterday") {
      return {
        label: "Yesterday",
        value: money(note.value),
        hint: `${trend(note.change, "a usual day like it")} (${money(note.usual)})`,
        icon: note.change >= 0 ? "up" : "down",
        tone: note.change >= 0 ? "brand" : "saffron",
      };
    }
    if (note.key === "week") {
      return {
        label: "This week so far",
        value: money(note.value),
        hint: trend(note.change, "the same days last week"),
        icon: note.change >= 0 ? "up" : "down",
        tone: note.change >= 0 ? "brand" : "saffron",
      };
    }
    return {
      label: "Best day this month",
      value: money(note.value),
      hint: shortDate(note.date),
      icon: "chart",
    };
  });
}

function SalesForecast({ sales }) {
  if (!sales.ready) {
    return (
      <Panel title="Sales forecast">
        <EmptyState
          icon="chart"
          title="Not enough history yet"
          action={
            <Link to="/money" className="btn-secondary">
              Import M-Pesa history
            </Link>
          }
        >
          Forecasts start once there are 14 days of takings. StockPilot has {sales.days_of_history}{" "}
          so far. Importing an M-Pesa statement fills the gap straight away.
        </EmptyState>
      </Panel>
    );
  }

  const bars = [
    ...sales.history.slice(-28).map((day) => ({
      label: dayLabel(day.date),
      value: day.takings,
      detail: money(day.takings),
    })),
    ...sales.forecast.map((day) => ({
      label: dayLabel(day.date),
      value: day.expected,
      forecast: true,
      detail: `Expected ${money(day.expected)} (likely ${money(day.low)} to ${money(day.high)})`,
    })),
  ];
  const nextWeek = sales.forecast.slice(0, 7).reduce((sum, day) => sum + day.expected, 0);

  return (
    <Panel
      title="Sales forecast"
      subtitle={`Last 4 weeks, then the next 2 weeks (lighter bars). Expect about ${money(nextWeek)} over the next 7 days.`}
    >
      <div className="p-4">
        <BarChart data={bars} height={240} label="Takings per day with forecast" format={money} />
        {sales.accuracy !== null && (
          <p className="mt-3 text-xs text-muted">
            Tested on the last two weeks, the forecast was {sales.accuracy}% accurate.
          </p>
        )}
      </div>
    </Panel>
  );
}

function Cashflow({ cash }) {
  if (!cash.ready) {
    return (
      <Panel title="Cash for the next 30 days">
        <EmptyState
          icon="cash"
          title="Import your M-Pesa history"
          action={
            <Link to="/money" className="btn-secondary">
              Go to M-Pesa money
            </Link>
          }
        >
          With your statement, StockPilot can see what usually goes out and warn you before cash
          runs short.
        </EmptyState>
      </Panel>
    );
  }

  const short = cash.expected_net < 0;
  const weeks = cash.weeks.flatMap((week) => [
    { label: `${shortDate(week.week)} in`, value: week.in, detail: `In ${money(week.in)}` },
    {
      label: `${shortDate(week.week)} out`,
      value: week.out,
      detail: `Out ${money(week.out)}`,
      forecast: true,
    },
  ]);

  return (
    <Panel title="Cash for the next 30 days">
      <div className="flex flex-col gap-4 p-4">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted">Expected in</dt>
            <dd className="figure text-lg">{money(cash.expected_in)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Expected out</dt>
            <dd className="figure text-lg">{money(cash.expected_out)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">M-Pesa balance</dt>
            <dd className="figure text-lg">{cash.balance === null ? "—" : money(cash.balance)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">In 30 days</dt>
            <dd className={`figure text-lg ${short ? "text-danger" : "text-brand-dark"}`}>
              {cash.projected_balance === null
                ? money(cash.expected_net)
                : money(cash.projected_balance)}
            </dd>
          </div>
        </dl>
        {short && (
          <p role="alert" className="rounded-xl border border-danger/30 p-3 text-sm text-danger">
            More is likely to go out than come in over the next month. Look at the biggest spending
            categories on the M-Pesa money page.
          </p>
        )}
        <BarChart
          data={weeks}
          height={160}
          label="Money in and out per week, last 8 weeks"
          format={money}
        />
        <p className="text-xs text-muted">
          Solid bars are money in, lighter bars money out. Your own deposits and withdrawals are
          left out.
        </p>
      </div>
    </Panel>
  );
}

function List({ title, empty, rows }) {
  return (
    <Panel title={title}>
      {rows.length ? (
        <ul className="divide-y divide-line text-sm">{rows}</ul>
      ) : (
        <p className="p-4 text-sm text-muted">{empty}</p>
      )}
    </Panel>
  );
}

function Row({ to, name, children, figure }) {
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        {to ? (
          <Link to={to} className="font-semibold hover:underline">
            {name}
          </Link>
        ) : (
          <span className="font-semibold">{name}</span>
        )}
        <p className="text-xs text-muted">{children}</p>
      </div>
      {figure && <span className="figure">{figure}</span>}
    </li>
  );
}

const customerName = (customer) => customer.name || customer.phone || "Unknown";

export default function InsightsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/insights")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <p role="alert" className="text-danger">
        {error}
      </p>
    );
  }
  if (!data) return <p className="text-muted">Working out your numbers…</p>;

  const { sales, stock, customers, cash } = data;

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Insights"
        subtitle="What your sales, stock and M-Pesa history say about the weeks ahead."
      />
      {sales.comparisons.length > 0 && <StatStrip items={comparisonItems(sales.comparisons)} />}
      <SalesForecast sales={sales} />
      <Cashflow cash={cash} />
      <div className="grid gap-6 lg:grid-cols-3">
        <List
          title="Running out soon"
          empty="Nothing is likely to run out this week."
          rows={stock.running_out.map((item) => (
            <Row
              key={item.id}
              to={`/products/${item.id}`}
              name={item.name}
              figure={`${item.days_left} day${item.days_left === 1 ? "" : "s"}`}
            >
              {item.quantity} left, selling about {item.per_day} a day. Order about{" "}
              {item.suggested_order} to cover two weeks.
            </Row>
          ))}
        />
        <List
          title="Not selling"
          empty="Everything in stock has sold in the last 30 days."
          rows={stock.slow_movers.map((item) => (
            <Row
              key={item.id}
              to={`/products/${item.id}`}
              name={item.name}
              figure={money(item.tied_up)}
            >
              {item.quantity} in stock, none sold in 30 days
            </Row>
          ))}
        />
        <List
          title="Most profitable"
          empty="No sales in the last 30 days."
          rows={stock.most_profitable.map((item) => (
            <Row
              key={item.id}
              to={`/products/${item.id}`}
              name={item.name}
              figure={money(item.profit)}
            >
              {item.sold} sold in 30 days
            </Row>
          ))}
        />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <List
          title="Best customers"
          empty="Customers appear once M-Pesa payments come in."
          rows={customers.top.map((customer) => (
            <Row
              key={customer.phone || customer.name}
              name={customerName(customer)}
              figure={money(customer.total)}
            >
              {customer.visits} payment{customer.visits === 1 ? "" : "s"} in 90 days
            </Row>
          ))}
        />
        <List
          title="Gone quiet"
          empty="None of your regulars have gone missing."
          rows={customers.gone_quiet.map((customer) => (
            <Row key={customer.phone || customer.name} name={customerName(customer)}>
              Paid {customer.visits} times, last on {shortDate(customer.last_at)}
              {customer.phone ? ` · ${customer.phone}` : ""}
            </Row>
          ))}
        />
      </div>
    </section>
  );
}
