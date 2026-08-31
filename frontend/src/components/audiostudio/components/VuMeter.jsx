import React, { useState, useEffect } from "react";

export function VuMeter({ levelsRef }) {
  const [left, setLeft] = useState(0);
  const [right, setRight] = useState(0);

  useEffect(() => {
    let raf;
    const tick = () => {
      if (levelsRef && levelsRef.current) {
        const lv = levelsRef.current;
        setLeft(lv.l);
        setRight(lv.r);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [levelsRef]);

  return (
    <div className="flex flex-col gap-0.5 w-14 bg-black/60 p-1 rounded border border-gray-700/60" title="Master Stereo Output Level">
      <div className="flex items-center gap-1">
        <span className="text-[7px] text-gray-400 font-mono w-2">L</span>
        <div className="flex-1 h-1.5 bg-gray-900 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-75 ${
              left > 85 ? "bg-rose-500" : left > 65 ? "bg-amber-400" : "bg-emerald-400"
            }`}
            style={{ width: `${left}%` }}
          />
        </div>
      </div>
      <div className="flex items-center gap-1">
        <span className="text-[7px] text-gray-400 font-mono w-2">R</span>
        <div className="flex-1 h-1.5 bg-gray-900 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-75 ${
              right > 85 ? "bg-rose-500" : right > 65 ? "bg-amber-400" : "bg-emerald-400"
            }`}
            style={{ width: `${right}%` }}
          />
        </div>
      </div>
    </div>
  );
}
