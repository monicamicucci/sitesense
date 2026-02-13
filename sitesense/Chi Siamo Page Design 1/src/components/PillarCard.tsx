import { LucideIcon } from 'lucide-react';

interface PillarCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function PillarCard({ icon: Icon, title, description }: PillarCardProps) {
  return (
    <div className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow">
      <Icon className="w-14 h-14 text-[#004D43] mb-6" />
      <h3 className="text-xl font-medium text-[#004D43] mb-3">{title}</h3>
      <p className="text-base text-[#333333]">{description}</p>
    </div>
  );
}
