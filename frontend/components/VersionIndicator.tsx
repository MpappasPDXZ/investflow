'use client';

import { useEffect, useState } from 'react';

export function VersionIndicator() {
  const [buildTime, setBuildTime] = useState<string>('');

  useEffect(() => {
    // Set build time when component mounts (indicates reload)
    setBuildTime(new Date().toLocaleTimeString());
  }, []);

  return (
    <div className="fixed bottom-2 right-2 bg-black text-white text-xs px-2 py-1 rounded shadow-lg z-50 font-mono">
      v1.1.2 - Built: {buildTime}
    </div>
  );
}

