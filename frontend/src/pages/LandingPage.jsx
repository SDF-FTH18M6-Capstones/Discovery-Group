import { useState } from "react";
import { Link } from "react-router-dom";

import Icon from "../components/Icon";
import Logo from "../components/Logo";
import ThemeSwitch from "../components/ThemeSwitch";

function TillScene() {
  return (
    <div
      className="relative mx-auto flex w-full max-w-[34rem] flex-col gap-4 pb-12 sm:block sm:h-[35rem] sm:pb-0"
      aria-hidden="true"
    >
      {/* the till */}
      <div className="relative z-10 rounded-[22px] border border-white/10 bg-[#f8faf7] p-5 text-[#12201c] shadow-[0_40px_80px_-30px_rgb(0_0_0/0.6)] sm:absolute sm:top-0 sm:left-0 sm:w-[21rem]">
        <div className="flex items-center justify-between text-xs text-[#5f6f69]">
          <span className="font-semibold text-[#12201c]">New sale</span>
          <span>Till 1</span>
        </div>
        <ul className="mt-4 flex flex-col gap-2.5 text-sm">
          {[
            ["Water Bottle 1L", "2", "500.00"],
            ["Coffee Beans 250g", "1", "650.00"],
            ["Kraft Bag Medium", "1", "35.00"],
          ].map(([name, qty, total]) => (
            <li key={name} className="flex items-center gap-3">
              <span className="grid size-7 place-items-center rounded-lg bg-[#e3f3ec] font-mono text-xs text-[#0a6a4c]">
                {qty}
              </span>
              <span className="flex-1">{name}</span>
              <span className="tabular-nums">{total}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 grid grid-cols-3 gap-1.5 text-center text-xs">
          <span className="rounded-lg border border-[#dfe6e1] py-1.5">Cash</span>
          <span className="rounded-lg border border-[#0e8a63] bg-[#e3f3ec] py-1.5 font-semibold text-[#0a6a4c]">
            M-Pesa
          </span>
          <span className="rounded-lg border border-[#dfe6e1] py-1.5">Card</span>
        </div>
        <div className="mt-4 flex items-end justify-between border-t border-[#dfe6e1] pt-3">
          <span className="text-sm text-[#5f6f69]">Total</span>
          <span className="font-display text-2xl font-bold tabular-nums">KES 1,185.00</span>
        </div>
      </div>

      {/* the receipt that prints out of it */}
      <div className="hidden sm:absolute sm:top-68 sm:left-6 sm:z-0 sm:block sm:w-48">
        <div className="animate-print perforated rounded-t-sm bg-white px-4 pt-8 pb-4 font-mono text-[11px] leading-5 text-[#2c3b36] shadow-xl">
          <p className="text-center font-semibold">StockPilot Shop</p>
          <p className="text-center text-[#5f6f69]">Receipt S-0042</p>
          <p className="mt-2 flex justify-between border-t border-dashed border-[#c9d3cd] pt-2">
            <span>Total</span>
            <span>1,185.00</span>
          </p>
          <p className="flex justify-between text-[#5f6f69]">
            <span>M-Pesa</span>
            <span>Vincent</span>
          </p>
        </div>
      </div>

      {/* the stock card it updates */}
      <div className="relative z-20 ml-auto w-[92%] rounded-[22px] border border-white/10 bg-[#10231f] p-5 text-white shadow-[0_40px_80px_-30px_rgb(0_0_0/0.7)] sm:absolute sm:top-[19.5rem] sm:right-0 sm:w-[19.5rem]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-display text-lg font-semibold">Water Bottle 1L</p>
            <p className="font-mono text-xs text-[#8fa59e]">SP-001</p>
          </div>
          <div className="text-right">
            <p className="font-display text-3xl font-bold tabular-nums">118</p>
            <p className="text-xs text-[#8fa59e]">in stock</p>
          </div>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
          <span className="block h-full w-[70%] rounded-full bg-[#3ccb95]" />
        </div>
        <ul className="mt-4 flex flex-col text-sm">
          <li className="animate-row -mx-2 flex items-center justify-between rounded-lg px-2 py-2">
            <span>Sale S-0042</span>
            <span className="font-display font-semibold text-[#f2b655]">−2</span>
          </li>
          <li className="flex items-center justify-between border-t border-white/10 py-2 text-[#c8d6d1]">
            <span>PO-0007 received</span>
            <span className="font-display font-semibold text-[#3ccb95]">+40</span>
          </li>
          <li className="flex items-center justify-between border-t border-white/10 py-2 text-[#c8d6d1]">
            <span>Damaged in store</span>
            <span className="font-display font-semibold text-[#f2b655]">−1</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

const FLOW = [
  {
    step: "Order",
    what: "Procurement places PO-0007 for 40 bags of coffee.",
    change: null,
    balance: 14,
  },
  {
    step: "Receive",
    what: "Inventory receives the delivery. Stock goes up.",
    change: "+40",
    balance: 54,
  },
  { step: "Sell", what: "Two bags go through the till on M-Pesa.", change: "−2", balance: 52 },
  {
    step: "Adjust",
    what: "One bag is torn. The reason is written down.",
    change: "−1",
    balance: 51,
  },
];

function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="flex flex-col gap-4">
          <h2 className="font-display text-[2.2rem] leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
            The count is never a guess.
          </h2>
          <p className="max-w-md text-lg text-muted">
            Stock only changes through a sale, a delivery or an adjustment, and each one writes a
            line to the stock ledger with who did it, when and why. Open any product and read how it
            got to today’s number.
          </p>
        </div>
        <ol className="relative grid gap-4 sm:grid-cols-2">
          {FLOW.map((item, index) => (
            <li
              key={item.step}
              className={`flex flex-col gap-3 rounded-2xl border p-5 ${
                index === 3 ? "border-brand bg-mint" : "border-line bg-surface"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-semibold">
                  <span className="grid size-7 place-items-center rounded-full bg-evergreen font-display text-sm text-white">
                    {index + 1}
                  </span>
                  {item.step}
                </span>
                {item.change && (
                  <span
                    className={`figure text-lg ${item.change.startsWith("+") ? "text-brand-dark" : "text-saffron-ink"}`}
                  >
                    {item.change}
                  </span>
                )}
              </div>
              <p className="text-sm text-muted">{item.what}</p>
              <p className="mt-auto flex items-baseline gap-2 border-t border-line pt-3">
                <span className="figure text-3xl">{item.balance}</span>
                <span className="text-sm text-muted">Coffee Beans 250g on the shelf</span>
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

const ROLES = [
  {
    key: "admin",
    name: "Administrator",
    who: "The owner or manager.",
    does: "Sees everything: sales, profit estimates, stock value, users and their roles.",
    pages: ["Dashboard", "Reports", "Users", "Sales", "Stock ledger", "Purchases"],
  },
  {
    key: "procurement",
    name: "Procurement",
    who: "Whoever buys from suppliers.",
    does: "Approves staff requests, keeps the supplier list and places purchase orders.",
    pages: ["Approvals", "Suppliers", "Purchases", "Products"],
  },
  {
    key: "inventory",
    name: "Inventory",
    who: "The stockroom.",
    does: "Receives deliveries, adjusts counts, manages products, assets and the repair board.",
    pages: ["Stock ledger", "Purchases", "Products", "Assets", "Repairs"],
  },
  {
    key: "sales",
    name: "Sales attendant",
    who: "Behind the counter.",
    does: "Rings up sales on the till with cash, M-Pesa or card and prints the receipt.",
    pages: ["New sale", "Sales", "Products", "My requests"],
  },
  {
    key: "employee",
    name: "Employee",
    who: "Everyone else on the team.",
    does: "Asks for what they need, sees the assets signed out to them, reports faults.",
    pages: ["My requests", "My assets", "Repairs", "Notifications"],
  },
];

function Roles() {
  const [current, setCurrent] = useState(ROLES[0]);
  return (
    <section id="roles" className="border-y border-line bg-surface-2">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 sm:py-28 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="flex flex-col gap-6">
          <h2 className="font-display text-[2.2rem] leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
            One app, five jobs.
          </h2>
          <p className="max-w-md text-lg text-muted">
            Each person signs in and sees only the work that is theirs. The server checks the role
            on every request, not just the menu.
          </p>
          <div role="group" aria-label="Choose a role" className="flex flex-wrap gap-2">
            {ROLES.map((role) => (
              <button
                key={role.key}
                type="button"
                aria-pressed={current.key === role.key}
                onClick={() => setCurrent(role)}
                className="chip"
              >
                {role.name}
              </button>
            ))}
          </div>
        </div>
        <div className="grid overflow-hidden rounded-[22px] border border-line bg-surface shadow-[var(--sp-shadow-lg)] sm:grid-cols-[13rem_minmax(0,1fr)]">
          <div
            className="flex flex-col gap-1 bg-evergreen p-4 text-sm text-sidebar-ink"
            aria-hidden="true"
          >
            <span className="mb-3 flex items-center gap-2 text-white">
              <Logo size={24} />
            </span>
            {current.pages.map((page, index) => (
              <span
                key={page}
                className={`rounded-lg px-3 py-1.5 ${index === 0 ? "bg-evergreen-2 font-semibold text-white" : ""}`}
              >
                {page}
              </span>
            ))}
          </div>
          <div className="flex flex-col gap-4 p-6 sm:p-8" aria-live="polite">
            <p className="font-display text-2xl font-bold tracking-[-0.02em]">{current.name}</p>
            <p className="text-muted">{current.who}</p>
            <p className="text-lg">{current.does}</p>
            <p className="mt-auto text-sm text-muted">
              Opens {current.pages.length} pages, including{" "}
              {current.pages.slice(0, 2).join(" and ")}.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <h2 className="max-w-2xl font-display text-[2.2rem] leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
        From the counter to the stockroom to the owner’s report.
      </h2>
      <div className="mt-12 grid gap-4 md:grid-cols-6 md:grid-rows-[auto_auto]">
        <article className="flex flex-col gap-5 rounded-[22px] bg-evergreen p-6 text-white md:col-span-4 md:row-span-2 sm:p-8">
          <div className="flex flex-col gap-2">
            <h3 className="font-display text-2xl font-bold">A till that keeps up</h3>
            <p className="max-w-md text-sidebar-ink">
              Tap products, set quantities, take cash, M-Pesa or card. The price comes from the
              product, the shelf count drops, and the receipt prints at 80 mm.
            </p>
          </div>
          <div className="mt-auto grid grid-cols-2 gap-2 sm:grid-cols-3" aria-hidden="true">
            {[
              ["Water Bottle 1L", "250.00", "118 left"],
              ["Coffee Beans 250g", "650.00", "13 left"],
              ["Mineral Water", "60.00", "240 left"],
              ["Sugar 1kg", "190.00", "Out of stock"],
              ["A4 Paper (ream)", "550.00", "42 left"],
              ["Ziplock Bag", "18.00", "65 left"],
            ].map(([name, price, left]) => (
              <span
                key={name}
                className={`flex flex-col gap-1 rounded-xl bg-white/[0.06] p-3 ring-1 ring-white/10 ${left === "Out of stock" ? "opacity-50" : ""}`}
              >
                <span className="text-sm text-white">{name}</span>
                <span className="font-display font-semibold">KES {price}</span>
                <span
                  className={`text-xs ${left === "13 left" ? "text-[#f2b655]" : "text-sidebar-ink"}`}
                >
                  {left}
                </span>
              </span>
            ))}
          </div>
        </article>

        <article className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-6 md:col-span-2">
          <Icon name="truck" size={22} className="text-brand-dark" />
          <h3 className="font-display text-xl font-bold">Purchase orders</h3>
          <p className="text-sm text-muted">
            Order from a supplier, receive the goods, and the stock goes up with the order number
            beside it.
          </p>
          <div
            className="mt-auto flex items-center justify-between rounded-xl bg-surface-2 p-3 text-sm"
            aria-hidden="true"
          >
            <span className="code">PO-0007</span>
            <span className="rounded-full bg-mint px-2 py-0.5 text-xs font-semibold text-brand-dark">
              Received
            </span>
          </div>
        </article>

        <article className="flex flex-col gap-4 rounded-[22px] bg-saffron-soft p-6 md:col-span-2">
          <Icon name="inbox" size={22} className="text-saffron-ink" />
          <h3 className="font-display text-xl font-bold">Requests and approvals</h3>
          <p className="text-sm text-ink-2">
            Staff ask for a laptop or a ream of paper; procurement approves or says why not, and the
            person is told.
          </p>
        </article>

        <article className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-6 md:col-span-3">
          <Icon name="wrench" size={22} className="text-brand-dark" />
          <h3 className="font-display text-xl font-bold">Assets and repairs</h3>
          <p className="text-sm text-muted">
            Every laptop and scanner has a code and a holder. A fault goes on the repair board and
            moves from submitted to in progress to done.
          </p>
          <div className="grid grid-cols-3 gap-2 text-xs" aria-hidden="true">
            {[
              ["Submitted", 2],
              ["In progress", 1],
              ["Done", 5],
            ].map(([column, count]) => (
              <span key={column} className="flex flex-col gap-1 rounded-xl bg-surface-2 p-3">
                <span className="text-muted">{column}</span>
                <span className="figure text-xl">{count}</span>
              </span>
            ))}
          </div>
        </article>

        <article className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-6 md:col-span-3">
          <Icon name="chart" size={22} className="text-brand-dark" />
          <h3 className="font-display text-xl font-bold">Reports for the owner</h3>
          <p className="text-sm text-muted">
            Sales per day, the average receipt, an estimate of profit, stock value and what needs
            reordering, for the last week, month or quarter.
          </p>
          <div className="flex h-16 items-end gap-1.5" aria-hidden="true">
            {[38, 52, 31, 64, 58, 80, 72, 46, 69, 90, 77, 84].map((h, i) => (
              <span key={i} className="flex-1 rounded-t bg-brand" style={{ height: `${h}%` }} />
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

const SAFEGUARDS = [
  [
    "shield",
    "Checked on every request",
    "Each of the 56 endpoints is tested against all five roles.",
  ],
  [
    "lock",
    "Passwords never stored",
    "Only a bcrypt hash is kept. Sessions renew quietly every 15 minutes.",
  ],
  ["alert", "Sign-in limits", "Ten tries a minute, then the door closes for a while."],
  ["layers", "Clean input", "Text is trimmed and checked before it reaches the database."],
];

function Safeguards() {
  return (
    <section id="security" className="bg-evergreen text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 sm:py-24 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] lg:gap-16">
        <h2 className="font-display text-[2.2rem] leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
          Locked down from the start.
        </h2>
        <ul className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
          {SAFEGUARDS.map(([icon, title, body]) => (
            <li key={title} className="flex gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 text-saffron">
                <Icon name={icon} />
              </span>
              <span className="flex flex-col gap-1">
                <span className="font-semibold">{title}</span>
                <span className="text-sm text-sidebar-ink">{body}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="relative bg-evergreen text-white">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.06] [background-image:linear-gradient(rgb(255_255_255)_1px,transparent_1px),linear-gradient(90deg,rgb(255_255_255)_1px,transparent_1px)] [background-size:48px_48px] [mask-image:linear-gradient(to_bottom,black,transparent)]"
        />
        <nav
          aria-label="StockPilot"
          className="relative mx-auto flex max-w-6xl items-center gap-6 px-4 py-5 sm:px-6"
        >
          <Link to="/" aria-label="StockPilot home">
            <Logo size={56} />
          </Link>
          <div className="hidden items-center gap-6 text-sm text-sidebar-ink md:flex">
            <a href="#how" className="hover:text-white">
              How it works
            </a>
            <a href="#roles" className="hover:text-white">
              Roles
            </a>
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#security" className="hover:text-white">
              Security
            </a>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <ThemeSwitch className="border-white/15 bg-white/5 text-white hover:border-white/40 hover:text-white" />
            <Link
              to="/login"
              className="btn-secondary border-white/20 bg-transparent text-white hover:border-white/50 hover:text-white"
            >
              Sign in
            </Link>
          </div>
        </nav>

        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pt-10 pb-6 sm:px-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,6fr)] lg:pt-16 lg:pb-20">
          <div className="flex flex-col gap-7">
            <h1 className="font-display text-[2.9rem] leading-[0.98] font-bold tracking-[-0.035em] text-balance sm:text-[4.2rem]">
              Know what is on every shelf, to the last unit.
            </h1>
            <p className="max-w-xl text-lg text-sidebar-ink">
              StockPilot is the till, the stock ledger, purchase orders and the asset register for a
              small business. Every sale and delivery updates the count the moment it happens.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/register" className="btn-accent px-5 py-3 text-base">
                Create an account
              </Link>
              <Link
                to="/login"
                className="btn-secondary border-white/20 bg-transparent px-5 py-3 text-base text-white hover:border-white/50 hover:text-white"
              >
                Sign in
              </Link>
            </div>
            <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-sidebar-ink">
              <li className="flex items-center gap-2">
                <Icon name="cash" size={16} className="text-saffron" /> Cash, M-Pesa and card
              </li>
            </ul>
          </div>
          <TillScene />
        </div>
      </header>

      <main>
        <HowItWorks />
        <Roles />
        <Features />
        <Safeguards />
        <section className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 py-20 sm:px-6 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-3">
            <h2 className="font-display text-[2.2rem] leading-[1.05] font-bold tracking-[-0.03em] sm:text-5xl">
              Open the shop.
            </h2>
            <p className="max-w-lg text-lg text-muted">
              New accounts start as Employee. An administrator gives each person the role for their
              job.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/register" className="btn-primary px-5 py-3 text-base">
              Create an account
            </Link>
            <Link to="/login" className="btn-secondary px-5 py-3 text-base">
              Sign in
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-4 px-4 py-8 text-sm text-muted sm:px-6">
          <span className="rounded-xl bg-evergreen px-3 py-2">
            <Logo size={24} />
          </span>
          <span>StockPilot, 2026</span>
          <span className="flex gap-5 sm:ml-auto">
            <Link to="/login" className="hover:text-ink">
              Sign in
            </Link>
            <Link to="/register" className="hover:text-ink">
              Create an account
            </Link>
            <Link to="/status" className="hover:text-ink">
              System status
            </Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
