interface FloatingEmoji {
  emoji: string;
  x: number;
  y: number;
  duration: number;
  delay: number;
  size: number;
  opacity: number;
}

export default function FloatingEmojis() {
  const currencyEmojis: FloatingEmoji[] = [
    { emoji: '🌙', x: 10, y: 15, duration: 20, delay: 0, size: 2.5, opacity: 0.15 },
    { emoji: '🌐', x: 85, y: 25, duration: 25, delay: 2, size: 2, opacity: 0.12 },
    { emoji: '🪙', x: 20, y: 70, duration: 22, delay: 4, size: 2.2, opacity: 0.18 },
    { emoji: '💎', x: 75, y: 60, duration: 24, delay: 1, size: 2.3, opacity: 0.16 },
    { emoji: '🌙', x: 50, y: 40, duration: 26, delay: 3, size: 1.8, opacity: 0.1 },
    { emoji: '🌐', x: 30, y: 85, duration: 23, delay: 5, size: 2.4, opacity: 0.14 },
    { emoji: '🪙', x: 90, y: 50, duration: 21, delay: 2.5, size: 2, opacity: 0.13 },
    { emoji: '💎', x: 15, y: 45, duration: 27, delay: 4.5, size: 2.1, opacity: 0.15 },
  ];

  const toolEmojis: FloatingEmoji[] = [
    { emoji: '🛠️', x: 25, y: 20, duration: 18, delay: 1, size: 2, opacity: 1 },
    { emoji: '🛠️', x: 70, y: 75, duration: 19, delay: 3, size: 2.2, opacity: 1 },
    { emoji: '🛠️', x: 60, y: 30, duration: 20, delay: 5, size: 1.8, opacity: 1 },
  ];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {currencyEmojis.map((item, index) => (
        <div
          key={`currency-${index}`}
          className="absolute"
          style={{
            left: `${item.x}%`,
            top: `${item.y}%`,
            fontSize: `${item.size}rem`,
            opacity: item.opacity,
            animation: `float ${item.duration}s ease-in-out infinite`,
            animationDelay: `${item.delay}s`,
          }}
        >
          {item.emoji}
        </div>
      ))}
      
      {toolEmojis.map((item, index) => (
        <div
          key={`tool-${index}`}
          className="absolute"
          style={{
            left: `${item.x}%`,
            top: `${item.y}%`,
            fontSize: `${item.size}rem`,
            opacity: item.opacity,
            animation: `float ${item.duration}s ease-in-out infinite`,
            animationDelay: `${item.delay}s`,
          }}
        >
          {item.emoji}
        </div>
      ))}

      <style>{`
        @keyframes float {
          0%, 100% {
            transform: translate(0, 0) rotate(0deg);
          }
          25% {
            transform: translate(10px, -15px) rotate(5deg);
          }
          50% {
            transform: translate(-5px, -25px) rotate(-5deg);
          }
          75% {
            transform: translate(-15px, -10px) rotate(3deg);
          }
        }
      `}</style>
    </div>
  );
}
