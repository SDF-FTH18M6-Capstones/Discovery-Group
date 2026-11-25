const cell = (value) => {
  let text = value == null ? "" : String(value);
  if (/^[=+\-@]/.test(text) && !/^-?\d+(\.\d+)?$/.test(text)) text = `'${text}`;
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};

export function toCsv(columns, rows) {
  const head = columns.map((column) => cell(column.label)).join(",");
  const body = rows.map((row) => columns.map((column) => cell(column.value(row))).join(","));
  return [head, ...body].join("\r\n");
}

export function saveCsv(filename, columns, rows) {
  const blob = new Blob([`﻿${toCsv(columns, rows)}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
