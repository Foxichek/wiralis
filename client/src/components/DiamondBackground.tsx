export default function DiamondBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <svg
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 md:w-80 md:h-80 lg:w-96 lg:h-96 opacity-10 animate-rotate-slow"
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="diamondGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0.3" />
            <stop offset="50%" stopColor="#8b5cf6" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0.3" />
          </linearGradient>
        </defs>
        <polygon
          points="100,10 180,60 180,140 100,190 20,140 20,60"
          fill="url(#diamondGradient)"
          stroke="url(#diamondGradient)"
          strokeWidth="2"
        />
        <polygon
          points="100,10 180,60 100,100"
          fill="rgba(168, 85, 247, 0.15)"
        />
        <polygon
          points="180,60 180,140 100,100"
          fill="rgba(139, 92, 246, 0.1)"
        />
        <polygon
          points="100,190 180,140 100,100"
          fill="rgba(99, 102, 241, 0.12)"
        />
        <polygon
          points="20,140 100,190 100,100"
          fill="rgba(168, 85, 247, 0.08)"
        />
        <polygon
          points="20,60 20,140 100,100"
          fill="rgba(139, 92, 246, 0.15)"
        />
        <polygon
          points="100,10 20,60 100,100"
          fill="rgba(168, 85, 247, 0.2)"
        />
      </svg>
    </div>
  );
}
