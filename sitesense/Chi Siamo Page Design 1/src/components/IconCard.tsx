import { LucideIcon } from 'lucide-react';

interface IconCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  variant?: 'default' | 'vertical';
}

export function IconCard({ icon: Icon, title, description, variant = 'default' }: IconCardProps) {
  if (variant === 'vertical') {
    return (
      <div className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow">
        <Icon className="w-12 h-12 text-[#004D43] mb-4" />
        <h3 className="text-[22px] font-medium text-[#004D43] mb-3">{title}</h3>
        <p className="text-base text-[#333333]">{description}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow h-[260px] flex flex-col">
      <Icon className="w-12 h-12 text-[#004D43] mb-4" />
      <h3 className="text-xl font-medium text-[#004D43] mb-3">{title}</h3>
      <p className="text-base text-[#333333]">{description}</p>
    </div>
  );
}
