export const CATEGORY_NAMES = {
  sales: "Sales",
  loan: "Loan received",
  owner_deposit: "My own deposit",
  savings: "Savings (Ziidi, M-Shwari)",
  other_income: "Other money in",
  stock: "Stock",
  rent: "Rent",
  utilities: "Electricity and water",
  wages: "Wages",
  transport: "Transport",
  airtime: "Airtime and data",
  fees: "M-Pesa charges",
  loan_repayment: "Loan repayment",
  withdrawal: "Cash withdrawal",
  personal: "Personal",
  other_expense: "Other spending",
};

export const MONEY_IN = ["sales", "loan", "owner_deposit", "savings", "other_income"];
export const MONEY_OUT = [
  ...Object.keys(CATEGORY_NAMES).filter((key) => !MONEY_IN.includes(key)),
  "savings",
];
