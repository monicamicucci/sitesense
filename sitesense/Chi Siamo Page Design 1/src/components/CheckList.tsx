import { Check } from 'lucide-react';

interface CheckListProps {
  items: string[];
}

export function CheckList({ items }: CheckListProps) {
  return (
    <div className="space-y-4">
      {items.map((item, index) => (
        <div key={index} className="flex items-start gap-4">
          <div className="flex-shrink-0 w-6 h-6 bg-[#004D43] rounded-full flex items-center justify-center mt-1">
            <Check className="w-4 h-4 text-white" />
          </div>
          <p className="text-lg text-[#333333]">{item}</p>
        </div>
      ))}
    </div>
  );
}
