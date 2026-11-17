import { useTheme } from "../theme/ThemeContext";
import Icon from "./Icon";

export default function ThemeSwitch({ className = "" }) {
  const { dark, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className={`grid size-10 place-items-center rounded-xl border border-line bg-surface text-ink-2 transition-colors hover:border-brand hover:text-brand-dark ${className}`}
    >
      <Icon name={dark ? "sun" : "moon"} />
    </button>
  );
}
