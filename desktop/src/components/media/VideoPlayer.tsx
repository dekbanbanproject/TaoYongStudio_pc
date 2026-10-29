import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { assetUrl } from "../../services/api";
import { formatDuration } from "../common/ui";

/** Plays a real file from disk through the Tauri asset protocol. */
export function VideoPlayer({
  src,
  poster,
  aspect = "16:9",
  autoPlay = false,
  muted = false,
  controls = true,
  onError,
}: {
  src?: string;
  poster?: string;
  aspect?: "16:9" | "9:16" | "1:1";
  autoPlay?: boolean;
  muted?: boolean;
  controls?: boolean;
  onError?: (msg: string) => void;
}) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const [failed, setFailed] = useState(false);
  const url = assetUrl(src);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (!src) {
    return (
      <div className="video-frame" style={{ aspectRatio: aspect.replace(":", " / ") }}>
        <span className="small muted" style={{ color: "#c9c3ee" }}>
          ยังไม่มีไฟล์วิดีโอ
        </span>
      </div>
    );
  }

  if (failed) {
    return (
      <div className="video-frame" style={{ aspectRatio: aspect.replace(":", " / ") }}>
        <span className="small" style={{ color: "#ff9db0" }}>
          เปิดไฟล์วิดีโอไม่ได้
        </span>
      </div>
    );
  }

  return (
    <div className="video-frame" style={{ aspectRatio: aspect.replace(":", " / ") }}>
      <video
        ref={ref}
        src={url}
        poster={assetUrl(poster)}
        controls={controls}
        autoPlay={autoPlay}
        muted={muted}
        playsInline
        preload="metadata"
        onError={() => {
          setFailed(true);
          onError?.("เปิดไฟล์วิดีโอไม่ได้");
        }}
      />
    </div>
  );
}

export function VideoThumbnail({
  thumb,
  duration,
  size = 64,
  label,
  onClick,
}: {
  thumb?: string;
  duration?: number;
  size?: number;
  label?: string;
  onClick?: () => void;
}) {
  const url = assetUrl(thumb);
  return (
    <div
      className="thumb"
      style={{ width: size, height: Math.round((size * 9) / 16) }}
      onClick={onClick}
      title={label}
    >
      {url ? (
        <img src={url} alt={label || "ภาพปกคลิป"} />
      ) : (
        <Play size={18} color="#a48cf0" />
      )}
      {duration ? <span className="thumb__duration">{formatDuration(duration)}</span> : null}
    </div>
  );
}

/** Horizontal clip strip used on the Clips / Facebook Profile pages. */
export function ClipStrip({
  clips,
  onPick,
}: {
  clips: { thumb: string; durationSeconds: number; title: string }[];
  onPick: (i: number) => void;
}) {
  return (
    <div className="row" style={{ overflowX: "auto", paddingBottom: 6, gap: 8 }}>
      {clips.map((c, i) => (
        <button
          key={i}
          onClick={() => onPick(i)}
          title={c.title}
          style={{
            border: "1px solid var(--c-line)",
            borderRadius: 12,
            padding: 0,
            overflow: "hidden",
            background: "#fff",
            cursor: "pointer",
            flex: "none",
            width: 92,
          }}
        >
          <VideoThumbnail thumb={c.thumb} duration={c.durationSeconds} size={92} />
          <div className="xsmall muted truncate" style={{ padding: "4px 6px 6px" }}>
            {c.title || `คลิป ${i + 1}`}
          </div>
        </button>
      ))}
    </div>
  );
}
