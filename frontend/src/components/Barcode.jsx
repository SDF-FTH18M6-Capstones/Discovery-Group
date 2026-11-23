// Code 128 (subset B) barcode as an SVG, drawn in the browser: no library, no image request.
// US-33: the asset page shows the barcode with the code in text beneath it.

// Bar and space widths for each Code 128 value (0–105), then the stop pattern.
const PATTERNS = (
  "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 " +
  "112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 " +
  "311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 " +
  "112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 " +
  "313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 " +
  "314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 " +
  "122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 " +
  "124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 " +
  "114311 411113 411311 113141 114131 311141 411131 211412 211214 211232"
).split(" ");
const STOP = "2331112";
const START_B = 104;

// The 0/1 modules for `text` (printable ASCII only), quiet zones not included.
export function code128Modules(text) {
  const values = [...text].map((char) => {
    const code = char.charCodeAt(0);
    if (code < 32 || code > 126) throw new Error(`Cannot encode “${char}” in a barcode`);
    return code - 32;
  });
  const checksum = values.reduce((sum, value, i) => sum + value * (i + 1), START_B) % 103;
  const widths = [START_B, ...values, checksum].map((v) => PATTERNS[v]).join("") + STOP;
  let bits = "";
  [...widths].forEach((width, i) => {
    bits += (i % 2 === 0 ? "1" : "0").repeat(Number(width));
  });
  return bits;
}

export default function Barcode({ value, height = 64, module = 2, showText = true }) {
  let bits;
  try {
    bits = code128Modules(value);
  } catch {
    return <span className="code text-danger">Cannot draw a barcode for {value}</span>;
  }
  const quiet = 10;
  const width = (bits.length + quiet * 2) * module;
  const bars = [];
  let start = -1;
  for (let i = 0; i <= bits.length; i += 1) {
    if (bits[i] === "1" && start < 0) start = i;
    if (bits[i] !== "1" && start >= 0) {
      bars.push([start, i - start]);
      start = -1;
    }
  }
  return (
    <figure className="inline-flex flex-col items-center gap-1 rounded-lg bg-white p-2 text-black">
      <svg
        role="img"
        aria-label={`Barcode ${value}`}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        shapeRendering="crispEdges"
      >
        <rect width={width} height={height} fill="#fff" />
        {bars.map(([x, w]) => (
          <rect key={x} x={(x + quiet) * module} width={w * module} height={height} fill="#000" />
        ))}
      </svg>
      {showText && <figcaption className="font-mono text-sm tracking-[0.15em]">{value}</figcaption>}
    </figure>
  );
}
