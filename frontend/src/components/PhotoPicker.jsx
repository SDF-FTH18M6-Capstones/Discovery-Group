import { useEffect, useRef, useState } from "react";

import { mediaUrl } from "../api/client";
import Icon from "./Icon";

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;

// US-10: refuse the wrong file before it is uploaded, and say why.
export function checkPhoto(file) {
  if (!file) return "";
  if (!PHOTO_TYPES.includes(file.type)) return "Choose a JPEG, PNG or WebP photo.";
  if (file.size > PHOTO_MAX_BYTES) return "The photo is larger than 5 MB. Choose a smaller one.";
  return "";
}

// Shows the current photo (or the one just picked) and lets the person pick another.
export default function PhotoPicker({
  currentUrl,
  file,
  onPick,
  onRemove,
  error,
  label = "Photo",
}) {
  const input = useRef(null);
  const [preview, setPreview] = useState("");

  useEffect(() => {
    if (!file || typeof URL.createObjectURL !== "function") {
      setPreview("");
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const shown = preview || mediaUrl(currentUrl);

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-ink-2">{label}</span>
      <div className="flex items-center gap-4">
        <span className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-xl border border-line bg-surface-2 text-muted">
          {shown ? (
            <img src={shown} alt="" className="size-full object-cover" />
          ) : (
            <Icon name="box" size={26} />
          )}
        </span>
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" onClick={() => input.current?.click()}>
              {shown ? "Replace photo" : "Choose photo"}
            </button>
            {shown && onRemove && (
              <button type="button" className="btn-ghost" onClick={onRemove}>
                Remove
              </button>
            )}
          </div>
          <span className="text-xs text-muted">JPEG, PNG or WebP, up to 5 MB.</span>
          <input
            ref={input}
            type="file"
            accept={PHOTO_TYPES.join(",")}
            aria-label={`${label} file`}
            className="sr-only"
            onChange={(event) => {
              onPick(event.target.files?.[0] || null);
              event.target.value = "";
            }}
          />
        </div>
      </div>
      {error && (
        <span role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
