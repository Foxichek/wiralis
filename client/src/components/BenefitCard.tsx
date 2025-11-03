import { LucideIcon } from 'lucide-react';

interface BenefitCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  delay?: number;
}

export default function BenefitCard({ icon: Icon, title, description, delay = 0 }: BenefitCardProps) {
  return (
    <div
      className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6 hover-elevate transition-all duration-300"
      style={{ animationDelay: `${delay}ms` }}
      data-testid={`card-benefit-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex flex-col items-center text-center space-y-4">
        <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
          <Icon className="w-7 h-7 text-white" />
        </div>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-white/70 text-sm leading-relaxed">{description}</p>
      </div>
    </div>
  );
}
