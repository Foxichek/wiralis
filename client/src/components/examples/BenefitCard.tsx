import BenefitCard from '../BenefitCard';
import { Sparkles } from 'lucide-react';

export default function BenefitCardExample() {
  return (
    <div className="p-8 bg-gradient-to-br from-purple-900 via-purple-800 to-purple-900">
      <div className="max-w-sm">
        <BenefitCard
          icon={Sparkles}
          title="Красивые посты"
          description="Современный дизайн для ваших новостей"
        />
      </div>
    </div>
  );
}
